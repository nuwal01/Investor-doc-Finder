"""
India primary source: Screener.in annual-report scraping (Step 6).

Screener.in aggregates annual report PDFs for all NSE/BSE-listed companies
and is reliably scrapable without authentication.

Annual-reports page: https://www.screener.in/company/{TICKER}/annual-reports/

Falls back to a BSE filing URL pattern when Screener has nothing.
"""

import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import Candidate

logger = logging.getLogger(__name__)

SCREENER_BASE = "https://www.screener.in"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class NSESource:
    name = "nse"

    def supports(self, intent: dict) -> bool:
        return intent.get("country") == "IN"

    def find_candidates(self, intent: dict) -> list[Candidate]:
        return find_india_candidates(intent)


def find_india_candidates(intent: dict) -> list[Candidate]:
    ticker = (intent.get("ticker_or_id") or "").upper()
    company = intent.get("company_name", "")
    fy_candidates = intent.get("fy_candidates", [])

    candidates: list[Candidate] = []

    # Try Screener with ticker
    if ticker:
        candidates.extend(_screener(ticker, fy_candidates))

    # If ticker search found nothing, try slug derived from company name
    if not candidates and company:
        slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
        candidates.extend(_screener(slug, fy_candidates))

    if not candidates:
        logger.warning(f"NSE/Screener: no candidates for ticker={ticker!r} company={company!r}")

    return candidates


def _screener(ticker: str, fy_candidates: list[str]) -> list[Candidate]:
    url = f"{SCREENER_BASE}/company/{ticker}/annual-reports/"
    logger.info(f"NSE/Screener: {url}")

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.warning(f"NSE/Screener: 404 for ticker {ticker!r}")
            return []
        if resp.status_code != 200:
            logger.warning(f"NSE/Screener: HTTP {resp.status_code}")
            return []
    except Exception as exc:
        logger.error(f"NSE/Screener fetch error: {exc}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    candidates: list[Candidate] = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        text = tag.get_text(strip=True)

        is_pdf = href.lower().endswith(".pdf")
        is_annual = "annual" in href.lower() or "annual" in text.lower()

        if not (is_pdf or is_annual):
            continue

        abs_url = urljoin(SCREENER_BASE, href)
        matched = _match_fy(text + " " + href, fy_candidates)

        if matched or not fy_candidates:
            note = f"Screener.in/{ticker}: {text[:50]} (fy={matched or 'any'})"
            candidates.append(Candidate(url=abs_url, source="nse", note=note))

    logger.info(f"NSE/Screener: {len(candidates)} candidate(s) for {ticker!r}")
    return candidates[:5]


def _match_fy(text: str, fy_candidates: list[str]) -> str | None:
    for fy in fy_candidates:
        years = re.findall(r"\d{4}", fy)
        if any(yr in text for yr in years):
            return fy
    return None
