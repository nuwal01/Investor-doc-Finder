"""
Entity Resolver — resolves a company name into structured financial entity data.

Input:  company_name (str), doc_type (str), year (int)
Output: dict {company_name, normalized_name, country, exchange_mic, isin, ir_url, ticker}

Resolution chain:
  1. OpenFIGI search → ticker, exchange_mic, isin, name
  2. Finnhub company profile → weburl (IR site), country
  3. If OpenFIGI misses, Groq LLM normalizes the name and retries
"""

import asyncio
import os
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from groq import Groq

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

OPENFIGI_URL = "https://api.openfigi.com/v3/search"
FINNHUB_PROFILE_URL = "https://finnhub.io/api/v1/stock/profile2"

# ── Global Country-to-Exchange Routing Map ──────────────────────────────────
# Maps country codes to primary exchanges, regulator URLs, and filing languages

COUNTRY_EXCHANGE_MAP: dict[str, dict] = {
    # Single Country Mappings
    "RU": {"exchanges": ["MOEX"], "urls": ["moex.com"], "languages": ["Russian"]},
    "TR": {"exchanges": ["KAP"], "urls": ["kap.org.tr"], "languages": ["Turkish"]},
    "ZA": {"exchanges": ["JSE"], "urls": ["jse.co.za"], "languages": ["English"]},
    "AE": {"exchanges": ["DFM", "ADX"], "urls": ["dfm.ae", "adx.ae"], "languages": ["Arabic", "English"]},
    "BR": {"exchanges": ["B3"], "urls": ["b3.com.br"], "languages": ["Portuguese"]},
    "UA": {"exchanges": ["PFTS"], "urls": ["pfts.com.ua"], "languages": ["Ukrainian"]},
    "NG": {"exchanges": ["NGX"], "urls": ["ngxgroup.com"], "languages": ["English"]},
    "MX": {"exchanges": ["BMV"], "urls": ["bmv.com.mx"], "languages": ["Spanish"]},
    "KZ": {"exchanges": ["KASE"], "urls": ["kase.kz"], "languages": ["Russian", "Kazakh"]},
    "SA": {"exchanges": ["Tadawul"], "urls": ["saudiexchange.sa"], "languages": ["Arabic", "English"]},
    "OM": {"exchanges": ["MSM"], "urls": ["msm.gov.om"], "languages": ["Arabic", "English"]},
    "CL": {"exchanges": ["BCS"], "urls": ["bolsadesantiago.com"], "languages": ["Spanish"]},
    "KW": {"exchanges": ["BKK"], "urls": ["boursakuwait.com.kw"], "languages": ["Arabic", "English"]},
    "IN": {"exchanges": ["BSE", "NSE"], "urls": ["bseindia.com", "nseindia.com"], "languages": ["English"]},
    "CO": {"exchanges": ["BVC"], "urls": ["bvc.com.co"], "languages": ["Spanish"]},
    "BH": {"exchanges": ["BHB"], "urls": ["bahrainbourse.com"], "languages": ["Arabic", "English"]},
    "GE": {"exchanges": ["GSE"], "urls": ["gse.ge"], "languages": ["Georgian", "English"]},
    "GB": {"exchanges": ["LSE"], "urls": ["londonstockexchange.com"], "languages": ["English"]},
    "QA": {"exchanges": ["QSE"], "urls": ["qe.com.qa"], "languages": ["Arabic", "English"]},
    "CN": {"exchanges": ["SSE", "SZSE"], "urls": ["sse.com.cn", "szse.cn"], "languages": ["Chinese"]},
    "BY": {"exchanges": ["BCSE"], "urls": ["bcse.by"], "languages": ["Russian"]},
    "AZ": {"exchanges": ["BSE"], "urls": ["bfb.az"], "languages": ["Azerbaijani", "English"]},
    "MA": {"exchanges": ["CSE"], "urls": ["casablanca-bourse.com"], "languages": ["French", "Arabic"]},
    "BG": {"exchanges": ["BSE"], "urls": ["bse-sofia.bg"], "languages": ["Bulgarian", "English"]},
    "LT": {"exchanges": ["Nasdaq Vilnius"], "urls": ["nasdaqbaltic.com"], "languages": ["Lithuanian", "English"]},
    "AR": {"exchanges": ["BYMA"], "urls": ["byma.com.ar"], "languages": ["Spanish"]},
    "AT": {"exchanges": ["Wiener Börse"], "urls": ["wienerborse.at"], "languages": ["German", "English"]},
    "NO": {"exchanges": ["Oslo Børs"], "urls": ["oslobors.no"], "languages": ["Norwegian", "English"]},
    "UZ": {"exchanges": ["RSE"], "urls": ["uzse.uz"], "languages": ["Uzbek", "Russian"]},
    "ID": {"exchanges": ["IDX"], "urls": ["idx.co.id"], "languages": ["Indonesian", "English"]},
    "HU": {"exchanges": ["BSE"], "urls": ["bet.hu"], "languages": ["Hungarian", "English"]},
    "CZ": {"exchanges": ["PSE"], "urls": ["pse.cz"], "languages": ["Czech", "English"]},
    "HR": {"exchanges": ["ZSE"], "urls": ["zse.hr"], "languages": ["Croatian", "English"]},
    "PA": {"exchanges": ["BVP"], "urls": ["panabolsa.com"], "languages": ["Spanish"]},
    "CH": {"exchanges": ["SIX"], "urls": ["six-group.com"], "languages": ["German", "French", "English"]},
    "US": {"exchanges": ["SEC"], "urls": ["sec.gov"], "languages": ["English"]},
    "PE": {"exchanges": ["BVL"], "urls": ["bvl.com.pe"], "languages": ["Spanish"]},
    "GR": {"exchanges": ["ATHEX"], "urls": ["athexgroup.gr"], "languages": ["Greek", "English"]},
    "MU": {"exchanges": ["SEM"], "urls": ["stockexchangeofmauritius.com"], "languages": ["English", "French"]},
    "KE": {"exchanges": ["NSE"], "urls": ["nse.co.ke"], "languages": ["English"]},
    "AU": {"exchanges": ["ASX"], "urls": ["asx.com.au"], "languages": ["English"]},
    "SE": {"exchanges": ["Nasdaq Stockholm"], "urls": ["nasdaqomxnordic.com"], "languages": ["Swedish", "English"]},
    "IE": {"exchanges": ["Euronext Dublin"], "urls": ["ise.ie"], "languages": ["English"]},
    "JO": {"exchanges": ["ASE"], "urls": ["exchange.jo"], "languages": ["Arabic", "English"]},
    "SG": {"exchanges": ["SGX"], "urls": ["sgx.com"], "languages": ["English"]},
    "NL": {"exchanges": ["Euronext Amsterdam"], "urls": ["euronext.com"], "languages": ["Dutch", "English"]},
    "PL": {"exchanges": ["GPW"], "urls": ["gpw.pl"], "languages": ["Polish", "English"]},
    "RO": {"exchanges": ["BVB"], "urls": ["bvb.ro"], "languages": ["Romanian", "English"]},
    "CA": {"exchanges": ["TSX"], "urls": ["tsx.com"], "languages": ["English", "French"]},
    "LU": {"exchanges": ["LuxSE"], "urls": ["bourse.lu"], "languages": ["French", "German", "English"]},
    "LK": {"exchanges": ["CSE"], "urls": ["cse.lk"], "languages": ["English"]},
    "LB": {"exchanges": ["BSE"], "urls": ["bse.com.lb"], "languages": ["Arabic", "English"]},
    "CY": {"exchanges": ["CSE"], "urls": ["cse.com.cy"], "languages": ["Greek", "English"]},
    "AM": {"exchanges": ["AMX"], "urls": ["amx.am"], "languages": ["Armenian", "English"]},
}

