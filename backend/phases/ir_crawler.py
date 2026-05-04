"""
IR Crawler — crawls investor-relations pages to find PDF document links.

Input:  entity dict, doc_type (str), year (int)
Output: dict {url, source, confidence} or None

Strategy:
  1. Playwright headless browser (JS-rendered pages) — Layer 1
  2. httpx static crawl fallback — Layer 2
  3. Site-scoped Serper search fallback — Layer 3
  4. Return None to allow agent web-search fallback — Layer 4
"""

import asyncio
import json
import logging
import os
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Ensure backend/ is on sys.path for sibling imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.pdf_validator import validate_pdf

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

DOC_TYPE_KEYWORDS = {
    "annual_report": ["annual", "yearly", "10-k", "10k"],
    "quarterly_report": ["quarterly", "quarter", "10-q", "10q", "q1", "q2", "q3", "q4"],
    "investor_presentation": ["presentation", "investor-day", "analyst-day", "deck"],
}

DOC_TYPE_LABELS = {
    "annual_report": "annual report",
    "quarterly_report": "quarterly report",
    "investor_presentation": "investor presentation",
}


# ── 1. Extract PDF links from HTML ──────────────────────────────────────────

FINANCIAL_PAGE_KEYWORDS = (
    "financial", "annual", "report", "investor", "ir/", "investors",
    "shareholder", "filings", "disclosures", "quarterly",
)

ANNUAL_HREF_KEYWORDS = (
    "annual-report", "annual_report", "ar20", "annualreport",
    "/ar/", "yearly-report", "annual-results", "integrated-report",
    "integrated_report", "annual-review", "annual_review",
)

ANNUAL_TEXT_KEYWORDS = (
    "annual report", "annual review", "integrated report", "integrated annual",
    "yearly report", "full year results", "annual results",
    "年報", "rapport annuel", "jahresbericht", "informe anual",
    "relatório anual", "годовой отчет", "yıllık rapor", "年度报告",
    "تقرير سنوي", "سالانه",
)

# FIX 2: reject keywords for non-annual doc types
_DOC_TYPE_REJECT_KW = (
    "quarter", "q1", "q2", "q3", "q4", "q5", "interim",
    "half-year", "halfyear", "h1", "h2", "financial-statement",
    "financial_statement",
    # FIX A: Companies House / ROC registration documents (not annual reports)
    "annual-return", "annual_return", "annualreturn",
    "company-return", "statutory-return", "filing-return", "roc-filing",
    # AGM notices are not annual reports
    "notice-of-agm", "notice_of_agm", "agm-notice", "agm_notice",
    # TIER 3: ESG / sustainability / governance — not annual financial reports
    "sustainability", "sustainable", "esg",
    "environmental", "environment", "climate",
    "csr", "corporate-social",
    "governance", "remuneration", "proxy",
    "notice", "agm", "circular", "prospectus",
    "supplement", "offering", "memorandum",
    "earnings", "results", "press-release",
    "transcript", "presentation", "factsheet",
    "pillar3", "pillar-3", "audit-report",
    # Space-variant and additional non-financial document types
    "audit report", "audit_report",
    "modern slavery", "modern-slavery", "slavery statement", "slavery-statement",
    "modern-slavery-statement",
    "gender pay", "gender-pay",
    "tax strategy", "tax-strategy",
    "pillar 3",
    "remuneration report",
    "directors report", "directors-report",
    "half year",
    "interim report", "interim-report",
    "results briefing", "results-briefing",
    "investor presentation", "investor-presentation",
    "capital markets day",
    "rb-report", "rb_report",
    "briefing document",
    # Investor day / capital markets day events — not annual reports
    "investor-day", "investor_day", "investor day",
    # Capital markets / fundraising documents
    "rights-issue", "rights_issue", "rights issue",
    "offer document", "offer-document",
    "scrip-dividend", "scrip_dividend",
    "credit-rating", "credit_rating", "credit rating",
    "mdys", "moodys-", "fitch-", "moody",
    # Corporate actions — not annual reports
    "buyback", "buy-back", "buy_back", "buy back",
    "share-repurchase", "share_repurchase",
    "notification", "dividend-notice",
    # IR collateral / equity-story / investor-facing presentations
    "equity-story", "equity_story", "equity story",
    "equity-presentation", "equity_presentation",
    # Consent forms, policies, legal docs — not financial reports
    "consent-form", "consent_form", "consent form",
    "data-protection", "data_protection", "data protection",
    "privacy-policy", "privacy_policy",
    "where-we-operate",
    # Romanian regulatory sub-filings and presentations
    "raport-asf", "raport_asf", "raport asf",
    "raport-consiliu", "raport_consiliu",
    "raport-remunerare", "raport_remunerare",
    "raport-audit", "raport_audit",
    "situatii-financiare", "situatii_financiare",
    "prezentare", "prezentari",
    "preliminare", "preliminar",
    "rezultate-financiare", "rezultate_financiare",
    # Marketing / ops / policy docs — not annual reports
    "mining-cvp", "mining_cvp", "-cvp-", "_cvp_",
    "customer-value", "value-proposition",
    "anti-bribery", "anti_bribery",
    "code-of-conduct", "code_of_conduct",
    "bribery-policy", "bribery_policy",
    "whistleblowing", "whistle-blowing",
    "conflict-of-interest", "conflict_of_interest",
    "data-protection-policy",
    "gender-pay-gap",
    "tax-transparency", "tax_transparency",
    "supplier-code", "supplier_code",
    "customer-charter", "customer_charter",
    # Governance / committee docs
    "nomgov", "nom-gov", "nomination-governance",
    "terms-of-reference", "committee-charter", "board-charter",
    "governance-framework", "governance-report",
    "risk-register", "reestr-riskov", "risk-appetite",
    "risk-framework",
    # Policy / compliance docs
    "anticorrupcion", "anti-corruption", "anticorruption",
    "plan-anticorrupcion", "estrategia-anticorrupcion",
    "compliance-report", "compliance-framework",
    "ethics-report", "code-ethics",
    "bribery-act", "antibribery",
    # Eskom power station names — station-level reports are not group ARs
    "grootvlei", "medupi", "kusile", "koeberg", "matimba",
    "lethabo", "tutuka", "hendrina",
)

