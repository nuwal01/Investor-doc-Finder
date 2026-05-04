"""
PDF Validator — scores a URL for likelihood of being the target investor document.

Input:  url (str), company_name (str), year (int), doc_type (str), ir_url (str)
Output: float score between 0.0 and 2.0

Score breakdown (max 2.00):
  DOC TYPE     (0.00 – 0.80)  confirmed / ambiguous / rejected (hard-reject → 0.0)
  YEAR MATCH   (0.00 – 0.50)  exact FY match / no signal / wrong year (hard-reject → 0.0)
  SOURCE QUAL  (0.00 – 0.40)  IR domain (+0.40) / trusted exchange (+0.20) / aggregator (0.00)
  LANGUAGE     (0.00 – 0.15)  English (+0.15) / neutral (+0.05) / non-English (0.00)
  FILE VALID   (0.00 – 0.15)  HTTP 200 (+0.15) / unverified (+0.05) / 4xx (hard-reject → 0.0)

Minimum passing score: 0.80
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

import httpx

MIN_SIZE = 100 * 1024        # 100 KB
MAX_SIZE = 50 * 1024 * 1024  # 50 MB

YEAR_PATTERN = re.compile(r'(?:19|20)\d{2}')

# NSE annual report URL encodes the exact FY as:
#   annual_reports/AR_{id}_{ticker}_{fy_start}_{fy_end}_{timestamp}.pdf
_NSE_AR_RE = re.compile(r'annual_reports/ar_\d+_[^/]+?_(\d{4})_(\d{4})_')

# Official exchange domains — contribute to SOURCE QUALITY score (+0.20).
# They NEVER bypass doc-type or year enforcement.
# sec.gov is listed here so EDGAR .htm 10-K files (primary filing format) bypass
# the PDF-extension gate while still being subject to doc-type and year checks.
TRUSTED_EXCHANGE_DOMAINS = (
    "sec.gov",
    "bseindia.com", "nseindia.com", "archives.nseindia.com",
    "nsearchives.nseindia.com", "kap.org.tr",
    "dfm.ae", "feeds.dfm.ae", "adx.ae", "apigateway.adx.ae",
    "saudiexchange.sa", "bursamalaysia.com", "sgx.com",
    "set.or.th", "jse.co.za", "ngxgroup.com", "stockex.co.tt", "jamstockex.com",
)

# Third-party aggregators — score 0.00 for SOURCE QUALITY, deprioritized over direct sources.
AGGREGATOR_DOMAINS = (
    "annualreports.com", "annualreport.com",
    "scribd.com", "slideshare.net",
    "axisdirect.in", "simplehai.axisdirect.in",
    "moneycontrol.com", "screener.in",
    "marketscreener.com", "wsj.com",
    "macrotrends.net", "wisesheets.io",
    "stock-analysis.com", "comparecamp.com",
    "yahoo.com", "finance.yahoo.com", "marketwatch.com", "investing.com",
    "stockanalysis.com", "simplywall.st",
    "planet-tracker.org", "influencemap.org", "carbontracker.org",
    "shareaction.org", "sustainalytics.com",
)

PRESS_RELEASE_KEYWORDS = (
    "press_release", "press-release", "pressrelease",
    "media-release", "media_release", "mediarelease",
    "news-release", "news_release", "newsrelease",
    "press/release", "media/release", "news/release",
    "/media/", "/news/", "/announcement",
    "credit_rating", "credit-rating", "creditrating",
)

# Hard-reject domains (credit rating agencies etc.) — always 0.0 regardless of doc type.
REJECT_DOMAINS = (
    "careratings", "crisil", "icra.in", "icra.com",
    "infomerics", "acuite", "brickworkratings",
    "india-ratings", "moodys.com", "spglobal.com", "fitchratings",
)

# Keywords that confirm the URL is an annual report.
ANNUAL_KEYWORDS = (
    "annual", "annual-report", "annual_report", "ar20", "annualreport",
    "integrated-report", "integrated_report", "annual-review", "annual_review",
    "10-k", "10k",   # SEC annual filing forms (US domestic)
    "20-f", "20f",   # SEC Form 20-F: annual filing for foreign private issuers (e.g. Petrobras, LUKOIL)
)

QUARTERLY_KEYWORDS = ("quarterly", "quarter", "q1", "q2", "q3", "q4", "10-q", "10q")

# GROUP A: Hard-reject keywords checked against the FULL URL (including normalized form).
# These unambiguously mean it's not an annual report regardless of where they appear in the path.
HARD_REJECT_FULL_URL_KW = (
    "quarter", "q1", "q2", "q3", "q4", "q5", "10-q", "10q",
    "interim", "half-year", "halfyear", "_h1_", "_h2_", "-h1-", "-h2-",
    "sustainability", "sustainable", "esg",
    "environmental", "environment", "climate", "csr",
    "corporate-social", "proxy", "prospectus",
    "press-release", "transcript", "factsheet",
    "annual-return", "annual_return", "annualreturn",
    "fitch", "moodys", "moody-", "credit-opinion",
    "rating-report", "ratings-report", "rating_report",
    "modern-slavery", "gender-pay", "pillar3", "pillar-3",
    "whistleblowing", "anticorruption", "anti-corruption",
    "buyback", "buy-back", "rights-issue", "rights_issue",
)

# GROUP B: Reject keywords checked against the FILENAME ONLY (url.rsplit('/', 1)[-1]).
# These are only meaningful if they appear in the actual filename, not a parent directory
# (e.g. "governance" in /corporate-governance/annual-reports/2024.pdf must not reject).
FILENAME_ONLY_REJECT_KW = (
    "notice", "agm", "circular",
    "supplement", "offering", "memorandum",
    "earnings", "results",
    "governance", "remuneration",
    "directors report", "directors-report",
    "audit report", "audit-report", "audit_report",
    "financial-statement", "financial_statement",
    "investor presentation", "investor-presentation",
    "capital markets day", "investor-day", "investor_day",
    "equity-story", "equity_story",
    "consent-form", "data-protection", "privacy-policy",
    "compliance-report", "ethics-report", "code-ethics",
    "risk-register", "risk-framework",
    "gender pay gap", "tax-strategy", "tax-transparency",
    "supplier-code", "customer-charter",
    "nomgov", "nom-gov", "terms-of-reference",
    "board-charter", "governance-framework",
    "scrip-dividend", "dividend-notice",
    "notification", "share-repurchase",
    "prezentare", "prezentari", "preliminare",
    "raport-asf", "raport-consiliu", "raport-remunerare",
    "raport-audit", "situatii-financiare",
    "rezultate-financiare",
    "mining-cvp", "customer-value", "value-proposition",
    "anti-bribery", "code-of-conduct", "bribery-policy",
    "conflict-of-interest", "gender-pay-gap",
    "supplier-code", "customer-charter",
    "rb-report", "briefing document",
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

_EN_URL_KW = ("english", "_en_", "-en-", "_en.", "-en.", "eng_", "_eng", "english-version")
_NON_EN_URL_KW = (
    "arabic", "_ar_", "_ar.", "-ar-", "عربي", "uzbek", "_uz_",
    "russian", "_ru_", "_ru.", "turkish", "_tr_", "_tr.", "chinese", "_cn_",
    "french", "_fr_", "german", "_de_",
)


def doc_type_tier(url: str, doc_type: str) -> int:
    """Return tier classification for a URL.

    1 — confirmed annual report (ANNUAL_KEYWORDS in URL)
    2 — ambiguous (has 'report' or no keyword either way)
    3 — hard reject (_ANNUAL_REJECT_URL_KW matched)

    Used by web_search.py to prefer TIER 1 results over TIER 2.
    """
    if doc_type != "annual_report":
        return 2
    url_lower = url.lower()
    if any(seg in url_lower for seg in _REJECT_PATH_SEGMENTS):
        return 3
    # GROUP A: check against full URL
    url_normalized = url_lower.replace('-', ' ').replace('_', ' ')
    if any(kw in url_lower or kw in url_normalized for kw in HARD_REJECT_FULL_URL_KW):
        return 3
    # GROUP B: check against filename only
    url_filename = url_lower.rsplit('/', 1)[-1]
    url_filename_normalized = url_filename.replace('-', ' ').replace('_', ' ')
    if any(kw in url_filename or kw in url_filename_normalized for kw in FILENAME_ONLY_REJECT_KW):
        return 3
    if any(kw in url_lower for kw in ANNUAL_KEYWORDS):
        return 1
    return 2


async def validate_pdf(
    url: str,
    company_name: str,
    year: int,
    doc_type: str,
    ir_url: str = "",
) -> float:
    """Score a URL from 0.0–2.0 for likelihood of being the target investor document.

    Hard rejects return 0.0 immediately. Minimum meaningful passing score is 0.80.
    Trusted exchange domains contribute to SOURCE QUALITY only — they never bypass
    doc-type or year checks.
    """
    try:
        url_lower = url.lower()

        # ── Hard-reject: credit rating agencies and similar ───────────────────
        if any(domain in url_lower for domain in REJECT_DOMAINS):
            return 0.0

        # ── Hard-reject: company-specific subsidiary path checks ──────────────
        _company_l = company_name.lower()
        if "adani ports" in _company_l or "apsez" in _company_l:
            if any(p in url_lower for p in (
                "/acc/", "/adani-cement/", "/adani-green/", "/adani-power/",
            )):
                return 0.0
        if "eskom" in _company_l:
            if any(s in url_lower for s in (
                "grootvlei", "medupi", "kusile", "koeberg", "matimba",
                "lethabo", "tutuka", "hendrina", "arnot", "camden",
            )):
                return 0.0

        # ── Hard-reject: unambiguous press releases ───────────────────────────
        is_press_release = any(kw in url_lower for kw in PRESS_RELEASE_KEYWORDS)
        if is_press_release:
            if "press_release" in url_lower and not any(
                kw in url_lower for kw in ("annual", "report")
            ):
                return 0.0

        is_trusted_exchange = any(d in url_lower for d in TRUSTED_EXCHANGE_DOMAINS)

        # ── DOC TYPE (0.00 – 0.80) — highest weight, no exceptions ──────────
        # Trusted exchange domains are NOT exempt from doc-type rejection.
        # Check both raw URL and normalized form (hyphens/underscores → spaces)
        # to catch "modern-slavery-statement", "audit_report", etc.
        _url_normalized = url_lower.replace('-', ' ').replace('_', ' ').replace('%20', ' ')
        if doc_type == "annual_report":
            if any(seg in url_lower for seg in _REJECT_PATH_SEGMENTS):
                return 0.0  # hard-reject: AGM/regulatory folder path
            # GROUP A: check against full URL
            if any(kw in url_lower or kw in _url_normalized for kw in HARD_REJECT_FULL_URL_KW):
                return 0.0
            # GROUP B: check against filename only
            url_filename = url_lower.rsplit('/', 1)[-1]
            _url_filename_normalized = url_filename.replace('-', ' ').replace('_', ' ').replace('%20', ' ')
            if any(kw in url_filename or kw in _url_filename_normalized for kw in FILENAME_ONLY_REJECT_KW):
                return 0.0
            if any(kw in url_lower for kw in ANNUAL_KEYWORDS):
                doc_type_score = 0.80  # confirmed
            else:
                doc_type_score = 0.30  # ambiguous — no keywords either way
        elif doc_type == "quarterly_report":
            if any(kw in url_lower for kw in QUARTERLY_KEYWORDS):
                doc_type_score = 0.80
            else:
                doc_type_score = 0.30
        else:
            doc_type_score = 0.30  # unknown doc type → ambiguous

        # Press release soft penalty on doc_type_score
        if is_press_release:
            doc_type_score = max(0.0, doc_type_score - 0.20)

        # ── FILE VALIDITY (0.00 – 0.15) ───────────────────────────────────────
        file_validity_score = 0.05  # unverified default (no HTTP request yet)
        content_type = ""
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.head(url, timeout=8)
            if resp.status_code >= 400:
                if resp.status_code in (403, 405):
                    pass  # server blocks HEAD requests — treat as unverified, file likely exists
                else:
                    return 0.0  # 404 / server error — hard-reject
            else:
                file_validity_score = 0.15  # HTTP 200 confirmed
                content_type = resp.headers.get("content-type", "").lower()
        except Exception:
            pass  # network error → treat as unverified (file_validity_score stays 0.05)

        # PDF gate: must look like a PDF (trusted exchange CDN may lack .pdf extension)
        is_pdf = ("pdf" in content_type) or url_lower.rstrip("/").endswith(".pdf")
        if not is_pdf and not is_trusted_exchange:
            return 0.0

        # ── YEAR MATCH (0.00 – 0.50) ──────────────────────────────────────────
        # NSE annual report FY range takes priority over the general year check.
        nse_m = _NSE_AR_RE.search(url_lower)
        skip_general_year_check = False
        year_score = 0.0

        if nse_m:
            fy_end = int(nse_m.group(2))
            if fy_end == year:
                year_score = 0.50
                skip_general_year_check = True
            elif fy_end > year:
                return 0.0  # FY ends after requested year → wrong report
            else:
                skip_general_year_check = True  # older FY — neutral, no year bonus

        if not skip_general_year_check:
            year_str = str(year)
            prev_year = str(year - 1)
            yr2 = year_str[2:]
            prev_yr2 = prev_year[2:]
            next_year = str(year + 1)
            next_yr2 = next_year[2:]

            fy_variants = [
                # Direct-year FY variants (FY2024, FY24, FY-24, FY_24)
                f"fy{year_str}", f"fy{yr2}",
                f"fy-{yr2}", f"fy-{year_str}", f"fy_{yr2}",
                # Dash/range variants (2023-24 style)
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
            # Dash-separated FY variants (e.g. "2023-24") can false-match inside date ranges
            # like "17.11.2023-24.11.2023". Use regex to require they're not surrounded by digits.
            _fy_dash = [
                f"{prev_year}-{yr2}", f"{prev_year}-{year_str}",
                f"{year_str}-{next_yr2}", f"{year_str}-{next_year}",
            ]
            _fy_other = [p for p in fy_variants if p not in _fy_dash]

            def _fy_dash_match(url_l: str, patterns: list) -> bool:
                for p in patterns:
                    if re.search(r'(?<!\d)' + re.escape(p) + r'(?!\d)', url_l):
                        return True
                return False

            # FIX 1: check filename FIRST — upload-path date (e.g. /2024/04/) must not
            # override the report year stated in the filename (e.g. FY-23-Report.pdf).
            url_filename = url_lower.rsplit("/", 1)[-1]
            filename_has_current = (
                year_str in url_filename
                or any(p in url_filename for p in _fy_other)
                or _fy_dash_match(url_filename, _fy_dash)
            )

            if filename_has_current:
                year_score = 0.50  # year confirmed in filename — don't check path date
            else:
                # Prior-year FY variants in filename (e.g. FY-23 when requesting 2024)
                _prior_fy = [
                    f"fy{prev_yr2}", f"fy-{prev_yr2}", f"fy_{prev_yr2}",
                    f"fy{prev_year}", f"fy-{prev_year}",
                    f"fy{str(year - 2)[2:]}", f"fy-{str(year - 2)[2:]}",
                ]
                filename_years_4d = [int(y) for y in YEAR_PATTERN.findall(url_filename)]
                if (any(p in url_filename for p in _prior_fy)
                        or (filename_years_4d and any(y < year for y in filename_years_4d))):
                    return 0.0  # prior year confirmed in filename

                # No year signal in filename — fall back to full URL check
                years_in_url = [int(y) for y in YEAR_PATTERN.findall(url)]
                if years_in_url and min(years_in_url) > year:
                    return 0.0  # future year in URL

                if (year_str in url_lower
                        or any(p in url_lower for p in _fy_other)
                        or _fy_dash_match(url_lower, _fy_dash)):
                    year_score = 0.50  # year / FY variant match in URL
                elif years_in_url:
                    return 0.0  # wrong year confirmed — hard-reject
                # else: no year signal → year_score stays 0.00

        # ── SOURCE QUALITY (0.00 – 0.40) ──────────────────────────────────────
        source_score = 0.0
        if ir_url:
            try:
                ir_netloc = urlparse(ir_url).netloc.lower().lstrip("www.")
                url_netloc = urlparse(url).netloc.lower().lstrip("www.")
                if ir_netloc and (
                    ir_netloc in url_netloc or url_netloc.endswith(ir_netloc)
                ):
                    source_score = 0.40  # company's own IR domain
                elif is_trusted_exchange:
                    source_score = 0.20
                # aggregator or unknown → 0.00
            except Exception:
                source_score = 0.20 if is_trusted_exchange else 0.0
        elif is_trusted_exchange:
            source_score = 0.20
        # aggregator and other unknown sources → 0.00

        # ── LANGUAGE (0.00 – 0.15) ────────────────────────────────────────────
        if any(kw in url_lower for kw in _EN_URL_KW):
            language_score = 0.15
        elif any(kw in url_lower for kw in _NON_EN_URL_KW):
            language_score = 0.00  # non-English confirmed
        else:
            language_score = 0.05  # language neutral

        # ── Company name in URL (small bonus, never penalises) ────────────────
        name_words = [w for w in company_name.lower().split() if len(w) > 3]
        company_bonus = 0.05 if (name_words and any(w in url_lower for w in name_words)) else 0.0

        # ── Final score ────────────────────────────────────────────────────────
        return (
            doc_type_score + year_score + source_score
            + language_score + file_validity_score + company_bonus
        )

    except Exception:
        return 0.0


_LIVENESS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Exchange/regulator domains where HTTP 200 is sufficient proof of liveness —
# no PDF magic-byte check. SEC 10-K filings are iXBRL HTML (.htm), not PDFs.
TRUSTED_LIVENESS_DOMAINS = (
    "sec.gov", "sedar.com", "sgx.com", "bseindia.com", "nseindia.com",
)


async def check_url_alive(url: str) -> bool:
    """Verify a URL is reachable and serves a PDF (or valid investor document).

    HEAD-first (fast, no body). Falls back to a streaming GET that reads only
    the first 512 bytes and checks for the PDF magic bytes (%PDF-) when:
      - HEAD returns 405 (method not allowed), or
      - HEAD returns an HTML content-type (login wall / redirect).

    HTML files (.htm/.html) and trusted exchange domains skip the PDF magic
    check — HTTP 200 is sufficient for these sources.

    Returns False for 4xx errors, unreachable hosts, and non-PDF bodies.
    """
    try:
        _url_l = url.lower()
        _is_html_url = _url_l.endswith(('.htm', '.html'))
        _is_trusted_liveness = any(d in _url_l for d in TRUSTED_LIVENESS_DOMAINS)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10,
            verify=False,  # some IR sites have self-signed or expired certs
        ) as client:
            # ── HEAD (no body download) ────────────────────────────────────
            head_ok = False
            try:
                resp = await client.head(url, headers={"User-Agent": _LIVENESS_UA})
                if resp.status_code in (200, 403):
                    # Trusted domains (e.g. sec.gov) and HTML files: accept 200 or 403.
                    # 403 from sec.gov = bot-protection, file exists and is publicly accessible.
                    if _is_html_url or _is_trusted_liveness:
                        return True
                    ct = resp.headers.get("content-type", "").lower()
                    # HTML content-type on a "200" = login wall → confirm with GET
                    head_ok = not (ct and "html" in ct and "pdf" not in ct)
                elif resp.status_code == 405:
                    pass  # HEAD not allowed → fall through to GET
                else:
                    logging.debug("[liveness] HEAD %d → %s", resp.status_code, url)
                    return False
            except (httpx.TimeoutException, httpx.ConnectError,
                    httpx.RemoteProtocolError) as e:
                logging.debug("[liveness] HEAD failed (%s) → %s", type(e).__name__, url)
                return False

            if head_ok:
                return True

            # ── GET fallback: read first 512 bytes, check %PDF- magic ─────
            try:
                async with client.stream(
                    "GET", url, headers={"User-Agent": _LIVENESS_UA}
                ) as resp:
                    if resp.status_code != 200:
                        logging.debug("[liveness] GET %d → %s", resp.status_code, url)
                        return False

                    # HTML files and trusted domains: HTTP 200 is sufficient
                    if _is_html_url or _is_trusted_liveness:
                        return True

                    # Only run PDF magic-byte check for .pdf URLs or application/pdf
                    ct_get = resp.headers.get("content-type", "").lower()
                    _is_pdf_url = (
                        _url_l.rstrip("/").endswith(".pdf")
                        or "application/pdf" in ct_get
                    )
                    if not _is_pdf_url:
                        return True

                    chunk = b""
                    async for data in resp.aiter_bytes(chunk_size=512):
                        chunk = data
                        break
                    if not chunk.startswith(b"%PDF-"):
                        logging.debug("[liveness] not a PDF (bad magic bytes) → %s", url)
                        return False
                    return True
            except (httpx.TimeoutException, httpx.ConnectError,
                    httpx.RemoteProtocolError) as e:
                logging.debug("[liveness] GET failed (%s) → %s", type(e).__name__, url)
                return False

    except Exception as e:
        logging.debug("[liveness] unexpected error (%s) → %s", type(e).__name__, url)
        return False


if __name__ == "__main__":
    test_urls = [
        (
            "https://www.annualreports.com/HostedData/AnnualReports/PDF/NASDAQ_AAPL_2023.pdf",
            "Apple Inc", 2023, "annual_report",
        ),
        (
            "https://susrepsmain.blob.core.windows.net/srdp/files/48fc91/XNSE_KRISHANA_2024_AR1.pdf",
            "Krishana Phoschem", 2023, "annual_report",
        ),
        (
            "https://susrepsmain.blob.core.windows.net/srdp/files/48fc91/XNSE_KRISHANA_2023_AR1.pdf",
            "Krishana Phoschem", 2023, "annual_report",
        ),
        (
            "https://www.example.com/page.html",
            "Apple Inc", 2023, "annual_report",
        ),
        (
            "https://www.reliance.com/investors/annual-report-2023.pdf",
            "Reliance Industries", 2023, "annual_report",
        ),
        # Exchange quarterly that must score 0.0
        (
            "https://bseindia.com/xml-data/corpfiling/AttachLive/Q1-2024-quarterly-results.pdf",
            "Test Corp", 2024, "annual_report",
        ),
    ]

    async def main():
        for url, company, year, doc_type in test_urls:
            score = await validate_pdf(url, company, year, doc_type)
            print(f"Score: {score:.2f}  |  {url[:90]}")

    asyncio.run(main())
