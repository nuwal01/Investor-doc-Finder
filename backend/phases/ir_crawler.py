"""
IR Crawler — crawls investor-relations pages to find PDF document links.

Input:  entity dict, doc_type (str), year (int)
Output: dict {url, source, confidence} or None

Strategy:
  1. Fast httpx fetch of the IR page + archive sub-paths
  2. Fallback to Playwright headless browser for JS-rendered pages
  3. Gemini AI-guided navigation for complex/dynamic pages
  4. Score and validate discovered PDF links
"""

import asyncio
import json
import os
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
    "financial_statement", "governance", "sustainability",
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


def _is_doc_type_rejected(url_lower: str, link_text_lower: str) -> bool:
    """Return True if this link should be rejected as a non-annual document."""
    combined = url_lower + " " + link_text_lower
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

_FY_PATTERNS = [
    # FY2024, FY24, fy2024
    r"fy\s*{year}",
    r"fy\s*{yr2}",
    # 2023-24, 2023-2024 (fiscal year ending in requested year)
    r"{prev}-{yr2}",
    r"{prev}-{year}",
    # 2024-25, 2024-2025 (fiscal year starting in requested year, common in India Apr-Mar)
    r"{year}-{next_yr2}",
    r"{year}-{next_year}",
]


def _year_score(url_lower: str, link_text_lower: str, year: int) -> float:
    """FIX 3: +0.30 exact year, -0.20 prior year, -0.10 no year found.

    Also accepts FY variants: FY2024, FY24, 2023-24, 2024-25.
    """
    import re as _re
    combined = url_lower + " " + link_text_lower
    year_str = str(year)
    prev_year = str(year - 1)
    next_year = str(year + 1)
    yr2 = year_str[2:]     # e.g. "24" for 2024
    prev_yr2 = prev_year[2:]
    next_yr2 = next_year[2:]

    # Check exact year
    if year_str in combined:
        return 0.30

    # Check FY variants
    fy_patterns = [
        f"fy{year_str}", f"fy{yr2}",
        f"{prev_year}-{yr2}", f"{prev_year}-{year_str}",
        f"{year_str}-{next_yr2}", f"{year_str}-{next_year}",
    ]
    if any(p in combined for p in fy_patterns):
        return 0.30

    # Prior year present → penalty
    if prev_year in combined:
        return -0.20

    # No year signal
    return -0.10


