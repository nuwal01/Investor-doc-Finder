"""
India secondary source: aggregator (Step 6).

Two modes — chosen automatically based on whether resolver found a stock_discovery_id:

  1. Direct S3 URLs (preferred):
     When resolver sets intent["stock_discovery_id"], we construct the exact
     StockDiscovery S3 PDF URLs and return them — no web search needed.
     URL pattern:
       https://stockdiscovery.s3.amazonaws.com/insight/india/{ID}/Annual%20Report/AR-{YY}.pdf
     where YY is the 2-digit ending year extracted from each fy_candidate label
     (e.g. "FY2020-21" -> "21", "FY2021-22" -> "22").

  2. Tavily search fallback:
     When stock_discovery_id is unavailable, fall back to the original Tavily
     web search filtered to bseindia.com / nseindia.com / screener.in.
     This is kept intact so no coverage is lost.
"""

import logging
import re

from .base import Candidate

logger = logging.getLogger(__name__)

_SD_BASE = "https://stockdiscovery.s3.amazonaws.com/insight/india"

_INDIA_DOMAINS = (
    "site:bseindia.com",
    "site:nseindia.com",
    "site:screener.in",
    "site:moneycontrol.com",
    "site:sebi.gov.in",
)


class AggregatorsSource:
    name = "aggregators"

    def supports(self, intent: dict) -> bool:
        return intent.get("country") == "IN"

    def find_candidates(self, intent: dict) -> list[Candidate]:
        return find_aggregator_candidates(intent)


def find_aggregator_candidates(intent: dict) -> list[Candidate]:
    sd_id = intent.get("stock_discovery_id")
    if sd_id:
        return _direct_sd_candidates(sd_id, intent)
    return _tavily_candidates(intent)


# ── Mode 1: StockDiscovery direct S3 URLs ─────────────────────────────────────

def _direct_sd_candidates(sd_id: str, intent: dict) -> list[Candidate]:
    """Build deterministic StockDiscovery S3 URLs — no search API call needed."""
    fy_candidates = intent.get("fy_candidates", [])
    candidates: list[Candidate] = []

    for fy in fy_candidates:
        suffix = _fy_to_ar_suffix(fy)
        if not suffix:
            continue
        url = f"{_SD_BASE}/{sd_id}/Annual%20Report/AR-{suffix}.pdf"
        candidates.append({
            **Candidate(url=url, source="aggregators",
                        note=f"StockDiscovery direct: id={sd_id} {fy}"),
            "skip_company_check": True,
        })
        logger.info(f"Aggregators: StockDiscovery direct -> {url}")

    logger.info(f"Aggregators: {len(candidates)} StockDiscovery candidate(s)")
    return candidates


def _fy_to_ar_suffix(fy: str) -> str | None:
    """
    Extract the 2-digit ending year from an FY label.

    'FY2020-21' -> '21'
    'FY2021-22' -> '22'
    '2022'      -> '22'
    """
    m = re.search(r'FY\d{4}-(\d{2})', fy)
    if m:
        return m.group(1)
    m = re.search(r'(\d{4})', fy)
    if m:
        return m.group(1)[2:]
    return None


# ── Mode 2: Tavily search fallback ────────────────────────────────────────────

def _tavily_candidates(intent: dict) -> list[Candidate]:
    """Original Tavily search approach — used when stock_discovery_id is unknown."""
    company       = intent.get("company_name", "")
    fy_candidates = intent.get("fy_candidates", [])
    fiscal_year   = intent.get("fiscal_year", "")

    fy_str        = " OR ".join(f'"{f}"' for f in fy_candidates) if fy_candidates else str(fiscal_year)
    domain_clause = " OR ".join(_INDIA_DOMAINS[:3])
    query = f'"{company}" ({fy_str}) "annual report" filetype:pdf ({domain_clause})'

    logger.info(f"Aggregators/Tavily: {query!r}")

    from .web_search import _search, _scrape_pdf_links, _is_pdf_url

    urls = _search(query, intent.get("country"))
    candidates: list[Candidate] = []

    for url in urls[:6]:
        if _is_pdf_url(url):
            candidates.append(Candidate(
                url=url,
                source="aggregators",
                note=f"India PDF from aggregator search: {url[:70]}",
            ))
        else:
            for pdf_url in _scrape_pdf_links(url)[:2]:
                candidates.append(Candidate(
                    url=pdf_url,
                    source="aggregators",
                    note=f"India PDF scraped from {url[:55]}",
                ))

    logger.info(f"Aggregators: {len(candidates)} candidate(s)")
    return candidates