# Multilateral country mappings (check multiple exchanges)
MULTILATERAL_COUNTRY_MAP: dict[str, list[str]] = {
    "GB/ZA": ["LSE", "JSE"],
    "AE/GB": ["DFM", "ADX", "LSE"],
    "GB/GE": ["LSE", "GSE"],
    "GB/RU": ["LSE", "MOEX"],
    "KZ/AE": ["KASE", "AIX"],
    "SE/RU": ["Nasdaq Stockholm", "MOEX"],
    "GB/IE": ["LSE", "Euronext Dublin"],
    "AE/SA": ["DFM", "ADX", "Tadawul"],
    "GB/JO": ["LSE", "ASE"],
    "CH/SG": ["SIX", "SGX"],
    "NL/RU": ["Euronext Amsterdam", "MOEX"],
    "KZ/GB": ["KASE", "LSE"],
    "RO/PL": ["BVB", "GPW"],
    "NL/ZA": ["Euronext Amsterdam", "JSE"],
    "RU/LU": ["MOEX", "LuxSE"],
    "UZ/SG": ["RSE", "SGX"],
    "CH/UA": ["SIX", "PFTS"],
    "MU/GB": ["SEM", "LSE"],
    "GB/GR": ["LSE", "ATHEX"],
    "GB/IN": ["LSE", "BSE", "NSE"],
    "GB/LK": ["LSE", "CSE"],
    "BR/PE": ["B3", "BVL"],
    "AE/LB": ["DFM", "ADX", "BSE"],
    "RU/CY": ["MOEX", "CSE"],
    "NL/NG": ["Euronext Amsterdam", "NGX"],
    "CH/RU": ["SIX", "MOEX"],
    "RU/NL": ["MOEX", "Euronext Amsterdam"],
    "NL/BR": ["Euronext Amsterdam", "B3"],
    "BR/NL": ["B3", "Euronext Amsterdam"],
    "GB/RU/AM": ["LSE", "MOEX", "AMX"],
    "PE/CL": ["BVL", "BCS"],
}

