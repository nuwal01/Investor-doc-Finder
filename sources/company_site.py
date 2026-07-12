"""
India primary source: the company's own investor-relations site (Step 6).

Guessing a domain by string-munging the name is unreliable, so instead we run
a web search scoped (via site: filters) to the company's most likely official
domains — {slug}.co.in and {slug}.com — where the slug is built from the
distinctive tokens of the company name.  This gives the company's own IR page
a real shot at producing the authoritative PDF before we fall back to the
generic aggregator / web-search sources.

Slot order in agent.py's IN chain:  nse → company_site → aggregators → web_search
"""

import logging
import re
from urllib.parse import urlparse

from .base import Candidate

logger = logging.getLogger(__name__)

# Corporate suffix / filler words that never belong in a domain slug.
_SLUG_STOPWORDS: frozenset[str] = frozenset({
    "india", "limited", "ltd", "private", "pvt", "company", "co",
    "inc", "corp", "corporation", "group", "industries", "industry",
    "international", "national", "the", "and",
})

_MAX_URLS = 6
_MAX_CANDIDATES = 8   # bound per-source verify cost against the 45s wall-clock budget


class CompanySiteSource:
    name = "company_site"

    def supports(self, intent: dict) -> bool:
        return intent.get("country") == "IN"

    def find_candidates(self, intent: dict) -> list[Candidate]:
        return find_company_site_candidates(intent)


def find_company_site_candidates(intent: dict) -> list[Candidate]:
    company = intent.get("company_name", "")
    slug = _domain_slug(company)
    if not slug:
        logger.info("CompanySite: no usable domain slug from company name — skipping")
        return []

    # Narrow by bare 4-digit years (NOT the quoted "FY2020-21" labels) so we keep
    # precision without an exact-phrase requirement that documents — titled
    # "Annual Report 2020-21" — would never satisfy.  verify.py re-checks the year.
    years = sorted({y for f in intent.get("fy_candidates", []) for y in re.findall(r"\d{4}", f)})
    year_clause = f" ({' OR '.join(years)})" if years else ""

    # Scope the search to the company's likely official domains.
    query = (
        f'"{company}"{year_clause} site:{slug}.co.in OR site:{slug}.com '
        f'annual report filetype:pdf'
    )
    logger.info(f"CompanySite: {query!r}")

    # Reuse the web_search module's search + scrape stack.
    from .web_search import _search, _scrape_pdf_links, _is_pdf_url

    # company_site only runs for India, so force the IN provider order
    # (Tavily-first) rather than the global Exa-first default.
    urls = _search(query, country="IN")
    candidates: list[Candidate] = []

    for url in urls[:_MAX_URLS]:
        if len(candidates) >= _MAX_CANDIDATES:
            break
        # Tavily/Exa do not strictly honour the site: operator, so results can
        # leak off-domain (e.g. a subsidiary's report on a different host that
        # still contains the parent's name tokens).  This source's whole point is
        # the company's OWN site, so enforce the guessed domain ourselves.
        if _is_pdf_url(url):
            if not _on_company_domain(url, slug):
                continue
            candidates.append(Candidate(
                url=url, source="company_site",
                note=f"Company-site PDF: {url[:70]}",
            ))
        elif _on_company_domain(url, slug):
            for pdf_url in _scrape_pdf_links(url)[:2]:
                if not _on_company_domain(pdf_url, slug):
                    continue
                candidates.append(Candidate(
                    url=pdf_url, source="company_site",
                    note=f"Company-site PDF scraped from {url[:55]}",
                ))

    logger.info(f"CompanySite: {len(candidates)} candidate(s)")
    return candidates


def _on_company_domain(url: str, slug: str) -> bool:
    """True if the URL's host belongs to the guessed company domain.

    Accepts the slug as a host label anywhere in the netloc so subdomains pass:
    'tatamotors' matches tatamotors.com, www.tatamotors.com, investors.tatamotors.co.in.
    Rejects unrelated hosts like tatacapital.com that Tavily may return despite a
    site: filter.
    """
    host = urlparse(url).netloc.lower()
    return slug in host.replace("-", "")


def _domain_slug(company: str) -> str:
    """
    Build a likely domain slug by dropping corporate filler words and joining
    the distinctive tokens.

      'Arfin India Limited' -> 'arfin'      (arfin.co.in)
      'Tata Motors'         -> 'tatamotors' (tatamotors.com)
    """
    tokens = re.findall(r"[a-z0-9]+", company.lower())
    distinctive = [t for t in tokens if t not in _SLUG_STOPWORDS]
    if not distinctive:
        # Name is entirely corporate filler ("The India Company Limited") — no
        # reliable slug.  Return "" so the caller skips this source rather than
        # issuing a guaranteed-bogus site:-scoped search and burning API quota.
        return ""
    return "".join(distinctive)
