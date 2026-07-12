"""
Universal web-search fallback source (Step 3).

Search chain (first that returns results wins):
  Tavily → Serper → Exa

For each result URL:
  • ends in .pdf  → candidate directly
  • HTML page     → BeautifulSoup scrape for PDF links
  • JS-rendered   → Firecrawl fallback (if BS4 finds < 500 chars of text)

All API calls use direct REST so no extra packages are required beyond requests.
"""

import logging
import os
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import Candidate

logger = logging.getLogger(__name__)

MAX_HTML_PAGES   = 5      # HTML pages to scrape per query
MAX_HTML_READ    = 200_000  # bytes to read from each HTML page
MAX_CANDIDATES   = 8

# [RANK-DIAG] candidate-ordering logging is a diagnostic, OFF by default. Enable by
# setting IDF_RANK_DIAG=1 (or true/yes/on) in the environment — so normal operation
# carries no extra per-query log line.
_RANK_DIAG = os.environ.get("IDF_RANK_DIAG", "").lower() in ("1", "true", "yes", "on")

# Third-party financial-data repositories that mirror annual reports. Two uses:
# (1) UK plcs frequently serve their own PDFs behind bot-blocking (HTTP 403); these
# hosts do not, so a scoped Exa query sidesteps the blocked issuer domain. (2) For
# the broader non-US/non-IN population, they add fallback breadth when the issuer's
# own site doesn't surface a verifiable report. Each entry was checked for
# fetchability before inclusion (Exa-scoped query → a real report PDF returns 200 +
# application/pdf); candidates that failed that check (reportjunction, last10k,
# marketscreener) were deliberately NOT added.
_THIRDPARTY_REPORT_DOMAINS = [
    "annualreports.com",
    "www.annualreports.com",
    "www.annualreports.co.uk",   # verified 2026-07-08: global reports, same archive operator as .com
    "responsibilityreports.com",
    "www.responsibilityreports.co.uk",
    "www.londonstockexchange.com",
    "www.investegate.co.uk",
]

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
}


class WebSearchSource:
    name = "web_search"

    def supports(self, intent: dict) -> bool:
        return True  # universal fallback

    def find_candidates(self, intent: dict) -> list[Candidate]:
        return find_web_candidates(intent)


def _urls_to_candidates(urls: list[str], kind: str = "WebSearch") -> list[Candidate]:
    """Build web_search Candidates from an ordered URL list, capped at MAX_CANDIDATES.

    Exact-URL dedup: a search API (or an HTML page's links) can surface the same URL
    more than once; fetching/verifying it twice wastes a full attempt. Match is EXACT
    URL only — near-duplicates (same file at different URLs, e.g. distinct S3 version
    paths) are intentionally NOT collapsed here (separate scope).
    """
    candidates: list[Candidate] = []
    seen_urls: set[str] = set()
    pages_scraped = 0

    for url in urls:
        if len(candidates) >= MAX_CANDIDATES:
            break
        if url in seen_urls:
            continue
        if _is_pdf_url(url):
            seen_urls.add(url)
            candidates.append(Candidate(url=url, source="web_search",
                                        note=f"Direct PDF from search: {url[:80]}"))
            continue
        if pages_scraped < MAX_HTML_PAGES:
            seen_urls.add(url)   # mark the HTML page so a repeat isn't re-scraped
            for pdf_url in _scrape_pdf_links(url)[:3]:
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)
                candidates.append(Candidate(url=pdf_url, source="web_search",
                                            note=f"PDF scraped from {url[:60]}"))
            pages_scraped += 1

    logger.info(f"{kind}: {len(candidates)} candidate(s)")
    # [RANK-DIAG] candidate-ordering trace — gated behind IDF_RANK_DIAG (off by
    # default) so normal operation carries no extra per-query log line. Logging only.
    if _RANK_DIAG:
        for _pos, _cand in enumerate(candidates, 1):
            logger.info(f"[RANK-DIAG] {kind} candidate {_pos}/{len(candidates)}: {_cand.get('url', '')}")
    return candidates