# OpenFIGI exchCode → ISO country (covers common non-US exchanges)
_EXCHCODE_TO_COUNTRY: dict[str, str] = {
    # India
    "IB": "IN", "IN": "IN", "NS": "IN", "IS": "IN",
    # UAE
    "DU": "AE", "AD": "AE", "DF": "AE",
    # Turkey
    "TK": "TR", "TI": "TR",
    # Japan
    "JP": "JP", "JT": "JP",
    # UK
    "LN": "GB", "IL": "GB",
    # Europe
    "PA": "FR", "AM": "NL", "BB": "BE", "LB": "PT", "ID": "IE",
    # Saudi Arabia
    "AB": "SA", "SR": "SA",
    # Singapore
    "SP": "SG",
    # Malaysia
    "MK": "MY", "KL": "MY",
    # Thailand
    "TB": "TH", "BK": "TH",
    # South Africa
    "SJ": "ZA", "JO": "ZA",
    # Nigeria
    "LA": "NG", "NL": "NG",
    # China/HK
    "HK": "HK", "CH": "CN", "C1": "CN",
    # Korea
    "KS": "KR", "KQ": "KR",
    # Australia
    "AU": "AU",
    # Canada
    "CN": "CA", "CT": "CA",
    # Brazil
    "BZ": "BR",
    # Russia
    "MM": "RU", "MO": "RU",
    # Mexico
    "MM": "MX",
    # Kazakhstan
    "KZ": "KZ",
    # Norway
    "NO": "NO",
    # Sweden
    "SS": "SE",
    # Switzerland
    "SW": "CH", "VX": "CH",
    # Austria
    "AV": "AT",
    # Greece
    "GA": "GR",
    # Poland
    "PW": "PL",
    # Czech Republic
    "CP": "CZ",
    # Romania
    "BU": "RO",
}


def _empty_entity(company_name: str) -> dict:
    """Return a blank entity dict with only the original company_name filled."""
    return {
        "company_name": company_name,
        "normalized_name": "",
        "country": "",
        "exchange_mic": "",
        "isin": "",
        "ir_url": "",
        "ticker": "",
        "bse_scripcode": "",   # numeric BSE code for Indian companies
        "nse_symbol": "",      # NSE ticker symbol for Indian companies
    }


def _detect_country_from_name(company_name: str) -> str:
    """Infer country from company name keywords when APIs don't return one."""
    name_lower = company_name.lower()
    # UAE indicators (check before India — PJSC companies don't use Ltd)
    if any(kw in name_lower for kw in ("pjsc", "p.j.s.c", "dubai", "abu dhabi", "emaar",
                                        "adnoc", "emirates nbd", "dib", "dfm", "etisalat",
                                        "du telecom")):
        return "AE"
    # Turkish indicators
    if any(kw in name_lower for kw in ("a.ş.", "a.s.", "anonim şirket", "botas", "botaş")):
        return "TR"
    # Indian indicators (after UAE since Gulf companies can use "limited")
    indian_sfx = (" limited", " ltd.", " ltd,", " industries", " enterprises",
                  " pharmaceuticals", " infosys", " wipro", " tata ", "reliance ")
    if any(sfx in name_lower for sfx in indian_sfx):
        return "IN"
    return ""


async def _search_openfigi(client: httpx.AsyncClient, query: str) -> dict | None:
    """Search OpenFIGI for the given query string.
    Returns the first result dict or None."""
    payload = {"query": query, "start": 0, "maxRecords": 1}
    resp = await client.post(OPENFIGI_URL, json=payload, timeout=15)
    if resp.status_code != 200:
        return None
    data = resp.json()
    results = data.get("data", [])
    if not results:
        return None
    return results[0]


