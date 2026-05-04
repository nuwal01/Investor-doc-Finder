"""
Entity Resolver — resolves a company name into structured financial entity data.

Input:  company_name (str), doc_type (str), year (int)
Output: dict {company_name, normalized_name, country, exchange_mic, isin, ir_url, ticker,
              ir_url_candidates}

Resolution chain:
  1. OpenFIGI search → ticker, exchange_mic, isin, name
  2a. Finnhub /search fallback (FIX 1) — when OpenFIGI returns no exchCode
  2b. Country-based MIC inference (FIX 1) — last resort
  3.  Finnhub company profile → weburl (IR site), country
  4.  IR URL validation (FIX 2) — reject aggregators, generate CDN variants
  5.  Serper fallback for ir_url
"""

import asyncio
import logging
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
FINNHUB_SEARCH_URL = "https://finnhub.io/api/v1/search"

# FIX 1 — Maps Finnhub exchange name strings to MIC codes used by exchange_direct.py.
# Sorted longest-first so substring matching is unambiguous (no false sub-matches).
_FINNHUB_EXCHANGE_TO_MIC: dict[str, str] = {
    "NATIONAL STOCK EXCHANGE OF INDIA": "XNSE",
    "BORSA ISTANBUL": "XIST",
    "JOHANNESBURG": "XJSE",
    "HONG KONG": "XHKG",
    "ABU DHABI": "XADS",
    "SINGAPORE": "XSES",
    "SHENZHEN": "XSHE",
    "SHANGHAI": "XSHG",
    "AUSTRALIAN": "XASX",
    "NIGERIAN": "XNSA",
    "TADAWUL": "XSAU",
    "BOMBAY": "XBOM",
    "TORONTO": "XTSE",
    "JAKARTA": "XIDX",
    "MOSCOW": "XMOS",
    "BOVESPA": "BVMF",
    "NASDAQ": "XNAS",
    "LONDON": "XLON",
    "DUBAI": "XDFM",
    "QATAR": "DSMD",
    "SAUDI": "XSAU",
    "MOEX": "XMOS",
    "NYSE": "XNYS",
    "LSE": "XLON",
    "KAP": "XIST",
    "NGX": "XNSA",
    "DFM": "XDFM",
    "ADX": "XADS",
    "QSE": "DSMD",
    "JSE": "XJSE",
    "IDX": "XIDX",
    "ASX": "XASX",
    "TSX": "XTSE",
    "SGX": "XSES",
    "B3":  "BVMF",
    "HKEX": "XHKG",
}

# FIX 1 — When both OpenFIGI and Finnhub /search return no exchCode, infer MIC from country.
# MIC values must match the MIC-set names in exchange_direct.py.
_COUNTRY_TO_MIC_FALLBACK: dict[str, str] = {
    "US": "XNAS", "TR": "XIST", "NG": "XNSA", "IN": "XBOM",
    "GB": "XLON", "RU": "XMOS", "JP": "XTKS", "AE": "XDFM",
    "SA": "XSAU", "BR": "BVMF", "ZA": "XJSE", "MY": "XKLS",
    "SG": "XSES", "TH": "XBKK", "AU": "XASX", "CA": "XTSE",
    "FR": "XPAR", "NL": "XAMS", "BE": "XBRU", "PT": "XLIS",
    "IE": "XDUB", "KE": "XNAI", "GH": "XGHA", "OM": "XMSM",
}

# Country → preferred TLD(s). Used to detect subsidiary domains.
# E.g. Halyk Bank (KZ) resolving to halykbank.ge → .ge ≠ .kz → search for parent.
COUNTRY_TLD_MAP: dict[str, list[str]] = {
    "KZ": [".kz"],
    "NG": [".ng", ".com.ng"],
    "RO": [".ro"],
    "GE": [".ge"],
    "QA": [".qa", ".com.qa"],
    "CO": [".co"],
    "SA": [".com.sa", ".sa"],
    "TR": [".com.tr", ".tr"],
    "RU": [".ru"],
    "UA": [".ua"],
    "IN": [".in", ".co.in"],
    "AE": [".ae"],
    "ZA": [".co.za", ".za"],
    "KE": [".co.ke", ".ke"],
    "GH": [".com.gh", ".gh"],
    "EG": [".eg", ".com.eg"],
    "GB": [".co.uk"],
}