_REJECT_PATH_SEGMENTS = (
    "/agm/", "/aga/", "/agm-20", "/aga-20",
    "/adunare/", "/adunare-generala/",
    "/shareholder-meeting/", "/general-meeting/",
    "/extraordinary/", "/egm/",
    "/proxy/", "/circular/",
    "/regulatory-filing/", "/regulatory/",
    "/raport-asf/", "/asf-filing/",
    "/rezultate-financiare/", "/rezultate/",
    "/prezentari/", "/prezentari-roadshows",
    "/preliminare/",
)

# FIX 2: must contain at least one of these to be accepted as annual report
_ANNUAL_ACCEPT_KW = (
    "annual", "yearly", "ar2", "integrated report", "integrated-report",
    "annual review", "rapport annuel", "годовой", "yıllık", "relatório anual",
    "jahresbericht", "informe anual", "年度报告", "سالانه", "تقرير سنوي",
)

# FIX 4: English language indicators
_ENGLISH_KW = ("english", "_en", "-en.", "_en_", "en.pdf", "eng", "english-version")
# FIX 4: Non-English indicators
_NON_ENGLISH_KW = (
    "arabic", "_ar.", "_ar_", "عربي", "uzbek", "_uz", "russian", "_ru.",
    "turkish", "_tr.", "chinese", "_cn.", "french", "_fr.", "german", "_de.",
)

# FIX 1: Company identity scoring
_LEGAL_SUFFIXES_ID = frozenset({
    "plc", "jsc", "llc", "ltd", "inc", "corp", "corporation", "as", "sa",
    "nv", "bv", "ag", "gmbh", "oy", "ab", "asa", "se", "spa", "srl",
    "pjsc", "oao", "pao", "ojsc", "bhd", "tbk", "limited", "co",
})

_COMMON_GEO_WORDS_ID = frozenset({
    "united", "bank", "group", "holding", "holdings", "company", "companies",
    "international", "national", "global", "general", "africa", "american",
    "americas", "europe", "european", "asia", "asian", "pacific",
    "middle", "east", "north", "south", "west", "china", "india",
    "kingdom", "states", "federal", "for", "and", "the", "of",
})


def _extract_core_tokens(company_name: str) -> list[str]:
    """Strip legal suffixes and generic geo/common words; return distinctive tokens."""
    tokens = [t.lower() for t in company_name.split()]
    return [t for t in tokens
            if t not in _LEGAL_SUFFIXES_ID and t not in _COMMON_GEO_WORDS_ID and len(t) > 2]


def _name_acronym(company_name: str) -> str:
    """Derive acronym from significant words: 'United Bank Africa Plc' → 'uba'."""
    tokens = [t for t in company_name.split()
              if len(t) >= 4 and t.lower() not in _LEGAL_SUFFIXES_ID]
    return "".join(t[0].lower() for t in tokens)


def _company_identity_score(url: str, title: str, snippet: str,
                             company_name: str, ticker: str = "") -> float:
    """Score how well a search result matches the target company.

    Returns 1.0 (domain match), 0.5 (title), 0.2 (snippet only), 0.0 (no match → reject).
    Falls back to name acronym when core tokens and ticker are both absent.
    """
    core = _extract_core_tokens(company_name)
    ticker_l = ticker.lower().strip()

    # Acronym fallback when all tokens are filtered and no ticker provided
    if not core and not ticker_l:
        acronym = _name_acronym(company_name)
        if len(acronym) >= 3:
            ticker_l = acronym
        else:
            return 1.0  # truly no criteria → allow

    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        domain = url.lower()

    domain_flat = domain.replace("-", "").replace(".", "")
    title_l = title.lower()
    snippet_l = snippet.lower()

    # Domain check: single-token uses strict prefix rule to prevent "zenith" matching
    # "zenithdrugs.com"; multi-token requires all (or all-but-one for 3+) tokens.
    if ticker_l and len(ticker_l) >= 3 and ticker_l in domain_flat:
        return 1.0
    if core:
        if len(core) == 1:
            _c = core[0]
            _root = domain.split(".")[0].replace("-", "").replace("_", "")
            _exact = (_root == _c)
            _start = _root.startswith(_c) and len(_root) - len(_c) <= 4
            _end = _root.endswith(_c) and len(_root) - len(_c) <= 7
            if _exact or _start or _end:
                return 1.0
        else:
            matched = sum(1 for t in core if t in domain)
            required = len(core) if len(core) <= 2 else len(core) - 1
            if matched >= required:
                return 1.0

    # Title check: single-token uses whole-word boundary; multi-token uses any().
    if ticker_l and len(ticker_l) >= 3 and ticker_l in title_l:
        return 0.5
    if core:
        if len(core) == 1:
            if re.search(r'\b' + re.escape(core[0]) + r'\b', title_l):
                return 0.5
        elif any(t in title_l for t in core):
            return 0.5

    # Snippet check
    if ticker_l and len(ticker_l) >= 3 and ticker_l in snippet_l:
        return 0.2
    if core and any(t in snippet_l for t in core):
        return 0.2

    return 0.0  # no match → reject


