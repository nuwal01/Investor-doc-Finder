"""
Company name / ticker -> per-source IDs.

Resolution order for US and other non-Indian companies (foreign private
issuers with a US listing — ASML, Shopify, Turkcell ADRs — appear in EDGAR's
ticker file and file 20-F/40-F, so the CIK lookup runs for every non-IN
country; a miss just leaves the web_search chain unchanged):
  1. data/company_map.csv   — exact ticker or canonical name match (fast, no network)
  2. EDGAR company_tickers.json — full EDGAR filer list; cached 24 h locally
     - exact ticker match
     - exact title match (case-insensitive)
     - suffix-stripped title match ("Apple" == "Apple Inc.", "ASML Holding" == "ASML HOLDING NV")
     - best-scoring word-boundary substring match (must cover ≥ 50 % of entry title)

India resolution:
  1. data/company_map.csv   — stock_discovery_id column (seeded + runtime cache)
  2. Scrape stockdiscovery.in/search — extracts integer company ID from first result
     Caches newly found IDs back to company_map.csv.
  3. None — callers fall back to Tavily search.

Ambiguity guard:
  If company_name is ≤ 3 characters AND no ticker AND no country, the intent is
  too vague to resolve. We set intent["_give_up_reason"] and return immediately
  so the agent skips all sources and gives up cleanly.
"""

import csv
import json
import logging
import re
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DATA_DIR    = Path(__file__).parent / "data"
COMPANY_MAP = DATA_DIR / "company_map.csv"
TICKERS_CACHE = DATA_DIR / "edgar_tickers.json"
TICKERS_URL   = "https://www.sec.gov/files/company_tickers.json"
CACHE_TTL     = 86_400  # 24 hours

EDGAR_HEADERS = {"User-Agent": "IDF research trade@ostwal.in"}
_SD_SCRAPE_TIMEOUT = 5   # seconds; kept tight so it doesn't eat into the wall-clock budget


def resolve(intent: dict) -> dict:
    """Enrich intent dict with CIK (US) or stock_discovery_id (IN). Returns a copy."""
    intent = dict(intent)

    # ── Raw-token override ───────────────────────────────────────────────────────
    # Runs BEFORE any LLM-parsed-name resolution (and before the ambiguity guard)
    # so a known ticker/abbreviation is never lost to an LLM misparse. The LLM
    # sometimes rewrites an unfamiliar abbreviation into a similarly-spelled
    # well-known company ("mbapl" → "Mphasis"); an exact hit on the CSV ticker
    # column against the raw user input overrides that and wires up the IDs.
    override = _raw_token_override(intent)
    if override is not None:
        return override

    company = intent.get("company_name", "")
    ticker  = intent.get("ticker_or_id", "") or ""
    country = (intent.get("country") or "").upper()

    # ── Ambiguity guard ────────────────────────────────────────────────────────
    # A company name of ≤ 3 characters with no ticker and no country is almost
    # certainly a nonsense or test query ("xyz"). Don't waste 45 s on it.
    if len(company) <= 3 and not ticker and not country:
        intent["_give_up_reason"] = "company name too ambiguous to resolve"
        logger.warning(
            f"Resolver: {company!r} is ≤3 chars with no ticker/country "
            "— marking for early give_up"
        )
        return intent

    if intent.get("cik"):
        logger.info(f"Resolver: CIK already present ({intent['cik']}), skipping lookup")
        return intent

    if country == "IN":
        sd_id = _resolve_india(company, ticker)
        if sd_id:
            intent["stock_discovery_id"] = sd_id
            logger.info(f"Resolver: stock_discovery_id={sd_id} for {company!r}")
        else:
            logger.warning(f"Resolver: could not resolve stock_discovery_id for {company!r}")

    else:
        # US, unknown, or any other country. Foreign private issuers with a
        # US listing (ASML, Shopify, Turkcell ADRs) are in EDGAR's ticker
        # file and file 20-F/40-F, so the CIK lookup is worth attempting for
        # every non-Indian company; a resolved CIK routes the agent through
        # the edgar source, a miss leaves the web_search chain unchanged.
        cik = _resolve_us(company, ticker)
        if cik:
            intent["cik"] = cik
            logger.info(f"Resolver: CIK={cik} for {company!r} (country={country or 'unknown'})")
        else:
            logger.warning(f"Resolver: could not resolve CIK for {company!r} / ticker={ticker!r}")

    return intent