def find_web_candidates(intent: dict) -> list[Candidate]:
    """Primary web_search source.

    For UK-listed issuers, third-party report mirrors are tried FIRST (prepended)
    because the issuer's own domain bot-blocks (HTTP 403) — the Fix-4 behaviour,
    unchanged. For every other country the mirror query is NOT run here; it is deferred
    to the lazy ``web_search_mirror`` source (find_web_mirror_candidates), which the
    agent fires only if this primary yields no verified candidate — avoiding the mirror
    Exa call (and its latency) for companies that already resolve cleanly.
    """
    query = _build_query(intent)
    logger.info(f"WebSearch: {query!r}")

    urls = _search(query, intent.get("country"))

    if _is_uk_listed(intent):
        tp_new = [u for u in _exa_thirdparty(query) if u not in set(urls)]
        if tp_new:
            logger.info(f"WebSearch: UK path — {len(tp_new)} third-party URL(s) tried FIRST")
            urls = tp_new + urls
        else:
            logger.info("WebSearch: UK path — third-party query returned nothing new")

    if not urls:
        logger.warning("WebSearch: all search APIs returned no results")
        return []

    return _urls_to_candidates(urls, kind="WebSearch")


def find_web_mirror_candidates(intent: dict) -> list[Candidate]:
    """Lazy fallback source (``web_search_mirror``): the scoped third-party report-mirror
    query ONLY. The agent fires this after the primary web_search and only when nothing
    verified, so companies that already resolve cleanly pay no mirror-query cost. No-op
    for UK (its mirrors are already tried first inside find_web_candidates) and for US/IN
    (never routed here).
    """
    if _is_uk_listed(intent) or not _wants_thirdparty(intent):
        return []
    query = _build_query(intent)
    urls = _exa_thirdparty(query)
    if not urls:
        logger.info("WebSearch/mirror: third-party mirror query returned nothing")
        return []
    logger.info(f"WebSearch/mirror: {len(urls)} third-party mirror URL(s) as fallback")
    return _urls_to_candidates(urls, kind="WebSearch/mirror")


# ── query builder ─────────────────────────────────────────────────────────────

def _build_query(intent: dict) -> str:
    company = intent.get("company_name", "")
    year    = intent.get("fiscal_year", "")
    country = (intent.get("country") or "").upper()

    if country == "IN":
        fy_candidates = intent.get("fy_candidates", [])
        fy_str = " OR ".join(f'"{f}"' for f in fy_candidates) if fy_candidates else str(year)
        return f'"{company}" ({fy_str}) "annual report" filetype:pdf'

    # US / global
    return f'"{company}" {year} annual report filetype:pdf'


# ── search API cascade ────────────────────────────────────────────────────────

def _search(query: str, country: str | None = None) -> list[str]:
    # Country-aware provider order. Tavily indexes US/IN corporate & regulatory
    # sites well; Exa's neural search tends to have better coverage for the rest
    # of the world, so it leads for global/unknown-country queries.
    c = (country or "").upper()
    if c in ("US", "IN"):
        order = (_tavily, _serper, _exa)
    else:
        order = (_exa, _serper, _tavily)
    for fn in order:
        urls = fn(query)
        if urls:
            return urls
    return []


def _tavily(query: str) -> list[str]:
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 10,
                "include_raw_content": False,
                "include_answer": False,
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        logger.info(f"WebSearch/Tavily: {len(results)} results")
        return [r["url"] for r in results]
    except Exception as exc:
        logger.warning(f"Tavily failed: {exc}")
        return []


def _serper(query: str) -> list[str]:
    key = os.environ.get("SERPER_API_KEY", "")
    if not key or key.startswith("your_"):
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": 10},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("organic", [])
        logger.info(f"WebSearch/Serper: {len(results)} results")
        return [r["link"] for r in results]
    except Exception as exc:
        logger.warning(f"Serper failed: {exc}")
        return []