def _det_sort_key(url: str, link_text: str, year: int, doc_type: str) -> tuple:
    """Deterministic sort key: (tier, no_year_match, lang_penalty, url).

    Lower values = higher priority. url as final tiebreaker ensures full determinism.
    """
    combined = url.lower() + " " + link_text.lower()
    if doc_type == "annual_report":
        if any(seg in url.lower() for seg in _REJECT_PATH_SEGMENTS) or any(kw in combined for kw in _DOC_TYPE_REJECT_KW):
            tier = 3
        elif any(kw in combined for kw in _ANNUAL_ACCEPT_KW):
            tier = 1
        else:
            tier = 2
    else:
        tier = 2
    no_year = 0 if any(p in combined for p in _build_fy_patterns(year)) else 1
    if any(kw in combined for kw in _ENGLISH_KW):
        lang = 0
    elif any(kw in combined for kw in _NON_ENGLISH_KW):
        lang = 2
    else:
        lang = 1
    return (tier, no_year, lang, url)


def _is_doc_type_rejected(url_lower: str, link_text_lower: str) -> bool:
    """Return True if this link should be rejected as a non-annual document."""
    if any(seg in url_lower for seg in _REJECT_PATH_SEGMENTS):
        return True
    url_normalized = url_lower.replace('-', ' ').replace('_', ' ').replace('%20', ' ')
    combined = url_lower + " " + url_normalized + " " + link_text_lower
    return any(kw in combined for kw in _DOC_TYPE_REJECT_KW)


def _is_annual_accepted(url_lower: str, link_text_lower: str) -> bool:
    """Return True if this link clearly identifies as an annual report."""
    combined = url_lower + " " + link_text_lower
    return any(kw in combined for kw in _ANNUAL_ACCEPT_KW)


def _language_score(url_lower: str, link_text_lower: str) -> float:
    """FIX 4: +0.15 for English signals, -0.10 for non-English signals."""
    combined = url_lower + " " + link_text_lower
    if any(kw in combined for kw in _ENGLISH_KW):
        return 0.15
    if any(kw in combined for kw in _NON_ENGLISH_KW):
        return -0.10
    return 0.0