# ── Raw-token override ──────────────────────────────────────────────────────────

# Query words that must never be treated as a ticker candidate. Punctuation is
# stripped before comparison, so "10-K" arrives here as "10K".
_RAW_TOKEN_NOISE = frozenset({
    "ANNUAL", "REPORT", "REPORTS", "FILING", "FILINGS", "10K", "10Q", "20F", "40F",
    "ANNUALREPORT", "FY", "AR", "THE", "AND", "FOR", "OF",
})


def _raw_token_override(intent: dict) -> dict | None:
    """
    Guard against the LLM rewriting an unfamiliar ticker/abbreviation into a
    similarly-spelled well-known company (e.g. "mbapl" -> "Mphasis").

    Extracts candidate tokens from the untouched user input (``raw_company``,
    plus any parsed ``ticker_or_id``), normalises them (strip punctuation,
    uppercase) and exact-matches them against company_map.csv's ticker column
    BEFORE any LLM-parsed-name resolution. On a hit the row's canonical name
    and every known ID (CIK / stock_discovery_id) override the LLM parse and
    the enriched intent is returned so the caller can short-circuit.

    Returns None when no raw token matches a known ticker.
    """
    if not COMPANY_MAP.exists():
        return None

    raw = intent.get("raw_company") or ""
    pieces = raw.split() + [intent.get("ticker_or_id") or ""]
    tokens: set[str] = set()
    for piece in pieces:
        norm = re.sub(r"[^A-Za-z0-9]", "", piece).upper()
        if norm and not norm.isdigit() and norm not in _RAW_TOKEN_NOISE:
            tokens.add(norm)
    if not tokens:
        return None

    with open(COMPANY_MAP, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row_ticker = (row.get("ticker") or "").strip().upper()
            if not row_ticker or row_ticker not in tokens:
                continue

            canonical = (row.get("canonical_name") or row.get("company_name") or "").strip()
            llm_name  = intent.get("company_name", "")
            logger.info(
                f"raw-token match: {row_ticker!r} → {canonical!r} "
                f"(overriding LLM parse {llm_name!r})"
            )

            out = dict(intent)
            out["company_name"] = canonical or llm_name
            out["ticker_or_id"] = row_ticker

            row_country = (row.get("country") or "").strip().upper()
            if row_country and row_country != (intent.get("country") or "").upper():
                out["country"] = row_country
                # fy_candidates was computed by intent.py from the OLD country;
                # recompute so IN/US fiscal-year expansion stays consistent.
                try:
                    from intent import _fy_candidates
                    out["fy_candidates"] = _fy_candidates(out.get("fiscal_year"), row_country)
                except Exception as exc:  # pragma: no cover — defensive only
                    logger.debug(f"Resolver: fy_candidates recompute skipped: {exc}")
            elif row_country:
                out["country"] = row_country

            cik = (row.get("cik") or "").strip()
            if cik:
                out["cik"] = _pad(cik)
            sd_id = (row.get("stock_discovery_id") or "").strip()
            if sd_id:
                out["stock_discovery_id"] = sd_id

            return out

    return None


# ── India resolution ──────────────────────────────────────────────────────────

def _resolve_india(company: str, ticker: str) -> str | None:
    """Return stock_discovery_id for an Indian company, or None if not found."""
    sd_id = _sd_csv_lookup(company, ticker)
    if sd_id:
        logger.info(f"Resolver: stock_discovery_id={sd_id} from CSV for {company!r}")
        return sd_id

    # Dynamic: scrape stockdiscovery.in
    query = ticker if ticker else company
    sd_id = _scrape_stock_discovery(query)
    if sd_id:
        _cache_sd_id(company, ticker, sd_id)
    return sd_id


def _sd_csv_lookup(company: str, ticker: str) -> str | None:
    """Return stock_discovery_id from company_map.csv if present."""
    if not COMPANY_MAP.exists():
        return None
    cn_lower = company.lower()
    tk_upper = ticker.upper()
    with open(COMPANY_MAP, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sd_id = row.get("stock_discovery_id", "").strip()
            if not sd_id:
                continue
            row_ticker    = row.get("ticker", "").upper()
            row_name      = row.get("company_name", "").lower()
            row_canonical = row.get("canonical_name", "").lower()
            if tk_upper and row_ticker == tk_upper:
                return sd_id
            if cn_lower and cn_lower in (row_name, row_canonical):
                return sd_id
    return None


def _scrape_stock_discovery(query: str) -> str | None:
    """
    Try to extract the integer company ID from stockdiscovery.in.
    Returns None silently if scraping fails — caller falls back to Tavily.
    """
    encoded = requests.utils.quote(query)
    search_url = f"https://stockdiscovery.in/search?q={encoded}"

    _ID_PATTERNS = (
        r'/company/(\d+)',
        r'/insight/india/(\d+)',
        r'"companyId"\s*:\s*(\d+)',
        r'"stockId"\s*:\s*(\d+)',
        r'"id"\s*:\s*(\d+)',
    )

    # Attempt 1: plain HTTP GET (works if the page is server-side rendered)
    try:
        resp = requests.get(
            search_url,
            headers={"User-Agent": "IDF research trade@ostwal.in"},
            timeout=_SD_SCRAPE_TIMEOUT,
        )
        if resp.status_code == 200:
            for pat in _ID_PATTERNS:
                m = re.search(pat, resp.text)
                if m:
                    logger.info(
                        f"Resolver: found stock_discovery_id={m.group(1)} "
                        f"via HTML for {query!r}"
                    )
                    return m.group(1)
    except Exception as exc:
        logger.debug(f"Resolver: stockdiscovery.in HTML scrape failed: {exc}")

    # Attempt 2: Firecrawl (handles JS-rendered pages)
    import os
    fc_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if fc_key:
        try:
            fc = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {fc_key}"},
                json={"url": search_url, "formats": ["markdown"]},
                timeout=_SD_SCRAPE_TIMEOUT * 2,
            )
            if fc.ok:
                text = (fc.json().get("data") or {}).get("markdown", "")
                for pat in _ID_PATTERNS:
                    m = re.search(pat, text)
                    if m:
                        logger.info(
                            f"Resolver: found stock_discovery_id={m.group(1)} "
                            f"via Firecrawl for {query!r}"
                        )
                        return m.group(1)
        except Exception as exc:
            logger.debug(f"Resolver: Firecrawl scrape failed: {exc}")

    logger.warning(f"Resolver: could not scrape stock_discovery_id for {query!r}")
    return None


def _cache_sd_id(company: str, ticker: str, sd_id: str) -> None:
    """Append a newly discovered stock_discovery_id row to company_map.csv."""
    try:
        with open(COMPANY_MAP, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow([
                company,
                ticker.upper() if ticker else company.upper(),
                "IN", "", "", company.lower(), sd_id,
            ])
        logger.info(
            f"Resolver: cached stock_discovery_id={sd_id} for {company!r} in company_map.csv"
        )
    except Exception as exc:
        logger.warning(f"Resolver: could not write SD ID to company_map.csv: {exc}")


# ── US resolution ─────────────────────────────────────────────────────────────

def _resolve_us(company: str, ticker: str) -> str | None:
    cik = _csv_lookup(company, ticker)
    if cik:
        logger.info("Resolver: match from company_map.csv")
        return cik
    cik = _edgar_tickers_lookup(company, ticker)
    if cik:
        logger.info("Resolver: match from EDGAR tickers JSON")
        return cik
    return None


def _csv_lookup(company: str, ticker: str) -> str | None:
    if not COMPANY_MAP.exists():
        return None
    cn_lower = company.lower()
    tk_upper = ticker.upper()
    with open(COMPANY_MAP, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row_ticker    = row.get("ticker", "").upper()
            row_name      = row.get("company_name", "").lower()
            row_canonical = row.get("canonical_name", "").lower()
            raw_cik       = row.get("cik", "")
            if not raw_cik:
                continue
            if tk_upper and row_ticker == tk_upper:
                return _pad(raw_cik)
            if cn_lower and cn_lower in (row_name, row_canonical):
                return _pad(raw_cik)
    return None


# Corporate suffix/filler words ignored when comparing company names to EDGAR
# titles. "Apple" must match "Apple Inc.", "ASML Holding" must match
# "ASML HOLDING NV" — exact title equality alone misses common names, and the
# old substring score for "apple" vs "apple inc." was exactly 0.5, one short
# of the > 0.5 fuzzy threshold.
_CORP_SUFFIX_RE = re.compile(
    r"\b(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|"
    r"lp|llp|sa|nv|se|ag|ab|asa|spa|oyj|holding|holdings|group)\b"
)


def _normalise_title(name: str) -> str:
    """Lowercase, drop punctuation, corporate suffixes and stray single letters.

    'Apple Inc.' -> 'apple';  'ASML Holding N.V.' -> 'asml'
    (the N.V. survives punctuation removal as single letters 'n v', hence the
    single-letter drop).
    """
    s = re.sub(r"[^\w\s]", " ", name.lower())
    s = _CORP_SUFFIX_RE.sub(" ", s)
    return " ".join(tok for tok in s.split() if len(tok) > 1)


def _edgar_tickers_lookup(company: str, ticker: str) -> str | None:
    data = _load_tickers()
    if not data:
        return None

    tk_upper = ticker.upper()
    cn_lower = company.lower()
    cn_norm  = _normalise_title(company)
    # Word-boundary containment; lookarounds instead of \b so names ending in
    # punctuation ("apple inc.") still anchor correctly.
    word_re  = re.compile(rf"(?<!\w){re.escape(cn_lower)}(?!\w)") if cn_lower else None

    exact_cik: int | None = None
    norm_cik: int | None = None
    best_cik: int | None = None
    best_score: float = 0.0

    # company_tickers.json is ordered roughly by market cap, so on ties the
    # first (largest) filer wins — the right default for bare famous names.
    for entry in data.values():
        e_ticker = entry.get("ticker", "").upper()
        e_title  = entry.get("title", "").lower()
        e_cik    = entry.get("cik_str", 0)

        if tk_upper and e_ticker == tk_upper:
            logger.debug(f"Resolver: exact ticker match {e_ticker} -> CIK {e_cik}")
            return _pad(str(e_cik))

        if exact_cik is None and cn_lower and e_title == cn_lower:
            exact_cik = e_cik

        if norm_cik is None and cn_norm and _normalise_title(e_title) == cn_norm:
            norm_cik = e_cik

        if word_re and e_title and word_re.search(e_title):
            score = len(cn_lower) / len(e_title)
            if score > best_score:
                best_score = score
                best_cik   = e_cik

    if exact_cik:
        logger.debug(f"Resolver: exact name match {cn_lower!r} -> CIK {exact_cik}")
        return _pad(str(exact_cik))

    if norm_cik:
        logger.debug(f"Resolver: suffix-stripped name match {cn_norm!r} -> CIK {norm_cik}")
        return _pad(str(norm_cik))

    if best_cik and best_score >= 0.5:
        logger.debug(f"Resolver: fuzzy name match score={best_score:.2f} -> CIK {best_cik}")
        return _pad(str(best_cik))

    return None


def _load_tickers() -> dict | None:
    """Return EDGAR company_tickers.json, refreshing the local cache if stale."""
    if TICKERS_CACHE.exists():
        age = time.time() - TICKERS_CACHE.stat().st_mtime
        if age < CACHE_TTL:
            logger.debug("Resolver: using cached EDGAR tickers")
            return json.loads(TICKERS_CACHE.read_text(encoding="utf-8"))

    logger.info("Resolver: downloading EDGAR company tickers JSON (~2 MB)")
    try:
        resp = requests.get(TICKERS_URL, headers=EDGAR_HEADERS, timeout=20)
        resp.raise_for_status()
        TICKERS_CACHE.write_text(resp.text, encoding="utf-8")
        logger.info(f"Resolver: tickers cached to {TICKERS_CACHE}")
        return resp.json()
    except Exception as exc:
        logger.error(f"Resolver: EDGAR tickers download failed: {exc}")
        return None


def _pad(cik: str) -> str:
    """Return zero-padded 10-digit CIK string."""
    return str(int(cik.strip() or "0")).zfill(10)
