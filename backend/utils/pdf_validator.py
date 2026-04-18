"""
PDF Validator — scores a URL for likelihood of being the target investor document.

Input:  url (str), company_name (str), year (int), doc_type (str)
Output: float score between 0.0 and 1.0
"""

import asyncio
import re

import httpx

MIN_SIZE = 100 * 1024       # 100 KB
MAX_SIZE = 50 * 1024 * 1024  # 50 MB

YEAR_PATTERN = re.compile(r'(?:19|20)\d{2}')  # matches 1900–2099

# NSE annual report URL contains explicit FY range: annual_reports/AR_{id}_{ticker}_{from}_{to}_
# e.g. AR_25168_KRISHANA_2022_2023_27082024... → FY ending 2023
_NSE_AR_RE = re.compile(r'annual_reports/ar_\d+_[^/]+?_(\d{4})_(\d{4})_')

# Official exchange domains — their opaque CDN/download URLs are given a floor score
TRUSTED_EXCHANGE_DOMAINS = (
    "bseindia.com", "nseindia.com", "archives.nseindia.com",
    "nsearchives.nseindia.com", "kap.org.tr",
    "dfm.ae", "feeds.dfm.ae", "adx.ae", "apigateway.adx.ae",
    "saudiexchange.sa", "bursamalaysia.com", "sgx.com",
    "set.or.th", "jse.co.za", "ngxgroup.com", "stockex.co.tt", "jamstockex.com",
)

PRESS_RELEASE_KEYWORDS = (
    "press_release", "press-release", "pressrelease",
    "media-release", "media_release", "mediarelease",
    "news-release", "news_release", "newsrelease",
    "press/release", "media/release", "news/release",
    "/media/", "/news/", "/announcement",
    "credit_rating", "credit-rating", "creditrating",
)

# Substrings that identify credit rating / non-annual-report sources — always hard-reject.
# Kept as bare name keywords (no TLD) so they catch blob storage CDN variants like
# "infomericstorage.blob.core.windows.net/..." as well as the primary domain.
REJECT_DOMAINS = (
    "careratings", "crisil", "icra.in", "icra.com",
    "infomerics", "acuite", "brickworkratings",
    "india-ratings", "moodys.com", "spglobal.com", "fitchratings",
)

ANNUAL_KEYWORDS = ("annual", "annual-report", "annual_report", "ar20", "annualreport",
                   "integrated-report", "integrated_report", "annual-review", "annual_review")
QUARTERLY_KEYWORDS = ("quarterly", "quarter", "q1", "q2", "q3", "q4", "10-q")

# FIX 2: URL-level doc type rejection for annual_report searches
_ANNUAL_REJECT_URL_KW = (
    "quarter", "q1", "q2", "q3", "q4", "q5", "interim",
    "half-year", "halfyear", "_h1_", "_h2_", "-h1-", "-h2-",
    "financial-statement", "financial_statement",
    "governance", "sustainability",
)

# FIX 4: language scoring signals
_EN_URL_KW = ("english", "_en_", "-en-", "_en.", "-en.", "eng_", "_eng", "english-version")
_NON_EN_URL_KW = (
    "arabic", "_ar_", "_ar.", "-ar-", "عربي", "uzbek", "_uz_", "russian", "_ru_", "_ru.",
    "turkish", "_tr_", "_tr.", "chinese", "_cn_", "french", "_fr_", "german", "_de_",
)