def extract_pdf_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Parse HTML and return a deduplicated list of (absolute_url, link_text) tuples.

    Collects all href links ending in .pdf OR containing annual/report keywords.
    Also captures links whose visible text contains annual report synonyms.
    """
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[tuple[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        href_lower = href.lower()
        link_text = (a.get_text() or "").strip()
        link_text_lower = link_text.lower()

        is_pdf = href_lower.endswith(".pdf") or "pdf" in href_lower
        is_annual_href = any(kw in href_lower for kw in ANNUAL_HREF_KEYWORDS)
        is_annual_text = any(kw in link_text_lower for kw in ANNUAL_TEXT_KEYWORDS)
        # Also capture any link with 'report' in text that leads to a pdf-like path
        is_report_text = "report" in link_text_lower and ("pdf" in href_lower or "download" in href_lower)

        if is_pdf or is_annual_href or is_annual_text or is_report_text:
            absolute = urljoin(base_url, href)
            if absolute not in seen:
                seen.add(absolute)
                links.append((absolute, link_text))

    return links


def extract_financial_subpages(html: str, base_url: str) -> list[str]:
    """Find internal links that look like financial/investor report pages."""
    soup = BeautifulSoup(html, "lxml")
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    seen = set()
    pages = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != base_domain:
            continue
        combined = f"{absolute.lower()} {(a.get_text() or '').lower()}"
        if any(kw in combined for kw in FINANCIAL_PAGE_KEYWORDS):
            if absolute not in seen and absolute != base_url:
                seen.add(absolute)
                pages.append(absolute)

    return pages[:5]


# ── 2. Score a PDF link by URL keywords (no HTTP) ───────────────────────────

def _build_fy_patterns(year: int) -> list[str]:
    """Return all accepted FY-variant strings for the given year (lowercased)."""
    year_str = str(year)
    prev_year = str(year - 1)
    next_year = str(year + 1)
    yr2 = year_str[2:]
    next_yr2 = next_year[2:]
    prev_yr2 = prev_year[2:]
    return [
        year_str,
        # Direct-year FY variants (FY2024, FY24, FY-24, FY_24)
        f"fy{year_str}", f"fy{yr2}",
        f"fy-{yr2}", f"fy-{year_str}", f"fy_{yr2}",
        # Dash/range variants
        f"{prev_year}-{yr2}", f"{prev_year}-{year_str}",
        f"{year_str}-{next_yr2}", f"{year_str}-{next_year}",
        # Indian FY next-year convention: FY25 → 2024, FY2025 → 2024
        f"fy{next_yr2}", f"fy{next_year}",
        f"fy-{next_yr2}", f"fy-{next_year}",
        f"fy{year_str}-{next_yr2}", f"fy{year_str}_{next_yr2}",
        # AR / annual variants
        f"ar{year_str}", f"{year_str}ar",
        f"ar{next_yr2}", f"ar-{next_yr2}",
        f"report{year_str}", f"{year_str}report",
        f"annual{year_str}", f"{year_str}annual",
        f"annual{next_yr2}",
        f"{prev_year}_{yr2}", f"{year_str}_{next_yr2}",
    ]


def _is_prior_year(url_lower: str, link_text_lower: str, year: int) -> bool:
    """FIX B: Return True if prior-year is confirmed with NO current-year match.

    Checks the filename first to avoid upload-path false positives like
    /uploads/2024/05/uba_AR2023.pdf (path has 2024, filename has 2023).
    Checks up to 5 years back.
    """
    fy_patterns = _build_fy_patterns(year)

    # 1. Filename (last path segment) — highest signal quality
    url_filename = url_lower.rsplit("/", 1)[-1]
    if any(p in url_filename for p in fy_patterns):
        return False  # current year in filename
    for delta in range(1, 6):
        if str(year - delta) in url_filename:
            return True  # prior year in filename, no current year

    # 2. Full URL + link_text fallback
    combined = url_lower + " " + link_text_lower
    if any(p in combined for p in fy_patterns):
        return False
    for delta in range(1, 6):
        if str(year - delta) in combined:
            return True
    return False


def _year_score(url_lower: str, link_text_lower: str, year: int) -> float:
    """Return +0.30 for current year match, -0.10 for no year signal.

    Prior-year case is handled upstream by _is_prior_year() hard reject.
    """
    combined = url_lower + " " + link_text_lower
    if any(p in combined for p in _build_fy_patterns(year)):
        return 0.30
    return -0.10


def score_pdf_link(url: str, year: int, doc_type: str, link_text: str = "") -> float:
    """Quick keyword score for a PDF URL + link_text. Returns float (may be negative)."""
    url_lower = url.lower()
    link_text_lower = link_text.lower()

    # FIX B: hard reject if prior year confirmed with no current-year match
    if _is_prior_year(url_lower, link_text_lower, year):
        return 0.0

    score = 0.0
    score += _year_score(url_lower, link_text_lower, year)

    # Doc-type keywords
    keywords = DOC_TYPE_KEYWORDS.get(doc_type, [])
    if any(kw in url_lower for kw in keywords):
        score += 0.2

    if "report" in url_lower:
        score += 0.1

    # FIX 4: language scoring
    score += _language_score(url_lower, link_text_lower)

    return score


# ── 3. httpx-based crawl ────────────────────────────────────────────────────

async def crawl_httpx(
    ir_url: str, company_name: str, year: int, doc_type: str,
) -> tuple[str, float] | tuple[None, float]:
    """Fetch the IR page with httpx, score PDFs, validate the top candidates.
    Tries financial subpages + archive paths when main page has no PDFs.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                ir_url, headers={"User-Agent": BROWSER_UA},
                timeout=httpx.Timeout(60.0, connect=15.0),
            )
            if resp.status_code != 200:
                return None, 0.0
            html = resp.text
    except Exception:
        return None, 0.0

    raw_links = extract_pdf_links(html, ir_url)

    # If no PDFs on this page, try financial subpages + standard IR/archive paths
    if not raw_links:
        subpages = extract_financial_subpages(html, ir_url)
        _parsed = urlparse(ir_url)
        _base = f"{_parsed.scheme}://{_parsed.netloc}"
        _extra_paths = [
            "/annual-reports", "/investor-relations",
            "/financials", "/reports", "/investors",
            "/archive", "/annual-reports/archive",
            "/investor-relations/historical", "/financials/archive",
            "/reports/archive",
        ]
        _extra = [
            _base + sp for sp in _extra_paths if _base + sp != ir_url
        ]
        all_subpages = list(dict.fromkeys(subpages + _extra))[:12]

        async def _fetch_pdfs(url: str) -> list[tuple[str, str]]:
            try:
                async with httpx.AsyncClient(follow_redirects=True) as c:
                    r = await c.get(
                        url, headers={"User-Agent": BROWSER_UA},
                        timeout=httpx.Timeout(60.0, connect=15.0),
                    )
                    if r.status_code == 200:
                        return extract_pdf_links(r.text, url)
            except Exception:
                pass
            return []

        sub_results = await asyncio.gather(
            *[_fetch_pdfs(sp) for sp in all_subpages],
            return_exceptions=True,
        )
        for res in sub_results:
            if isinstance(res, list) and res:
                raw_links = res
                break

    if not raw_links:
        return None, 0.0

    # FIX 2: doc-type filter — reject quarterly/governance, keep annual
    if doc_type == "annual_report":
        filtered = [
            (url, lt) for url, lt in raw_links
            if not _is_doc_type_rejected(url.lower(), lt.lower())
               and _is_annual_accepted(url.lower(), lt.lower())
        ]
        # Fallback: if filter yields nothing, use all links (avoid empty result)
        pdf_links = filtered if filtered else raw_links
    else:
        pdf_links = raw_links

    # FIX 3: deterministic tier-priority sort before scoring
    pdf_links.sort(key=lambda x: _det_sort_key(x[0], x[1], year, doc_type))
    scored = [(url, lt, score_pdf_link(url, year, doc_type, lt)) for url, lt in pdf_links]

    # Validate top 5 in tier-priority order
    top_candidates = scored[:5]
    val_scores = await asyncio.gather(
        *[validate_pdf(url, company_name, year, doc_type) for url, _, _ in top_candidates],
        return_exceptions=True,
    )
    best_url = None
    best_score = 0.0
    for (url, lt, link_score), val_score in zip(top_candidates, val_scores):
        if isinstance(val_score, Exception):
            val_score = 0.0
        # FIX 4: validate_pdf hard-rejected this URL — link_score cannot rescue it
        combined = 0.0 if val_score <= 0.0 else (link_score + val_score)
        if combined > best_score:
            best_score = combined
            best_url = url

    if best_url and best_score > 0.3:
        return best_url, best_score

    return None, 0.0


# ── 4. Playwright-based crawl (JS-rendered pages) ───────────────────────────