async def _get_finnhub_profile(client: httpx.AsyncClient, ticker: str) -> dict:
    """Fetch company profile from Finnhub. Returns the JSON dict (may be empty)."""
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    resp = await client.get(FINNHUB_PROFILE_URL, params=params, timeout=15)
    if resp.status_code != 200:
        return {}
    data = resp.json()
    return data if data else {}


def _normalize_name_with_llm(company_name: str) -> str:
    """Use Groq llama-3.3-70b-versatile to produce a cleaner company name
    that is more likely to match in financial databases."""
    client = Groq(api_key=GROQ_API_KEY)

    prompt = (
        "Given the following company name, return the official legal or widely-recognised "
        "stock-market name that would appear in financial databases like OpenFIGI or Bloomberg.\n"
        "Reply with ONLY the normalized company name, nothing else.\n\n"
        f"Company: {company_name}"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=50,
    )

    return response.choices[0].message.content.strip()


SERPER_URL = "https://google.serper.dev/search"


def _domain_matches_company(domain: str, company_name: str) -> bool:
    """Check if any significant company name word appears in the domain."""
    domain_lower = domain.lower().replace("-", "").replace(".", " ")
    words = [w.lower() for w in company_name.split() if len(w) > 2]
    # Ignore generic suffixes
    ignore = {"limited", "ltd", "inc", "corp", "corporation", "group", "plc", "llc"}
    words = [w for w in words if w not in ignore]
    return any(w in domain_lower for w in words)