async def validate_pdf(url: str, company_name: str, year: int, doc_type: str) -> float:
    """Score a URL from 0.0–1.0 based on how likely it is the target PDF."""
    try:
        url_lower = url.lower()

        # --- Hard-reject domains (credit rating agencies etc.) ---
        if any(domain in url_lower for domain in REJECT_DOMAINS):
            return 0.0

        # --- Press release check ---
        is_press_release = any(kw in url_lower for kw in PRESS_RELEASE_KEYWORDS)
        if is_press_release:
            # Hard reject only when explicitly a press release with no annual/report context
            if "press_release" in url_lower and not any(kw in url_lower for kw in ("annual", "report")):
                return 0.0

        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.head(url, timeout=8)

        content_type = resp.headers.get("content-type", "").lower()
        score = 0.0

        # --- NSE fiscal year range check (must come before general year check) ---
        # NSE annual report URLs encode the exact FY as:
        #   annual_reports/AR_{id}_{ticker}_{fy_start}_{fy_end}_{timestamp}.pdf
        # e.g. AR_25168_KRISHANA_2022_2023_... → FY ending 2023
        #      AR_25168_KRISHANA_2023_2024_... → FY ending 2024 (NOT a 2023 report)
        nse_m = _NSE_AR_RE.search(url_lower)
        skip_general_year_check = False
        if nse_m:
            fy_end = int(nse_m.group(2))
            if fy_end == year:
                score += 0.2   # exact FY match bonus (same as general year-in-URL)
                skip_general_year_check = True
            elif fy_end > year:
                return 0.0     # FY ends after requested year → wrong report
            else:
                skip_general_year_check = True  # older FY → neutral

        # --- PDF detection (gate) ---
        is_trusted_exchange = any(d in url_lower for d in TRUSTED_EXCHANGE_DOMAINS)
        if "pdf" in content_type:
            score += 0.4
        elif url_lower.rstrip("/").endswith(".pdf"):
            score += 0.2
        elif is_trusted_exchange:
            # Trusted exchange CDN/download URLs often lack .pdf extension but are real PDFs
            score += 0.3
        else:
            return 0.0

        # --- Press release soft penalty ---
        if is_press_release:
            score -= 0.2

        # --- FIX 2: URL-level doc-type rejection (annual_report searches only) ---
        if doc_type == "annual_report" and not is_trusted_exchange:
            if any(kw in url_lower for kw in _ANNUAL_REJECT_URL_KW):
                return 0.0

        # --- FIX 3: Year in URL — strict scoring with FY variants ---
        if not skip_general_year_check:
            year_str = str(year)
            prev_year = str(year - 1)
            yr2 = year_str[2:]
            prev_yr2 = prev_year[2:]
            next_year = str(year + 1)
            next_yr2 = next_year[2:]

            # FY variant patterns
            fy_variants = [
                f"fy{year_str}", f"fy{yr2}",
                f"{prev_year}-{yr2}", f"{prev_year}-{year_str}",
                f"{year_str}-{next_yr2}", f"{year_str}-{next_year}",
            ]

            years_in_url = [int(y) for y in YEAR_PATTERN.findall(url)]
            if years_in_url and min(years_in_url) > year:
                return 0.0

            if year_str in url_lower or any(p in url_lower for p in fy_variants):
                score += 0.30   # FIX 3: exact match bonus (was 0.20)
            elif prev_year in url_lower or f"fy{prev_yr2}" in url_lower:
                score -= 0.20   # FIX 3: prior year penalty
            elif not years_in_url:
                score -= 0.10   # FIX 3: no year found penalty
        # (NSE paths already handled above — skip_general_year_check=True)

        # --- Content-Length check ---
        length = resp.headers.get("content-length")
        if length and length.isdigit():
            size = int(length)
            if MIN_SIZE <= size <= MAX_SIZE:
                score += 0.2

        # --- Company name words in URL (bonus only, never reject) ---
        words = [w for w in company_name.lower().split() if len(w) > 3]
        if words and any(w in url_lower for w in words):
            score += 0.2

        # --- Doc-type keyword bonus ---
        if doc_type == "annual_report" and any(kw in url_lower for kw in ANNUAL_KEYWORDS):
            score += 0.3
        elif doc_type == "quarterly_report" and any(kw in url_lower for kw in QUARTERLY_KEYWORDS):
            score += 0.3

        # --- FIX 4: Language scoring ---
        if any(kw in url_lower for kw in _EN_URL_KW):
            score += 0.15
        elif any(kw in url_lower for kw in _NON_EN_URL_KW):
            score -= 0.10

        score = min(max(score, 0.0), 1.0)
        return score

    except Exception:
        return 0.0


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
    ]

    async def main():
        for url, company, year, doc_type in test_urls:
            score = await validate_pdf(url, company, year, doc_type)
            print(f"Score: {score:.2f}  |  {url[:80]}")

    asyncio.run(main())