async def crawl_playwright(
    ir_url: str, company_name: str, year: int, doc_type: str,
) -> tuple[str, float] | tuple[None, float]:
    """Launch headless Chromium in an isolated context, render the IR page, score PDFs.

    Implements all stability fixes:
    - FIX 1: every Playwright action in its own try/except
    - FIX 2: is_visible/is_enabled checks before any click
    - FIX 3: load-state fallback chain + 2s JS-render wait after every navigation
    - FIX 5: isolated browser.new_context() per crawl
    - FIX 6: scroll-to-bottom then scroll-to-top to trigger lazy content
    - FIX 7: explicit timeouts on every action
    """
    html = ""
    js_all_links: list[tuple[str, str]] = []   # FIX C: JS/iframe/onclick extracted links
    pdf_urls_intercepted: list[str] = []        # FIX C4: response-intercepted PDFs

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                # FIX 5: isolated context per crawl — await first, then manage lifetime manually
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=BROWSER_UA,
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )
                try:
                    page = await context.new_page()

                    # FIX C4: intercept PDF responses — must be wired before goto
                    async def _handle_response(response):
                        try:
                            if ".pdf" in response.url.lower() and response.status == 200:
                                pdf_urls_intercepted.append(response.url)
                        except Exception:
                            pass
                    try:
                        page.on("response", _handle_response)
                    except Exception:
                        pass

                    # FIX 1+7: goto with explicit timeout — domcontentloaded avoids
                    # hangs on heavy pages that never reach full "load"
                    try:
                        await page.goto(ir_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception as e:
                        logging.warning("[Playwright] goto failed for %s: %s", ir_url, e)

                    # FIX 3: load-state fallback chain
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=8000)
                        except Exception:
                            pass
                    # FIX 3: let JS render
                    try:
                        await page.wait_for_timeout(2000)
                    except Exception:
                        pass

                    # FIX 1+2: click Annual Reports nav with full safety checks
                    for btn_text in (
                        "Annual Reports", "Financial Reports",
                        "Annual Report", "Financials",
                    ):
                        try:
                            btn = page.get_by_text(btn_text, exact=False)
                            count = 0
                            try:
                                count = await btn.count()
                            except Exception:
                                continue
                            if count == 0:
                                continue

                            elem = btn.first
                            # FIX 2: safety checks before interaction
                            try:
                                is_visible = await elem.is_visible()
                                is_enabled = await elem.is_enabled()
                                if not is_visible or not is_enabled:
                                    continue
                            except Exception:
                                continue

                            try:
                                await elem.scroll_into_view_if_needed()
                                await elem.click(timeout=8000)
                            except Exception:
                                try:
                                    await elem.evaluate("el => el.click()")
                                except Exception:
                                    pass

                            # FIX 3: load-state fallback chain after click
                            try:
                                await page.wait_for_load_state("networkidle", timeout=15000)
                            except Exception:
                                try:
                                    await page.wait_for_load_state(
                                        "domcontentloaded", timeout=8000
                                    )
                                except Exception:
                                    pass
                            try:
                                await page.wait_for_timeout(2000)
                            except Exception:
                                pass
                            break
                        except Exception:
                            continue

                    # FIX 6: scroll to bottom to trigger lazy-loaded content
                    try:
                        await page.evaluate(
                            "window.scrollTo(0, document.body.scrollHeight)"
                        )
                    except Exception:
                        pass
                    try:
                        await page.wait_for_timeout(2000)
                    except Exception:
                        pass
                    # FIX 6: scroll back to top
                    try:
                        await page.evaluate("window.scrollTo(0, 0)")
                    except Exception:
                        pass
                    try:
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass

                    # FIX 1: get full HTML for BeautifulSoup
                    try:
                        html = await page.content()
                    except Exception as e:
                        logging.warning("[Playwright] content() failed: %s", e)

                    # FIX C1: JS-rendered link extraction (catches dynamically added DOM links)
                    try:
                        raw_js = await page.evaluate(
                            "() => Array.from(document.querySelectorAll('a'))"
                            ".map(a => ({href: a.href, text: a.innerText.trim()}))"
                            ".filter(a => a.href && a.href.length > 0)"
                        )
                        for item in raw_js or []:
                            href = str(item.get("href", "")).strip()
                            text = str(item.get("text", "")).strip()
                            if href:
                                js_all_links.append((href, text))
                    except Exception as e:
                        logging.warning("[Playwright] JS link eval failed: %s", e)

                    # FIX C2: iframe link extraction
                    try:
                        for frame in page.frames[1:]:  # skip main frame
                            try:
                                frame_js = await frame.evaluate(
                                    "() => Array.from(document.querySelectorAll('a'))"
                                    ".map(a => ({href: a.href, text: a.innerText.trim()}))"
                                )
                                for item in frame_js or []:
                                    href = str(item.get("href", "")).strip()
                                    text = str(item.get("text", "")).strip()
                                    if href:
                                        js_all_links.append((href, text))
                            except Exception:
                                continue
                    except Exception:
                        pass

                    # FIX C3: onclick handler PDF URLs
                    try:
                        onclick_vals = await page.evaluate(
                            "() => Array.from(document.querySelectorAll('[onclick]'))"
                            ".map(el => el.getAttribute('onclick'))"
                            ".filter(v => v && v.includes('.pdf'))"
                        )
                        import re as _re_c3
                        for onclick in onclick_vals or []:
                            for match in _re_c3.findall(
                                r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick, _re_c3.IGNORECASE
                            ):
                                js_all_links.append((match, ""))
                    except Exception:
                        pass

                finally:
                    try:
                        await context.close()
                    except Exception:
                        pass
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass

    except Exception as e:
        logging.warning("[Playwright] browser-level error: %s", e)

    # FIX C4: add response-intercepted PDF URLs
    for pdf_url in pdf_urls_intercepted:
        js_all_links.append((pdf_url, ""))

    # Build combined raw_links: BeautifulSoup (html) + JS-extracted links
    seen_urls: set[str] = set()
    raw_links: list[tuple[str, str]] = []

    if html:
        for url, text in extract_pdf_links(html, ir_url):
            if url not in seen_urls:
                seen_urls.add(url)
                raw_links.append((url, text))

    # Filter JS-extracted links the same way extract_pdf_links() does
    for href, text in js_all_links:
        if not href.startswith("http"):
            href = urljoin(ir_url, href)
        if href in seen_urls:
            continue
        href_lower = href.lower()
        text_lower = text.lower()
        is_pdf = ".pdf" in href_lower
        is_annual_href = any(kw in href_lower for kw in ANNUAL_HREF_KEYWORDS)
        is_annual_text = any(kw in text_lower for kw in ANNUAL_TEXT_KEYWORDS)
        is_report_dl = "report" in text_lower and (
            "pdf" in href_lower or "download" in href_lower
        )
        if is_pdf or is_annual_href or is_annual_text or is_report_dl:
            seen_urls.add(href)
            raw_links.append((href, text))

    if not raw_links:
        return None, 0.0

    # FIX 2: doc-type filter
    if doc_type == "annual_report":
        filtered = [
            (url, lt) for url, lt in raw_links
            if not _is_doc_type_rejected(url.lower(), lt.lower())
               and _is_annual_accepted(url.lower(), lt.lower())
        ]
        pdf_links = filtered if filtered else raw_links
    else:
        pdf_links = raw_links

    # FIX 3: deterministic tier-priority sort before scoring
    pdf_links.sort(key=lambda x: _det_sort_key(x[0], x[1], year, doc_type))
    scored = [(url, lt, score_pdf_link(url, year, doc_type, lt)) for url, lt in pdf_links]

    top_candidates = scored[:5]
    val_scores = await asyncio.gather(
        *[validate_pdf(url, company_name, year, doc_type) for url, _, _ in top_candidates],
        return_exceptions=True,
    )
    best_url = None
    best_score = 0.0
    for (url, lt, link_score), val_score in zip(top_candidates, val_scores):
        if isinstance(val_score, Exception):
            val_score = 0.0
        # FIX 4: validate_pdf hard-rejected this URL — link_score cannot rescue it
        combined = 0.0 if val_score <= 0.0 else (link_score + val_score)
        if combined > best_score:
            best_score = combined
            best_url = url

    if best_url and best_score > 0.3:
        return best_url, best_score

    return None, 0.0