def _exa(query: str) -> list[str]:
    key = os.environ.get("EXA_API_KEY", "")
    if not key:
        return []
    try:
        resp = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={"query": query, "numResults": 10},
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        logger.info(f"WebSearch/Exa: {len(results)} results")
        return [r["url"] for r in results]
    except Exception as exc:
        logger.warning(f"Exa failed: {exc}")
        return []


def _is_uk_listed(intent: dict) -> bool:
    """UK-listed heuristic. Prefers the resolved country code, but also catches
    a "plc" suffix so a degraded intent parse (no country) still routes here."""
    if (intent.get("country") or "").upper() in ("GB", "UK"):
        return True
    name = f"{intent.get('company_name', '')} {intent.get('raw_company', '')}".lower()
    return bool(re.search(r"\bplc\b", name))


def _wants_thirdparty(intent: dict) -> bool:
    """Whether to run the scoped third-party report-mirror query. Applies to the
    non-US/non-IN population that flows through web_search as its primary source
    (US routes to edgar, IN to the India chain). Unknown-country queries also flow
    through web_search, so they qualify too. (UK is a subset — it additionally gets
    prepend-first ordering via _is_uk_listed at the call site.)"""
    return (intent.get("country") or "").upper() not in ("US", "IN")


def _exa_thirdparty(query: str) -> list[str]:
    """Exa query restricted to third-party report repositories (includeDomains),
    i.e. explicitly NOT the company's own site — so a bot-blocked issuer domain
    can't hide an otherwise-available report. Same timeout as the primary Exa
    call: the issue is blocking, not latency, so we do not extend it."""
    key = os.environ.get("EXA_API_KEY", "")
    if not key:
        return []
    try:
        resp = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": 10,
                "includeDomains": _THIRDPARTY_REPORT_DOMAINS,
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        logger.info(f"WebSearch/Exa(third-party): {len(results)} results")
        return [r["url"] for r in results]
    except Exception as exc:
        logger.warning(f"Exa third-party query failed: {exc}")
        return []


# ── PDF extraction ────────────────────────────────────────────────────────────

def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _scrape_pdf_links(url: str) -> list[str]:
    """Fetch an HTML page; return PDF hrefs found. Falls back to Firecrawl."""
    try:
        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=15, stream=True)
        if resp.status_code == 403:
            # Blocked, NOT missing — the page exists but the host is refusing our
            # request (bot filtering). Logged distinctly from a 404 so a blocked
            # source isn't mistaken for an absent document.
            resp.close()
            logger.warning(
                f"WebSearch: source blocked (HTTP 403, not missing): "
                f"{urlparse(url).netloc}{urlparse(url).path[:60]}"
            )
            return []
        if resp.status_code != 200:
            resp.close()
            return []
        if "text/html" not in resp.headers.get("content-type", ""):
            resp.close()
            return []
        chunk = b""
        for c in resp.iter_content(8192):
            chunk += c
            if len(chunk) >= MAX_HTML_READ:
                break
        resp.close()
    except Exception as exc:
        logger.debug(f"WebSearch: fetch failed for {url}: {exc}")
        return []

    soup = BeautifulSoup(chunk, "html.parser")
    page_text = soup.get_text()

    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#"):
            continue
        abs_url = urljoin(url, href)
        if _is_pdf_url(abs_url):
            links.append(abs_url)

    # Firecrawl fallback for JS-rendered pages
    if not links and len(page_text) < 500:
        logger.info(f"WebSearch: JS page detected, trying Firecrawl: {url}")
        links = _firecrawl(url)

    logger.debug(f"WebSearch: {len(links)} PDF link(s) on {url}")
    return links[:5]


def _firecrawl(url: str) -> list[str]:
    key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not key:
        return []
    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["links"]},
            timeout=30,
        )
        if not resp.ok:
            logger.warning(f"Firecrawl {resp.status_code} for {url}")
            return []
        links = resp.json().get("data", {}).get("links", [])
        return [l for l in links if _is_pdf_url(l)]
    except Exception as exc:
        logger.warning(f"Firecrawl failed for {url}: {exc}")
        return []