# FIX 2 — Domains that must NEVER be used as the company IR URL seed.
# Site-scoped Serper on an aggregator returns wrong-company documents.
_IR_AGGREGATOR_DOMAINS: tuple[str, ...] = (
    "africanfinancials.com", "annualreports.com", "annualreport.com",
    "scribd.com", "slideshare.net", "axisdirect.in", "moneycontrol.com",
    "screener.in", "marketscreener.com", "macrotrends.net", "wisesheets.io",
    "wsj.com", "reuters.com", "bloomberg.com", "ft.com",
    "businesswire.com", "prnewswire.com", "globenewswire.com",
    "yahoo.com", "finance.yahoo.com", "marketwatch.com", "investing.com",
    "stockanalysis.com", "simplywall.st",
)

# Stock exchange domains that are never the company's own IR page.
# If entity_resolver resolves one of these as ir_url, it must be discarded.
_EXCHANGE_DOMAINS_NOT_IR: frozenset = frozenset({
    "bseindia.com", "nseindia.com", "kap.org.tr", "dfm.ae", "adx.ae",
    "msm.gov.om", "sgx.com", "hkex.com.hk", "jpx.co.jp", "krx.co.kr",
    "asx.com.au", "tsx.com", "londonstockexchange.com", "euronext.com",
    "boerse-frankfurt.de", "six-group.com",
})

# Subdomain prefixes that indicate dedicated IR pages — preferred over generic domains.
_IR_PREFERRED_SUBDOMAIN_PREFIXES: tuple[str, ...] = (
    "ri.", "ir.", "investors.", "investor.", "investorrelations.", "relations.",
)

# Subdomain prefixes that are never IR pages — hard-reject when selecting IR URL.
_KNOWN_REJECT_SUBDOMAIN_PREFIXES: tuple[str, ...] = (
    "saude.", "health.", "rh.", "careers.", "jobs.",
    "media.", "news.", "press.", "blog.", "shop.",
    "store.", "ecommerce.", "support.", "help.",
    "mail.", "webmail.", "intranet.", "portal.",
)