# ── 4b. Site-scoped Serper search (Layer 3 fallback) ────────────────────────

async def _crawl_serper_site_scoped(
    ir_url: str, company_name: str, year: int, doc_type: str, ticker: str = "",
) -> tuple[str, float] | tuple[None, float]:
    """Layer 3: targeted site-scoped Serper search on the IR domain.

    Tries progressively broader queries until candidates are found.
    Multi-query strategy handles FY-notation sites (e.g. MTN uses FY-24 not 2024)
    and non-English IR pages (e.g. Petrobras Portuguese).
    """
    if not SERPER_API_KEY:
        return None, 0.0

    try:
        ir_domain = urlparse(ir_url).netloc
        if not ir_domain:
            return None, 0.0

        yr2 = str(year)[2:]
        next_yr2 = str(year + 1)[2:]
        doc_label = DOC_TYPE_LABELS.get(doc_type, "annual report")
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

        # Ordered most-precise → broadest; break after first query that yields candidates.
        query_list = [
            f'site:{ir_domain} "{doc_label}" {year} filetype:pdf',       # primary
            f'site:{ir_domain} FY{yr2} filetype:pdf',                     # FY24
            f'site:{ir_domain} "FY-{yr2}" filetype:pdf',                  # FY-24
            f'site:{ir_domain} FY{next_yr2} filetype:pdf',                # Indian FY25→2024
            f'site:{ir_domain} {year} {doc_label} filetype:pdf',          # unquoted
            f'site:{ir_domain} {year} filetype:pdf',                      # broadest
        ]
    except Exception as e:
        logging.warning("[Serper] site-scoped search failed: %s", e)
        return None, 0.0

    candidates: list[tuple[str, str, str]] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for query in query_list:
            try:
                resp = await client.post(
                    SERPER_URL, json={"q": query, "num": 10},
                    headers=headers,
                    timeout=httpx.Timeout(60.0, connect=15.0),
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception as e:
                logging.warning("[Serper] site-scoped query failed: %s", e)
                continue

            batch: list[tuple[str, str, str]] = []
            for item in data.get("organic", []):
                link = item.get("link", "")
                if not link or ".pdf" not in link.lower():
                    continue
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                url_lower = link.lower()

                if doc_type == "annual_report" and _is_doc_type_rejected(url_lower, title.lower()):
                    continue
                if _company_identity_score(link, title, snippet, company_name, ticker) == 0.0:
                    continue

                batch.append((link, title, snippet))

            if batch:
                candidates = batch
                logging.info("[Serper] site-scoped: found %d candidates via: %s", len(batch), query)
                break  # stop at first query that yields results

    if not candidates:
        return None, 0.0

    # Deduplicate preserving order
    seen: set[str] = set()
    unique_candidates: list[tuple[str, str, str]] = []
    for item in candidates:
        if item[0] not in seen:
            seen.add(item[0])
            unique_candidates.append(item)

    scored = [
        (url, title, score_pdf_link(url, year, doc_type))
        for url, title, _ in unique_candidates[:5]
    ]
    scored.sort(key=lambda x: x[2], reverse=True)

    val_scores = await asyncio.gather(
        *[validate_pdf(url, company_name, year, doc_type) for url, _, _ in scored],
        return_exceptions=True,
    )
    best_url = None
    best_score = 0.0
    for (url, title, link_score), val_score in zip(scored, val_scores):
        if isinstance(val_score, Exception):
            val_score = 0.0
        combined = 0.0 if val_score <= 0.0 else (link_score + val_score)
        if combined >= 0.80 and combined > best_score:
            best_score = combined
            best_url = url

    if best_url:
        return best_url, best_score
    return None, 0.0


# ── 5. Gemini AI-guided navigation ──────────────────────────────────────────

async def crawl_with_ai_navigation(
    ir_url: str, company_name: str, doc_type: str, year: int,
) -> tuple[str | None, float]:
    """Use Playwright + Gemini Vision to navigate and find investor PDFs.

    Steps up to 3 times:
      1. Extract PDF links from current page and validate (quick wins)
      2. Screenshot → Gemini → JSON with {found_pdf, pdf_url, click_text, confidence}
      3. If PDF found directly → validate
      4. If navigation hint → click element, wait, repeat

    All Playwright actions are individually wrapped in try/except (FIX 1).
    Uses isolated browser context per crawl (FIX 5).
    """
    if not GEMINI_API_KEY:
        return None, 0.0

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        from playwright.async_api import async_playwright

        doc_label = DOC_TYPE_LABELS.get(doc_type, "annual report")
        best_url: str | None = None
        best_score = 0.0

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                # FIX 5: isolated context — await first, then manage lifetime manually
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=BROWSER_UA,
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )
                try:
                    page = await context.new_page()

                    # FIX 1+7: goto with timeout — domcontentloaded avoids
                    # hangs on heavy pages that never reach full "load"
                    try:
                        await page.goto(ir_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception as e:
                        logging.warning("[AI Nav] goto failed: %s", e)

                    # FIX 3: load-state fallback chain
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=8000)
                        except Exception:
                            pass
                    try:
                        await page.wait_for_timeout(2000)
                    except Exception:
                        pass

                    for _step in range(3):
                        # FIX 1: get page content
                        html = ""
                        try:
                            html = await page.content()
                        except Exception as e:
                            logging.warning("[AI Nav] content() failed: %s", e)

                        current_url = page.url
                        raw_links = extract_pdf_links(html, current_url) if html else []
                        if raw_links:
                            if doc_type == "annual_report":
                                filtered = [
                                    (u, lt) for u, lt in raw_links
                                    if not _is_doc_type_rejected(u.lower(), lt.lower())
                                       and _is_annual_accepted(u.lower(), lt.lower())
                                ]
                                links = filtered if filtered else raw_links
                            else:
                                links = raw_links
                            scored = [
                                (u, lt, score_pdf_link(u, year, doc_type, lt))
                                for u, lt in links
                            ]
                            scored.sort(key=lambda x: x[2], reverse=True)
                            val_scores = await asyncio.gather(
                                *[
                                    validate_pdf(u, company_name, year, doc_type)
                                    for u, _, _ in scored[:3]
                                ],
                                return_exceptions=True,
                            )
                            for (u, lt, ls), vs in zip(scored[:3], val_scores):
                                if isinstance(vs, Exception):
                                    vs = 0.0
                                combined = ls + vs
                                if combined > best_score:
                                    best_score = combined
                                    best_url = u
                            if best_score >= 0.4:
                                break

                        # FIX 1: screenshot
                        screenshot_bytes = b""
                        try:
                            screenshot_bytes = await page.screenshot(
                                full_page=False, type="png"
                            )
                        except Exception as e:
                            logging.warning("[AI Nav] screenshot failed: %s", e)
                            break

                        if not screenshot_bytes:
                            break

                        prompt = (
                            f"You are helping find the {doc_label} for {company_name} "
                            f"for the year {year} on this website.\n"
                            f"Look at this webpage screenshot carefully.\n\n"
                            f"Respond in JSON only, no extra text:\n"
                            f'{{\"found_pdf\":true or false,'
                            f'\"pdf_url\":\"direct PDF URL if visible on page or empty string\",'
                            f'\"click_text\":\"exact text of button or menu item to click to navigate '
                            f'toward annual reports section\",'
                            f'\"confidence\":\"high or medium or low\"}}\n\n'
                            f"Rules:\n"
                            f"- If you can see a direct PDF download link for {year} set found_pdf=true\n"
                            f"- If you need to navigate deeper provide click_text\n"
                            f"- If the page is irrelevant set confidence=low\n"
                            f"- Respond ONLY with valid JSON, nothing else"
                        )

                        try:
                            gemini_resp = model.generate_content(
                                [prompt, {"mime_type": "image/png", "data": screenshot_bytes}]
                            )
                            response_text = gemini_resp.text.strip()
                            if "{" in response_text and "}" in response_text:
                                response_text = response_text[
                                    response_text.index("{") : response_text.rindex("}") + 1
                                ]
                            gemini_data = json.loads(response_text)
                        except Exception:
                            break

                        # If Gemini spotted a direct PDF
                        if gemini_data.get("found_pdf") and gemini_data.get("pdf_url"):
                            pdf_url = gemini_data["pdf_url"]
                            try:
                                s = await validate_pdf(pdf_url, company_name, year, doc_type)
                                if s > best_score:
                                    best_score = s
                                    best_url = pdf_url
                            except Exception:
                                pass
                            if best_score >= 0.3:
                                break

                        # Navigate using Gemini's hint
                        click_text = gemini_data.get("click_text", "").strip()
                        confidence = gemini_data.get("confidence", "low")
                        if not click_text or confidence == "low":
                            break

                        # FIX 1+2: click with safety checks
                        try:
                            btn = page.get_by_text(click_text, exact=False)
                            count = 0
                            try:
                                count = await btn.count()
                            except Exception:
                                break
                            if count > 0:
                                elem = btn.first
                                # FIX 2: safety checks
                                try:
                                    is_visible = await elem.is_visible()
                                    is_enabled = await elem.is_enabled()
                                    if not is_visible or not is_enabled:
                                        break
                                except Exception:
                                    break
                                try:
                                    await elem.click(timeout=8000)
                                except Exception as e:
                                    logging.warning(
                                        "[AI Nav] click '%s' failed: %s", click_text, e
                                    )
                                    break
                                # FIX 3: load-state fallback after click
                                try:
                                    await page.wait_for_load_state(
                                        "networkidle", timeout=15000
                                    )
                                except Exception:
                                    try:
                                        await page.wait_for_load_state(
                                            "domcontentloaded", timeout=8000
                                        )
                                    except Exception:
                                        pass
                                try:
                                    await page.wait_for_timeout(2000)
                                except Exception:
                                    pass
                            else:
                                break
                        except Exception:
                            break

                finally:
                    try:
                        await context.close()
                    except Exception:
                        pass
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass

        if best_url and best_score > 0.3:
            return best_url, best_score
        return None, 0.0

    except Exception:
        return None, 0.0