async def _find_ir_url_via_ticker(client: httpx.AsyncClient, ticker: str, company_name: str) -> str:
    """Search Serper for IR URL using ticker symbol — handles rebranded companies.

    e.g. 'BTEL investor relations' finds Beyon (formerly Batelco) even if name search fails.
    """
    if not SERPER_API_KEY or not ticker:
        return ""

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    queries = [
        f'"{ticker}" investor relations annual report',
        f'{ticker} "{company_name}" investor relations',
    ]

    SKIP_DOMAINS = {"wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
                    "x.com", "bloomberg.com", "reuters.com", "google.com"}

    for query in queries:
        try:
            resp = await client.post(
                SERPER_URL, json={"q": query, "num": 5}, headers=headers, timeout=12,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            for item in data.get("organic", []):
                link = item.get("link", "")
                if not link:
                    continue
                from urllib.parse import urlparse as _up
                parsed = _up(link)
                domain = parsed.netloc.lower().replace("www.", "")
                if any(s in domain for s in SKIP_DOMAINS):
                    continue
                url_lower = link.lower()
                title = item.get("title", "").lower()
                if any(kw in f"{url_lower} {title}" for kw in ("investor", "annual", "ir", "report")):
                    return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            continue
    return ""


async def _find_ir_url_via_serper(client: httpx.AsyncClient, company_name: str) -> str:
    """Search Serper for the company's investor relations page.

    Tries multiple queries in priority order.
    Only accepts results whose domain contains a company name word.
    Returns the best URL found, or a fallback domain URL.
    """
    if not SERPER_API_KEY:
        return ""

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

    # Build query list — add region-specific queries for known company types
    queries = [
        f'"{company_name}" investor relations annual report site',
        f'"{company_name}" ir website annual report',
        f'"{company_name}" official website',
    ]
    name_lower = company_name.lower()
    if any(sfx in name_lower for sfx in ("limited", " ltd", " ltd.")):
        # Indian company hints
        queries.append(f'"{company_name}" bseindia.com annual report')
    if any(sfx in name_lower for sfx in ("a.ş.", "a.s.", "anonim")):
        # Turkish company hints
        queries.append(f'"{company_name}" kap.org.tr annual report')
    queries.append(f'"{company_name}" kurumsal faaliyet raporu')  # Turkish IR

    SKIP_DOMAINS = {"wikipedia.org", "linkedin.com", "facebook.com",
                    "twitter.com", "x.com", "youtube.com", "bloomberg.com",
                    "reuters.com", "google.com", "crunchbase.com",
                    "zaubacorp.com", "tofler.in", "ambitionbox.com",
                    "glassdoor.com", "indeed.com", "moneycontrol.com",
                    "economictimes.com", "livemint.com"}

    best_base = ""
    for query in queries:
        try:
            resp = await client.post(
                SERPER_URL, json={"q": query, "num": 5}, headers=headers, timeout=15,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            for item in data.get("organic", []):
                link = item.get("link", "")
                if not link:
                    continue
                parsed = urlparse(link)
                domain = parsed.netloc.lower().replace("www.", "")
                # Skip generic aggregator sites
                if any(s in domain for s in SKIP_DOMAINS):
                    continue
                # Domain must contain a company name word
                if not _domain_matches_company(domain, company_name):
                    continue
                # Check URL path, title, and snippet for investor-related keywords
                url_lower = link.lower()
                title = item.get("title", "").lower()
                snippet = item.get("snippet", "").lower()
                combined = f"{url_lower} {title} {snippet}"
                if any(kw in combined for kw in ("investor", "annual", "report", "financial")):
                    if parsed.path and parsed.path.strip("/"):
                        return link
                    return f"{parsed.scheme}://{parsed.netloc}"
                if not best_base:
                    best_base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            continue

    # Regional fallbacks when Serper found nothing usable
    if not best_base:
        if any(sfx in name_lower for sfx in ("limited", " ltd", " ltd.")):
            # Indian company — use BSE search as last resort IR URL
            best_base = "https://www.bseindia.com"
        elif any(sfx in name_lower for sfx in ("a.ş.", "a.s.", "anonim")):
            # Turkish company — use KAP as last resort
            best_base = "https://www.kap.org.tr"

    return best_base


async def resolve_entity(company_name: str, doc_type: str, year: int) -> dict:
    """Resolve a company name into a full entity dict.

    Args:
        company_name: raw or parsed company name
        doc_type: document type (for context, not used in resolution)
        year: target year (for context, not used in resolution)

    Returns:
        dict with keys: company_name, normalized_name, country,
                        exchange_mic, isin, ir_url, ticker
    """
    entity = _empty_entity(company_name)

    async with httpx.AsyncClient() as client:
        # --- Step 1: OpenFIGI search ---
        figi_result = await _search_openfigi(client, company_name)

        # --- Step 3: If no results, normalize with LLM and retry ---
        if figi_result is None:
            normalized = _normalize_name_with_llm(company_name)
            entity["normalized_name"] = normalized
            figi_result = await _search_openfigi(client, normalized)

        # Extract OpenFIGI fields
        if figi_result:
            exch_code = figi_result.get("exchCode", "")
            ticker = figi_result.get("ticker", "")
            entity["ticker"] = ticker
            entity["exchange_mic"] = exch_code
            entity["isin"] = figi_result.get("isin", "") or ""
            if not entity["normalized_name"]:
                entity["normalized_name"] = figi_result.get("name", company_name)

            # Derive country from OpenFIGI exchCode if Finnhub hasn't set it
            if not entity["country"] and exch_code:
                entity["country"] = _EXCHCODE_TO_COUNTRY.get(exch_code, "")

            # Store exchange-specific fields for India
            if exch_code == "IB" and ticker.isdigit():
                entity["bse_scripcode"] = ticker   # BSE numeric code
            elif exch_code in ("IN", "NS") and ticker and not ticker.isdigit():
                entity["nse_symbol"] = ticker      # NSE alphanumeric symbol

        # --- Step 2: Finnhub profile ---
        if entity["ticker"]:
            profile = await _get_finnhub_profile(client, entity["ticker"])
            if profile.get("country"):
                entity["country"] = profile["country"]
            if profile.get("weburl"):
                # FIX 5: Finnhub IR URL is authoritative — use even if domain differs from name
                entity["ir_url"] = profile["weburl"]

        # --- Name-based country detection as last resort ---
        if not entity["country"]:
            entity["country"] = _detect_country_from_name(company_name)

        # --- Step 3: Serper fallback for ir_url ---
        if not entity["ir_url"]:
            # FIX 5: Try ticker-based search first (catches rebranded companies)
            ticker = entity.get("ticker", "")
            if ticker and not ticker.isdigit():
                entity["ir_url"] = await _find_ir_url_via_ticker(client, ticker, company_name)

        if not entity["ir_url"]:
            entity["ir_url"] = await _find_ir_url_via_serper(client, company_name)

        # FIX 5: For companies with no ticker, try country-scoped Serper search
        if not entity["ir_url"] and entity.get("country"):
            country_query_name = entity.get("normalized_name") or company_name
            country = entity["country"]
            entity["ir_url"] = await _find_ir_url_via_serper(
                client, f"{country_query_name} {country}"
            )

    return entity


if __name__ == "__main__":
    test_companies = [
        ("Apple", "annual_report", 2023),
        ("Reliance Industries", "annual_report", 2023),
        ("Samsung", "investor_presentation", 2024),
    ]

    async def main():
        for name, doc_type, year in test_companies:
            print(f"\n{'='*50}")
            print(f"Resolving: {name} | {doc_type} | {year}")
            print("=" * 50)
            result = await resolve_entity(name, doc_type, year)
            for k, v in result.items():
                print(f"  {k:20s}: {v}")

    asyncio.run(main())