def score_pdf_link(url: str, year: int, doc_type: str, link_text: str = "") -> float:
    """Quick keyword score for a PDF URL + link_text. Returns float (may be negative)."""
    url_lower = url.lower()
    link_text_lower = link_text.lower()

    score = 0.0

    # FIX 3: year scoring
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
                ir_url, headers={"User-Agent": BROWSER_UA}, timeout=10,
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
                    r = await c.get(url, headers={"User-Agent": BROWSER_UA}, timeout=8)
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

    # Score and sort
    scored = [(url, lt, score_pdf_link(url, year, doc_type, lt)) for url, lt in pdf_links]
    scored.sort(key=lambda x: x[2], reverse=True)

    # Validate top 5 in parallel
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
        combined = link_score + val_score
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
    """Launch headless Chromium, render the IR page, then score PDFs."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=BROWSER_UA)

            try:
                await page.goto(ir_url, wait_until="networkidle", timeout=20_000)

                # Try clicking Annual Reports / Financial Reports navigation
                for btn_text in ("Annual Reports", "Financial Reports", "Annual Report", "Financials"):
                    try:
                        btn = page.get_by_text(btn_text, exact=False)
                        if await btn.count() > 0:
                            await btn.first.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass

                # Scroll to bottom to trigger lazy-loaded PDF links
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(5000)

                html = await page.content()
            finally:
                await browser.close()
    except Exception:
        return None, 0.0

    raw_links = extract_pdf_links(html, ir_url)
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

    scored = [(url, lt, score_pdf_link(url, year, doc_type, lt)) for url, lt in pdf_links]
    scored.sort(key=lambda x: x[2], reverse=True)

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
        combined = link_score + val_score
        if combined > best_score:
            best_score = combined
            best_url = url

    if best_url and best_score > 0.3:
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
            page = await browser.new_page(user_agent=BROWSER_UA)

            try:
                await page.goto(ir_url, wait_until="networkidle", timeout=20_000)

                for _step in range(3):
                    # Extract and validate PDF links visible on current page
                    html = await page.content()
                    current_url = page.url
                    raw_links = extract_pdf_links(html, current_url)
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
                        scored = [(u, lt, score_pdf_link(u, year, doc_type, lt)) for u, lt in links]
                        scored.sort(key=lambda x: x[2], reverse=True)
                        val_scores = await asyncio.gather(
                            *[validate_pdf(u, company_name, year, doc_type) for u, _, _ in scored[:3]],
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

                    # Screenshot → Gemini
                    screenshot_bytes = await page.screenshot(full_page=False, type="png")

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

                    try:
                        btn = page.get_by_text(click_text, exact=False)
                        if await btn.count() > 0:
                            await btn.first.click()
                            await page.wait_for_timeout(3000)
                        else:
                            break
                    except Exception:
                        break

            finally:
                await browser.close()

        if best_url and best_score > 0.3:
            return best_url, best_score
        return None, 0.0

    except Exception:
        return None, 0.0


# ── 6. Orchestrator ─────────────────────────────────────────────────────────

async def run_ir_crawl(entity: dict, doc_type: str, year: int) -> dict | None:
    """Try httpx crawl, Playwright, then Gemini AI navigation.

    Returns: {url, source, confidence, score} or None
    """
    ir_url = entity.get("ir_url", "")
    company_name = entity.get("company_name", "")

    if not ir_url:
        return None

    year_str = str(year)

    # Attempt 1: fast httpx + archive paths (hard timeout 25s)
    try:
        url, score = await asyncio.wait_for(
            crawl_httpx(ir_url, company_name, year, doc_type), timeout=25,
        )
    except asyncio.TimeoutError:
        url, score = None, 0.0
    # Only early-exit if the year appears in the URL — avoids returning a generic
    # "most recent" PDF when the user asked for a specific historical year
    if url and score >= 0.4 and year_str in url:
        return {"url": url, "source": "IR crawl (httpx)", "confidence": "medium", "score": score}

    # Keep httpx result as candidate (may still win at the end)
    httpx_result = (url, score) if url else (None, 0.0)

    # Attempt 2: Playwright for JS-heavy pages (hard timeout 35s)
    try:
        url, score = await asyncio.wait_for(
            crawl_playwright(ir_url, company_name, year, doc_type), timeout=35,
        )
    except asyncio.TimeoutError:
        url, score = None, 0.0
    if url and score >= 0.4 and year_str in url:
        return {"url": url, "source": "IR crawl (playwright)", "confidence": "medium", "score": score}

    playwright_result = (url, score) if url else (None, 0.0)

    # Attempt 3: Gemini AI navigation (hard timeout 45s)
    try:
        url, score = await asyncio.wait_for(
            crawl_with_ai_navigation(ir_url, company_name, doc_type, year), timeout=45,
        )
    except asyncio.TimeoutError:
        url, score = None, 0.0

    ai_result = (url, score) if url else (None, 0.0)

    # Pick best across all three attempts.
    # Prefer URLs that contain the requested year — a URL without the year may be
    # the "most recent" report, not the one the user asked for (especially for older
    # years like 2015 where the IR website only shows recent reports).
    candidates = [
        (httpx_result[0], httpx_result[1], "IR crawl (httpx)"),
        (playwright_result[0], playwright_result[1], "IR crawl (playwright)"),
        (ai_result[0], ai_result[1], "IR crawl (AI navigation)"),
    ]

    # First pass: prefer candidates where year is in the URL
    best_url, best_score, best_source = None, 0.0, ""
    for u, s, src in candidates:
        if u and s > best_score and year_str in u:
            best_score = s
            best_url = u
            best_source = src

    # Second pass: accept any candidate if nothing year-matched was found
    if not best_url:
        for u, s, src in candidates:
            if u and s > best_score:
                best_score = s
                best_url = u
                best_source = src
        # Without year in URL, treat result as low-confidence fallback:
        # return it only if score is very high (prevents blocking web search
        # on historical queries where IR pages lack archive PDFs)
        if best_url and best_score >= 0.8:
            return {"url": best_url, "source": best_source, "confidence": "low", "score": best_score}
        return None

    if best_url and best_score > 0.3:
        return {"url": best_url, "source": best_source, "confidence": "medium", "score": best_score}

    return None


if __name__ == "__main__":
    test_cases = [
        (
            {
                "company_name": "Apple",
                "normalized_name": "APPLE INC",
                "country": "US",
                "exchange_mic": "XNAS",
                "isin": "",
                "ir_url": "https://investor.apple.com/sec-filings/default.aspx",
                "ticker": "AAPL",
            },
            "annual_report",
            2023,
        ),
        (
            {
                "company_name": "Simsari",
                "normalized_name": "Simsari",
                "country": "AE",
                "exchange_mic": "",
                "isin": "",
                "ir_url": "https://www.simsari.ae",
                "ticker": "",
            },
            "annual_report",
            2023,
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
                print(f"  Source: {result['source']}")
                print(f"  Conf  : {result['confidence']}")
                print(f"  Score : {result['score']:.2f}")
            else:
                print("  No PDF found via IR crawl")

    asyncio.run(main())