# ── 6. Orchestrator — 4-layer fallback chain ────────────────────────────────

async def run_ir_crawl(entity: dict, doc_type: str, year: int) -> dict | None:
    """4-layer fallback: Playwright → httpx → site-scoped Serper → None.

    Layer 1 (Playwright, 45s): JS-rendered pages, full browser interaction.
    Layer 2 (httpx,      20s): Static HTML parse + archive sub-path crawl.
    Layer 3 (Serper,     15s): site:{ir_domain} "annual report" {year} filetype:pdf
    Layer 4:                   Returns None so the agent falls through to web search.

    Returns: {url, source, confidence, score} or None
    """
    ir_url = entity.get("ir_url", "")
    company_name = entity.get("company_name", "")

    if not ir_url:
        return None

    # ── Layer 1: Playwright (JS-heavy pages) ──────────────────────────────
    try:
        url, score = await asyncio.wait_for(
            crawl_playwright(ir_url, company_name, year, doc_type),
            timeout=45,
        )
    except asyncio.TimeoutError:
        logging.warning("[IR Crawl] Layer 1 (Playwright) timed out for %s", ir_url)
        url, score = None, 0.0

    if url:
        logging.info("[IR Crawl] Layer 1 (Playwright) found %s (score %.2f)", url, score)
        return {
            "url": url,
            "source": "IR crawl (playwright)",
            "confidence": "medium",
            "score": score,
        }

    logging.info("[IR Crawl] Layer 1 (Playwright) -> 0 results, trying httpx...")

    # ── Layer 2: httpx (static HTML + archive paths) ──────────────────────
    try:
        url, score = await asyncio.wait_for(
            crawl_httpx(ir_url, company_name, year, doc_type),
            timeout=60,
        )
    except asyncio.TimeoutError:
        logging.warning("[IR Crawl] Layer 2 (httpx) timed out for %s", ir_url)
        url, score = None, 0.0

    if url:
        logging.info("[IR Crawl] Layer 2 (httpx) found %s (score %.2f)", url, score)
        return {
            "url": url,
            "source": "IR crawl (httpx)",
            "confidence": "medium",
            "score": score,
        }

    logging.info("[IR Crawl] Layer 2 (httpx) -> 0 results, trying site-scoped Serper...")

    # ── Layer 3: site-scoped Serper — try primary URL + all CDN candidates ──
    # CDN variants are generated by entity_resolver (FIX 2) for cases where PDFs
    # live on a subdomain different from the main IR page (e.g. s.turkcell.com.tr).
    _ticker = entity.get("ticker", "")
    _serper_candidates = [ir_url] + entity.get("ir_url_candidates", [])
    for _candidate_url in _serper_candidates:
        try:
            url, score = await asyncio.wait_for(
                _crawl_serper_site_scoped(_candidate_url, company_name, year, doc_type,
                                          _ticker),
                timeout=30,  # increased: multi-query strategy may use up to 6 Serper requests
            )
        except asyncio.TimeoutError:
            logging.warning("[IR Crawl] Layer 3 (Serper) timed out for %s", _candidate_url)
            url, score = None, 0.0
        if url:
            logging.info("[IR Crawl] Layer 3 (Serper) found %s (score %.2f) via %s",
                         url, score, _candidate_url)
            return {
                "url": url,
                "source": "IR crawl (serper)",
                "confidence": "low",
                "score": score,
            }

    logging.info(
        "[IR Crawl] All 3 layers found 0 results for %d, trying year fallback...", year
    )

    # ── Layer 4: Year fallback — retry all layers with year-1 ─────────────
    fallback_year = year - 1
    for _fn, _timeout, _source, _kw in (
        (crawl_playwright, 45, "IR crawl (playwright)", {}),
        (crawl_httpx, 60, "IR crawl (httpx)", {}),
        (_crawl_serper_site_scoped, 30, "IR crawl (serper)", {"ticker": _ticker}),
    ):
        try:
            url, score = await asyncio.wait_for(
                _fn(ir_url, company_name, fallback_year, doc_type, **_kw), timeout=_timeout
            )
        except asyncio.TimeoutError:
            url, score = None, 0.0
        if url:
            logging.info(
                "[IR Crawl] Year fallback: found %s via %s (year %d)",
                url, _source, fallback_year,
            )
            return {
                "url": url,
                "source": _source,
                "confidence": "low",
                "score": score,
                "year_fallback": True,
                "requested_year": year,
                "found_year": fallback_year,
            }

    logging.info("[IR Crawl] Year fallback also failed for %s — agent falls to web search", ir_url)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    test_cases = [
        (
            {
                "company_name": "UzAuto Motors",
                "normalized_name": "UzAuto Motors",
                "country": "UZ",
                "exchange_mic": "",
                "isin": "",
                "ir_url": "https://uzautomotors.com/investors",
                "ticker": "",
            },
            "annual_report",
            2024,
        ),
        (
            {
                "company_name": "UltraTech Cement",
                "normalized_name": "UltraTech Cement",
                "country": "IN",
                "exchange_mic": "",
                "isin": "",
                "ir_url": "https://www.ultratechcement.com/corporate/investors-/financials-",
                "ticker": "",
            },
            "annual_report",
            2024,
        ),
        (
            {
                "company_name": "UBA Group",
                "normalized_name": "UBA Group",
                "country": "NG",
                "exchange_mic": "",
                "isin": "",
                "ir_url": "https://www.ubagroup.com/investors/financial-reports/",
                "ticker": "",
            },
            "annual_report",
            2024,
        ),
    ]

    async def main():
        for entity, doc_type, year in test_cases:
            name = entity["company_name"]
            ir = entity["ir_url"]
            print(f"\n{'='*60}")
            print(f"  {name} | {doc_type} | {year}")
            print(f"  IR URL: {ir}")
            print("=" * 60)
            result = await run_ir_crawl(entity, doc_type, year)
            if result:
                print(f"  Found : {result['url'][:100]}")
                print(f"  Layer : {result['source']}")
                print(f"  Conf  : {result['confidence']}")
                print(f"  Score : {result['score']:.2f}")
                if result.get("year_fallback"):
                    print(
                        f"  ⚠ Year fallback: requested {result['requested_year']}"
                        f" -> found {result['found_year']}"
                    )
            else:
                print("  No PDF found — all layers + year fallback failed")
                print(f"  Manual URL: {ir}")

    asyncio.run(main())