# ── Global Country-to-Exchange Routing Map ──────────────────────────────────
COUNTRY_EXCHANGE_MAP: dict[str, dict] = {
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

KNOWN_IR_URLS: dict[str, str] = {
    "zenith bank": "https://www.zenithbank.com/investor-relations/",
    "banca transilvania": "https://www.bancatransilvania.ro/relatii-investitori/",
    "halyk bank": "https://halykbank.kz/en/about/investor-relations/",
    "bank of georgia": "https://bankofgeorgia.ge/investor-relations/",
    "upl limited": "https://www.upl-ltd.com/investors/",
    "dno asa": "https://www.dno.no/investor-relations/",
    "petroleo brasileiro": "https://ri.petrobras.com.br/en/",
    "petrobras": "https://ri.petrobras.com.br/en/",
    "gerdau s.a.": "https://ri.gerdau.com/en/",
    "gerdau": "https://ri.gerdau.com/en/",
    "ypf s.a.": "https://inversores.ypf.com/en/",
    "ypf": "https://inversores.ypf.com/en/",
    "pt tower bersama": "https://www.towerbersama.com/investor-relations/",
    "tower bersama": "https://www.towerbersama.com/investor-relations/",
    "sabic": "https://www.sabic.com/en/investors/",
    "pjsc lukoil": "https://lukoil.com/InvestorAndShareholderCenter/",
    "lukoil": "https://lukoil.com/InvestorAndShareholderCenter/",
    "mtn group limited": "https://www.mtn.com/investors/",
    "mtn group": "https://www.mtn.com/investors/",
    "eskom holdings": "https://www.eskom.co.za/IR{year}/",
    "eskom": "https://www.eskom.co.za/IR{year}/",
    "adani ports": "https://www.adaniports.com/investor-relations/",
    "emaar properties": "https://www.emaar.com/en/investor-relations/",
    "dana gas": "https://www.danagas.com/investors/",
    "nostrum oil & gas": "https://www.nostrumoilandgas.com/investors/",
    "nostrum oil": "https://www.nostrumoilandgas.com/investors/",
    "bank muscat": "https://www.bankmuscat.com/en/investor-relations/",
    "infosys": "https://www.infosys.com/investors.html",
    "infosys limited": "https://www.infosys.com/investors.html",
    "infosys ltd": "https://www.infosys.com/investors.html",
    "tata consultancy services": "https://www.tcs.com/investor-relations",
    "tcs": "https://www.tcs.com/investor-relations",
    "wipro": "https://www.wipro.com/investors/",
    "wipro limited": "https://www.wipro.com/investors/",
    "hcl technologies": "https://www.hcltech.com/investor-relations",
    "hcl tech": "https://www.hcltech.com/investor-relations",
    "reliance industries": "https://www.ril.com/investors.aspx",
    "reliance": "https://www.ril.com/investors.aspx",
    "hdfc bank": "https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?folderPath=/footer/Investor+Relations/",
    "icici bank": "https://www.icicibank.com/investor-relations",
    "bharti airtel": "https://www.airtel.in/investor-relations/",
    "airtel": "https://www.airtel.in/investor-relations/",
}

# Year-templated direct PDF URL patterns for companies where IR crawl and Serper
# both fail (403 blocks / indexing gaps).  Keys are normalised names (legal suffixes
# already stripped).  Variables: {year} 4-digit, {nyear} year+1 4-digit,
# {yy} 2-digit, {nyy} year+1 2-digit.
KNOWN_PDF_URLS: dict[str, list[str]] = {
    # Indian companies use April–March fiscal year: "Annual Report 2024" covers
    # Apr 2023 – Mar 2024, so the filename convention is {pyear}-{yy} (e.g. 2023-24).
    "infosys": [
        # Infosys uses FY-end 2-digit year (ar-24 for FY2024) and full year (ar-2024)
        "https://www.infosys.com/investors/reports-filings/annual-report/annual/Documents/infosys-ar-{yy}.pdf",
        "https://www.infosys.com/investors/reports-filings/annual-report/annual/Documents/infosys-ar-{year}.pdf",
    ],
    "tata consultancy services": [
        "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/{pyear}-{yy}/ar/tcs-annual-report-{pyear}-{year}.pdf",
    ],
    "tcs": [
        "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/{pyear}-{yy}/ar/tcs-annual-report-{pyear}-{year}.pdf",
    ],
    "reliance industries": [
        "https://www.ril.com/getattachment/investors/financial-reporting/annual-reports/Annual-Report-{pyear}-{yy}.pdf",
        "https://www.ril.com/DownloadFiles/IRDocuments/RIL-Annual-Report-{pyear}-{yy}.pdf",
    ],
    "reliance": [
        "https://www.ril.com/getattachment/investors/financial-reporting/annual-reports/Annual-Report-{pyear}-{yy}.pdf",
        "https://www.ril.com/DownloadFiles/IRDocuments/RIL-Annual-Report-{pyear}-{yy}.pdf",
    ],
    "wipro": [
        "https://www.wipro.com/content/dam/nexus/en/investor-relations/wipro-annual-report-{pyear}-{yy}.pdf",
    ],
}


def resolve_known_pdf_url(company_name: str, year: int) -> list[str]:
    """Return candidate PDF URLs for known companies where IR crawl/Serper fails."""
    normalized = company_name.lower().strip()
    for suffix in (" limited", " ltd", " inc", " plc", " corp"):
        normalized = normalized.replace(suffix, "").strip()

    patterns = KNOWN_PDF_URLS.get(normalized, [])
    if not patterns:
        return []

    pyear = str(year - 1)
    pyy   = str(year - 1)[-2:]
    yy    = str(year)[-2:]
    nyy   = str(year + 1)[-2:]
    nyear = str(year + 1)

    urls = []
    for pattern in patterns:
        url = pattern.replace("{year}", str(year))
        url = url.replace("{nyear}", nyear)
        url = url.replace("{pyear}", pyear)
        url = url.replace("{yy}", yy)
        url = url.replace("{nyy}", nyy)
        url = url.replace("{pyy}", pyy)
        urls.append(url)

    return urls


# Ticker → correct ISO country code for known API misclassifications.
# Applied after OpenFIGI/Finnhub resolution to fix wrong country assignments.
TICKER_COUNTRY_OVERRIDE: dict[str, str] = {
    "MTN":   "ZA",
    "MTNOY": "ZA",
    "SABIC": "SA",
    "LKOH":  "RU",
    "LKOD":  "RU",
    "ROSN":  "RU",
    "NVTK":  "RU",
    "GAZP":  "RU",
    "SBER":  "RU",
    "VTBR":  "RU",
    "PETR4": "BR",
    "PETR3": "BR",
    "GGBR4": "BR",
    "BRKM3": "BR",
    "EC":    "CO",
    "YPF":   "AR",
    "TBIG":  "ID",
    "UPLL":  "IN",
    "ADSEZ": "IN",
}

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

_EXCHCODE_TO_COUNTRY: dict[str, str] = {
    "IB": "IN", "IN": "IN", "NS": "IN", "IS": "IN",
    "DU": "AE", "AD": "AE", "DF": "AE",
    "TK": "TR", "TI": "TR",
    "JP": "JP", "JT": "JP",
    "LN": "GB", "IL": "GB",
    "PA": "FR", "AM": "NL", "BB": "BE", "LB": "PT", "ID": "IE",
    "AB": "SA", "SR": "SA",
    "SP": "SG",
    "MK": "MY", "KL": "MY",
    "TB": "TH", "BK": "TH",
    "SJ": "ZA", "JO": "ZA",
    "LA": "NG", "NL": "NG",
    "HK": "HK", "CH": "CN", "C1": "CN",
    "KS": "KR", "KQ": "KR",
    "AU": "AU",
    "CN": "CA", "CT": "CA",
    "BZ": "BR",
    "MM": "RU", "MO": "RU",
    "KZ": "KZ",
    "NO": "NO",
    "SS": "SE",
    "SW": "CH", "VX": "CH",
    "AV": "AT",
    "GA": "GR",
    "PW": "PL",
    "CP": "CZ",
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
        "bse_scripcode": "",      # numeric BSE code for Indian companies
        "nse_symbol": "",         # NSE ticker symbol for Indian companies
        "ir_url_candidates": [],  # CDN/subdomain variants of the primary IR URL (FIX 2)
    }


def _detect_country_from_name(company_name: str) -> str:
    """Infer country from company name keywords when APIs don't return one."""
    name_lower = company_name.lower()
    if any(kw in name_lower for kw in ("pjsc", "p.j.s.c", "dubai", "abu dhabi", "emaar",
                                        "adnoc", "emirates nbd", "dib", "dfm", "etisalat",
                                        "du telecom")):
        return "AE"
    if any(kw in name_lower for kw in ("a.ş.", "a.s.", "anonim şirket", "botas", "botaş")):
        return "TR"
    indian_sfx = (" limited", " ltd.", " ltd,", " industries", " enterprises",
                  " pharmaceuticals", " infosys", " wipro", " tata ", "reliance ")
    if any(sfx in name_lower for sfx in indian_sfx):
        return "IN"
    return ""


# ── FIX 1: Finnhub /search fallback ─────────────────────────────────────────

def _map_finnhub_exchange_to_mic(exchange_str: str) -> str:
    """Map a Finnhub exchange name string to a MIC code. Returns '' if no match."""
    upper = exchange_str.upper()
    for keyword, mic in _FINNHUB_EXCHANGE_TO_MIC.items():
        if keyword in upper:
            return mic
    return ""


async def _search_finnhub_companies(client: httpx.AsyncClient, company_name: str) -> dict | None:
    """Search Finnhub /search for company; returns first result dict or None."""
    if not FINNHUB_API_KEY:
        return None
    try:
        params = {"q": company_name, "token": FINNHUB_API_KEY}
        resp = await client.get(FINNHUB_SEARCH_URL, params=params, timeout=12)
        if resp.status_code != 200:
            return None
        results = resp.json().get("result", [])
        if not results:
            return None
        # Prefer description closest to company_name
        name_lower = company_name.lower()
        for r in results:
            desc = (r.get("description") or "").lower()
            if desc and (name_lower in desc or desc in name_lower):
                return r
        return results[0]
    except Exception:
        return None


# ── FIX 2: IR URL validation helpers ────────────────────────────────────────

def _ir_domain_is_aggregator(url: str) -> bool:
    """Return True if url belongs to a known aggregator/news domain."""
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        return any(agg in netloc for agg in _IR_AGGREGATOR_DOMAINS)
    except Exception:
        return False


def _ir_domain_is_exchange(url: str) -> bool:
    """Return True if url belongs to a stock exchange (never the company's own IR page)."""
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        return any(netloc == d or netloc.endswith("." + d) for d in _EXCHANGE_DOMAINS_NOT_IR)
    except Exception:
        return False


def _subdomain_is_rejected(url: str) -> bool:
    """Return True if url's subdomain prefix is a known non-IR subdomain (e.g. saude., health.)."""
    try:
        netloc = urlparse(url).netloc.lower()
        return any(netloc.startswith(p) for p in _KNOWN_REJECT_SUBDOMAIN_PREFIXES)
    except Exception:
        return False


def _subdomain_is_preferred_ir(url: str) -> bool:
    """Return True if url's subdomain signals a dedicated IR page (e.g. ri., ir., investors.)."""
    try:
        netloc = urlparse(url).netloc.lower()
        return any(netloc.startswith(p) for p in _IR_PREFERRED_SUBDOMAIN_PREFIXES)
    except Exception:
        return False


def _ir_domain_matches_company(url: str, company_name: str) -> bool:
    """Return True if at least one significant company word appears in the URL domain."""
    try:
        netloc = urlparse(url).netloc.lower().replace("-", "").replace(".", " ")
        ignore = {"limited", "group", "holdings", "africa", "global", "international",
                  "india", "company", "corporation", "industries"}
        words = [w.lower() for w in company_name.split() if len(w) > 4 and w.lower() not in ignore]
        return any(w in netloc for w in words)
    except Exception:
        return False


def _generate_cdn_variants(ir_url: str) -> list[str]:
    """Return CDN/subdomain variants of the IR URL for site-scoped search broadening."""
    try:
        parsed = urlparse(ir_url)
        netloc = parsed.netloc.lower()
        parts = netloc.split(".")
        domain_base = ".".join(parts[1:]) if len(parts) > 2 else netloc
        scheme = parsed.scheme or "https"
        variants = []
        for sub in ("ir", "s", "cdn", "files", "reports", "investor", "investors", "media"):
            candidate = f"{scheme}://{sub}.{domain_base}"
            if candidate.rstrip("/") != ir_url.rstrip("/"):
                variants.append(candidate)
        return variants
    except Exception:
        return []


async def _find_ir_url_clean(client: httpx.AsyncClient, company_name: str) -> str:
    """Serper search for a non-aggregator IR URL containing a company name token."""
    if not SERPER_API_KEY:
        return ""
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    query = f'"{company_name}" investor relations annual report'
    try:
        resp = await client.post(
            SERPER_URL, json={"q": query, "num": 10}, headers=headers, timeout=15,
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        for item in data.get("organic", []):
            link = item.get("link", "")
            if not link:
                continue
            if _ir_domain_is_aggregator(link):
                continue
            if _subdomain_is_rejected(link):
                continue
            if _ir_domain_matches_company(link, company_name):
                parsed = urlparse(link)
                return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return ""


# ── Existing helpers (unchanged) ─────────────────────────────────────────────

async def _search_openfigi(client: httpx.AsyncClient, query: str) -> dict | None:
    """Search OpenFIGI for the given query string."""
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
    """Fetch company profile from Finnhub."""
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    resp = await client.get(FINNHUB_PROFILE_URL, params=params, timeout=15)
    if resp.status_code != 200:
        return {}
    data = resp.json()
    return data if data else {}


def _normalize_name_with_llm(company_name: str) -> str:
    """Use Groq to produce a cleaner company name for OpenFIGI."""
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
    domain_lower = domain.lower().replace("-", "").replace(".", "")
    # Broad ignore for word-match: legal suffixes + generic geo/industry words that
    # appear in many unrelated domain names (e.g. "africa" matches "africanfinancials").
    _WORD_IGNORE = frozenset({
        "limited", "ltd", "inc", "corp", "corporation", "group", "plc", "llc",
        "africa", "african", "bank", "national", "global", "international",
        "america", "american", "europe", "european", "the", "and", "for",
    })
    # Only words longer than 3 chars — "for", "and" etc. cause false substring matches.
    words = [w.lower() for w in company_name.split()
             if len(w) > 3 and w.lower() not in _WORD_IGNORE]
    if any(w in domain_lower for w in words):
        return True
    # Acronym fallback: "United Bank Africa Plc" → "uba" matches "ubagroup".
    # Narrower ignore set so geo words (Africa, Bank) stay in the acronym.
    _ACRONYM_IGNORE = frozenset({"limited", "ltd", "inc", "corp", "corporation",
                                  "group", "plc", "llc", "the", "and", "for"})
    significant = [w for w in company_name.split()
                   if len(w) >= 4 and w.lower() not in _ACRONYM_IGNORE]
    acronym = "".join(w[0].lower() for w in significant)
    if len(acronym) >= 3 and acronym in domain_lower:
        return True
    return False


async def _find_ir_url_via_ticker(client: httpx.AsyncClient, ticker: str, company_name: str) -> str:
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
    if not SERPER_API_KEY:
        return ""

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

    queries = [
        f'"{company_name}" investor relations annual report site',
        f'"{company_name}" ir website annual report',
        f'"{company_name}" official website',
    ]
    name_lower = company_name.lower()
    if any(sfx in name_lower for sfx in ("limited", " ltd", " ltd.")):
        queries.append(f'"{company_name}" bseindia.com annual report')
    if any(sfx in name_lower for sfx in ("a.ş.", "a.s.", "anonim")):
        queries.append(f'"{company_name}" kap.org.tr annual report')
    queries.append(f'"{company_name}" kurumsal faaliyet raporu')

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
                if _ir_domain_is_aggregator(link):
                    continue
                if _subdomain_is_rejected(link):
                    continue
                parsed = urlparse(link)
                domain = parsed.netloc.lower().replace("www.", "")
                if any(s in domain for s in SKIP_DOMAINS):
                    continue
                if not _domain_matches_company(domain, company_name):
                    continue
                # Skip direct document files — we want IR page URLs, not documents.
                # Finnhub can return PDF links; Serper also surfaces them. Capture the
                # base domain as a fallback so ir_crawler can still crawl the site.
                _DOC_EXTS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")
                if any(link.lower().endswith(ext) for ext in _DOC_EXTS):
                    if not best_base:
                        best_base = f"{parsed.scheme}://{parsed.netloc}"
                    continue
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

    if not best_base:
        if any(sfx in name_lower for sfx in ("limited", " ltd", " ltd.")):
            best_base = "https://www.bseindia.com"
        elif any(sfx in name_lower for sfx in ("a.ş.", "a.s.", "anonim")):
            best_base = "https://www.kap.org.tr"

    return best_base


async def resolve_entity(company_name: str, doc_type: str, year: int) -> dict:
    """Resolve a company name into a full entity dict.

    Returns dict with keys: company_name, normalized_name, country,
                            exchange_mic, isin, ir_url, ticker, ir_url_candidates
    """
    entity = _empty_entity(company_name)

    async with httpx.AsyncClient() as client:
        # ── Step 1: OpenFIGI search ───────────────────────────────────────
        figi_result = await _search_openfigi(client, company_name)

        if figi_result is None:
            normalized = _normalize_name_with_llm(company_name)
            entity["normalized_name"] = normalized
            figi_result = await _search_openfigi(client, normalized)

        if figi_result:
            exch_code = figi_result.get("exchCode", "")
            ticker = figi_result.get("ticker", "")
            entity["ticker"] = ticker
            entity["exchange_mic"] = exch_code
            entity["isin"] = figi_result.get("isin", "") or ""
            if not entity["normalized_name"]:
                entity["normalized_name"] = figi_result.get("name", company_name)
            if not entity["country"] and exch_code:
                entity["country"] = _EXCHCODE_TO_COUNTRY.get(exch_code, "")
            if exch_code == "IB" and ticker.isdigit():
                entity["bse_scripcode"] = ticker
            elif exch_code in ("IN", "NS") and ticker and not ticker.isdigit():
                entity["nse_symbol"] = ticker

        # ── FIX 1 Step 2: Finnhub /search fallback when OpenFIGI returns no exchCode ──
        if not entity["exchange_mic"]:
            search_name = entity.get("normalized_name") or company_name
            fh_match = await _search_finnhub_companies(client, search_name)
            if fh_match:
                fh_exchange = fh_match.get("exchange", "")
                fh_ticker = fh_match.get("symbol") or fh_match.get("displaySymbol") or ""
                fh_mic = _map_finnhub_exchange_to_mic(fh_exchange)
                if fh_mic:
                    entity["exchange_mic"] = fh_mic
                if fh_ticker and not entity["ticker"]:
                    entity["ticker"] = fh_ticker
                if not entity["normalized_name"] and fh_match.get("description"):
                    entity["normalized_name"] = fh_match["description"]

        # ── Step 2: Finnhub profile (by ticker, for weburl + country) ────
        if entity["ticker"]:
            profile = await _get_finnhub_profile(client, entity["ticker"])
            if profile.get("country"):
                entity["country"] = profile["country"]
            if profile.get("weburl"):
                entity["ir_url"] = profile["weburl"]

        # ── Name-based country detection as last resort ───────────────────
        if not entity["country"]:
            entity["country"] = _detect_country_from_name(company_name)

        # ── Ticker-country override for known API misclassifications ──────
        _ticker_up = entity.get("ticker", "").upper()
        if _ticker_up and _ticker_up in TICKER_COUNTRY_OVERRIDE:
            entity["country"] = TICKER_COUNTRY_OVERRIDE[_ticker_up]
            logging.info("[Entity] Ticker country override: %s → %s",
                         _ticker_up, entity["country"])

        # ── FIX 1 Step 3: Country-based MIC inference ────────────────────
        if not entity["exchange_mic"] and entity.get("country"):
            fallback_mic = _COUNTRY_TO_MIC_FALLBACK.get(entity["country"], "")
            if fallback_mic:
                entity["exchange_mic"] = fallback_mic

        # ── Step 3: Serper fallback for ir_url ───────────────────────────
        if not entity["ir_url"]:
            ticker = entity.get("ticker", "")
            if ticker and not ticker.isdigit():
                entity["ir_url"] = await _find_ir_url_via_ticker(client, ticker, company_name)

        if not entity["ir_url"]:
            entity["ir_url"] = await _find_ir_url_via_serper(client, company_name)

        if not entity["ir_url"] and entity.get("country"):
            country_query_name = entity.get("normalized_name") or company_name
            country = entity["country"]
            entity["ir_url"] = await _find_ir_url_via_serper(
                client, f"{country_query_name} {country}"
            )

        # ── Subsidiary detection: RULE 1/2/3 ────────────────────────────────
        # Only fires when a country-TLD mismatch is unambiguous AND the domain
        # contains no evidence of being the correct IR site.
        #
        # RULE 1: Never trigger if ANY of these are true:
        #   - domain is .com (global standard — never evidence of subsidiary)
        #   - domain contains IR keywords (investor / ir. / investors / relations)
        #   - company core name appears in domain
        #   - ticker appears in domain
        #
        # RULE 2: Only trigger if ALL of these are true:
        #   - domain TLD is a known country-specific TLD
        #   - that TLD does not match the company's known country
        #   - (RULE 1 conditions already excluded above)
        #
        # RULE 3: If triggered, search for better URL but keep original as
        #   fallback — only replace if a higher-quality non-subsidiary URL found.
        _sub_ir = entity.get("ir_url", "")
        _sub_country = entity.get("country", "")
        if _sub_ir and _sub_country and SERPER_API_KEY:
            _expected_tlds = COUNTRY_TLD_MAP.get(_sub_country, [])
            if _expected_tlds:
                try:
                    _netloc = urlparse(_sub_ir).netloc.lower()
                    _netloc_flat = _netloc.replace("-", "").replace(".", "")
                    _sub_ticker_l = (entity.get("ticker") or "").lower()

                    # RULE 1 guards — any True → skip subsidiary check entirely
                    _is_dotcom = _netloc.endswith(".com")
                    _has_ir_kw = any(kw in _netloc for kw in
                                     ("investor", "ir.", "investors", "relations"))
                    _name_in_domain = _ir_domain_matches_company(_sub_ir, company_name)
                    _ticker_in_domain = bool(
                        _sub_ticker_l and len(_sub_ticker_l) >= 3
                        and _sub_ticker_l in _netloc_flat
                    )

                    _rule1_ok = (_is_dotcom or _has_ir_kw
                                 or _name_in_domain or _ticker_in_domain)

                    if not _rule1_ok:
                        # RULE 2: check TLD mismatch
                        _tld_ok = any(_netloc.endswith(t) for t in _expected_tlds)
                        if not _tld_ok:
                            logging.warning(
                                "[Entity] Suspected subsidiary domain: %s for %s (%s)"
                                " — searching for parent",
                                _sub_ir, company_name, _sub_country,
                            )
                            _primary_tld = _expected_tlds[0].lstrip(".")
                            _parent_query = (
                                f'"{company_name}" investor relations annual report'
                                f' site:{_primary_tld}'
                            )
                            _headers = {
                                "X-API-KEY": SERPER_API_KEY,
                                "Content-Type": "application/json",
                            }
                            try:
                                _resp = await client.post(
                                    SERPER_URL,
                                    json={"q": _parent_query, "num": 5},
                                    headers=_headers,
                                    timeout=12,
                                )
                                if _resp.status_code == 200:
                                    for _item in _resp.json().get("organic", []):
                                        _link = _item.get("link", "")
                                        if not _link or _ir_domain_is_aggregator(_link):
                                            continue
                                        if _ir_domain_matches_company(_link, company_name):
                                            _parsed = urlparse(_link)
                                            _candidate = (
                                                f"{_parsed.scheme}://{_parsed.netloc}"
                                            )
                                            # RULE 3: replace only when better found;
                                            # if loop ends with no break, original kept
                                            logging.info(
                                                "[Entity] Replaced subsidiary IR URL"
                                                " %s → %s", _sub_ir, _candidate,
                                            )
                                            entity["ir_url"] = _candidate
                                            break
                            except Exception as _se:
                                logging.warning(
                                    "[Entity] Subsidiary search error: %s", _se
                                )
                except Exception:
                    pass

        # ── KNOWN_IR_URLS: deterministic override for known-difficult companies ──
        _name_lower = company_name.lower().strip()
        _known_ir = next(
            (url for key, url in KNOWN_IR_URLS.items() if key in _name_lower),
            "",
        )
        if _known_ir:
            _known_ir = _known_ir.replace("{year}", str(year))  # year-dynamic URLs (e.g. Eskom)
            entity["ir_url"] = _known_ir
            logging.info("[Entity] KNOWN_IR_URLS override: %s -> %s", company_name, _known_ir)

        # ── FIX 2: IR URL validation + CDN variant generation ─────────────
        ir_url = entity.get("ir_url", "")
        _was_rejected = False

        # Reject direct file URLs — Playwright cannot navigate a PDF as an IR page.
        # Finnhub sometimes returns a document URL (e.g. wp-content PDF) as weburl.
        _FILE_EXTS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar")
        if ir_url and any(ir_url.lower().endswith(ext) for ext in _FILE_EXTS):
            logging.warning("[Entity] Rejected IR URL (direct file): %s", ir_url)
            entity["ir_url"] = ""
            ir_url = ""
            _was_rejected = True

        # Reject aggregator domains — site-scoped Serper returns wrong-company docs.
        if ir_url and _ir_domain_is_aggregator(ir_url):
            logging.warning("[Entity] Rejected IR URL (aggregator): %s", ir_url)
            entity["ir_url"] = ""
            ir_url = ""
            _was_rejected = True

        # Reject exchange domains — the exchange hosts filings, not the company's IR page.
        if ir_url and _ir_domain_is_exchange(ir_url):
            logging.warning("[Entity] Rejected exchange domain as IR URL: %s", ir_url)
            entity["ir_url"] = ""
            ir_url = ""
            _was_rejected = True

        # If URL was rejected, search for a proper IR page via Serper.
        if not ir_url and _was_rejected:
            ticker = entity.get("ticker", "")
            if ticker and not ticker.isdigit():
                recovered = await _find_ir_url_via_ticker(client, ticker, company_name)
                if recovered and not _ir_domain_is_aggregator(recovered):
                    entity["ir_url"] = recovered
                    ir_url = recovered
            if not ir_url:
                recovered = await _find_ir_url_via_serper(client, company_name)
                if recovered and not _ir_domain_is_aggregator(recovered):
                    entity["ir_url"] = recovered
                    ir_url = recovered

        logging.info("[Entity] Final IR URL: %s", ir_url or "(none)")

        if ir_url:
            entity["ir_url_candidates"] = _generate_cdn_variants(ir_url)

    return entity


if __name__ == "__main__":
    test_companies = [
        ("Apple Inc", "annual_report", 2024),
        ("Turkcell", "annual_report", 2024),
        ("United Bank for Africa Plc", "annual_report", 2024),
    ]

    async def main():
        for name, doc_type, year in test_companies:
            print(f"\n{'='*55}")
            print(f"Resolving: {name} | {doc_type} | {year}")
            print("=" * 55)
            result = await resolve_entity(name, doc_type, year)
            for k, v in result.items():
                if v:
                    print(f"  {k:22s}: {v}")

    asyncio.run(main())
