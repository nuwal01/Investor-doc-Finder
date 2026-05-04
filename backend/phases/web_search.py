"""
Web Search — generates targeted search queries and finds investor PDFs via Google Custom Search.

Input:  entity dict, doc_type (str), year (int)
Output: dict {url, source, confidence} or None

Pipeline:
  0. Search annualreports.com first (reliable universal source)
  1. Build 6+ specialised Google search queries (fixed templates + native language)
  2. All queries run in parallel against Google Custom Search API
  3. Collected PDF URLs are validated and the best is returned
"""

import asyncio
import json
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.pdf_validator import validate_pdf, doc_type_tier

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SERPER_URL = "https://google.serper.dev/search"
TAVILY_URL = "https://api.tavily.com/search"

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── Search provider credit exhaustion tracking ────────────────────────────────
# These flip to True at runtime when a provider returns 429/402/403.
# They reset on process restart — no persistence needed for dev.
_SERPER_EXHAUSTED = False
_TAVILY_EXHAUSTED = False

DOC_TYPE_LABELS = {
    "annual_report": "annual report",
    "quarterly_report": "quarterly report",
    "investor_presentation": "investor presentation",
}

# ── Multilingual Sector Keywords ─────────────────────────────────────────────

SECTOR_KEYWORDS_MULTILINGUAL = {
    "Financial Services": {
        "en": ["annual report", "financial statements", "investor relations"],
        "ar": ["تقرير سنوي", "البيانات المالية"],
        "ru": ["годовой отчет", "финансовая отчетность"],
        "tr": ["yıllık rapor", "finansal tablolar"],
        "pt": ["relatório anual", "demonstrações financeiras"],
        "fr": ["rapport annuel", "états financiers"],
        "de": ["jahresbericht", "finanzberichte"],
        "es": ["informe anual", "estados financieros"],
        "zh": ["年度报告", "财务报表"],
        "hi": ["वार्षिक रिपोर्ट", "वित्तीय विवरण"],
    },
    "Energy": {
        "en": ["energy", "petroleum", "oil gas"],
        "ar": ["طاقة", "نفط"],
        "ru": ["энергетика", "нефть газ"],
        "tr": ["enerji", "petrol"],
        "pt": ["energia", "petróleo"],
        "es": ["energía", "petróleo"],
        "zh": ["能源", "石油"],
    },
    "Materials": {
        "en": ["materials", "mining", "metals"],
        "ar": ["مواد", "تعدين"],
        "ru": ["материалы", "горнодобывающая"],
        "tr": ["malzeme", "madencilik"],
        "pt": ["materiais", "mineração"],
        "es": ["materiales", "minería"],
        "zh": ["材料", "采矿"],
    },
    "Utilities": {
        "en": ["utilities", "water", "electric"],
        "ar": ["مرافق", "كهرباء"],
        "ru": ["коммунальные услуги", "электричество"],
        "tr": ["kamu hizmetleri", "elektrik"],
    },
    "Telecommunications": {
        "en": ["telecom", "telecommunications", "mobile"],
        "ar": ["اتصالات", "هاتف محمول"],
        "ru": ["телекоммуникации", "мобильная связь"],
        "tr": ["telekomunikasyon", "mobil"],
        "pt": ["telecomunicações", "móvel"],
        "fr": ["télécommunications", "mobile"],
        "zh": ["电信", "移动"],
    },
    "Real Estate": {
        "en": ["real estate", "property", "development"],
        "ar": ["عقارات", "ملكية"],
        "ru": ["недвижимость", "собственность"],
        "tr": ["gayrimenkul", "mülk"],
        "pt": ["imóveis", "propriedade"],
        "fr": ["immobilier", "propriété"],
        "de": ["Immobilien", "Eigentum"],
        "es": ["bienes raíces", "propiedad"],
        "zh": ["房地产", "物业"],
    },
    "Transportation": {
        "en": ["transport", "logistics", "shipping"],
        "ar": ["نقل", "لوجستيات"],
        "ru": ["транспорт", "логистика"],
        "tr": ["taşımacılık", "lojistik"],
        "pt": ["transporte", "logística"],
        "es": ["transporte", "logística"],
        "zh": ["运输", "物流"],
    },
    "Infrastructure": {
        "en": ["infrastructure", "construction", "engineering"],
        "ar": ["بنية تحتية", "إنشاءات"],
        "ru": ["инфраструктура", "строительство"],
        "tr": ["altyapı", "inşaat"],
        "pt": ["infraestrutura", "construção"],
        "zh": ["基础设施", "建设"],
    },
    "Consumer Discretionary": {
        "en": ["consumer", "retail", "automobile"],
        "ar": ["المستهلك", "تجزئة"],
        "ru": ["потребительский", "розничная торговля"],
        "tr": ["tüketici", "perakende"],
        "pt": ["consumidor", "varejo"],
        "es": ["consumidor", "minorista"],
        "zh": ["消费", "零售"],
    },
    "Conglomerate": {
        "en": ["conglomerate", "holding", "group"],
        "ar": ["مجموعة متنوعة", "قابضة"],
        "ru": ["конгломерат", "холдинг"],
        "tr": ["holding", "grup"],
        "pt": ["conglomerado", "holding"],
        "es": ["conglomerado", "grupo empresarial"],
        "zh": ["集团", "控股"],
    },
    "Consumer Staples": {
        "en": ["staples", "food", "beverage"],
        "ar": ["السلع الأساسية", "طعام"],
        "ru": ["товары повседневного спроса", "продукты питания"],
        "tr": ["temel tüketim", "gıda"],
        "pt": ["bens de consumo", "alimentos"],
        "zh": ["消费品", "食品"],
    },
    "Industrials": {
        "en": ["industrial", "manufacturing", "machinery"],
        "ar": ["صناعي", "تصنيع"],
        "ru": ["промышленность", "производство"],
        "tr": ["sanayi", "imalat"],
        "pt": ["industrial", "manufatura"],
        "es": ["industrial", "manufactura"],
        "zh": ["工业", "制造"],
    },
    "Agriculture": {
        "en": ["agriculture", "farming", "agro"],
        "ar": ["زراعة", "مزرعة"],
        "ru": ["сельское хозяйство", "фермерство"],
        "tr": ["tarım", "çiftçilik"],
        "pt": ["agricultura", "fazenda"],
        "es": ["agricultura", "granja"],
        "zh": ["农业", "农场"],
    },
    "Healthcare": {
        "en": ["healthcare", "pharmaceutical", "medical"],
        "ar": ["رعاية صحية", "طبي"],
        "ru": ["здравоохранение", "фармацевтика"],
        "tr": ["sağlık", "ilaç"],
        "pt": ["saúde", "farmacêutico"],
        "fr": ["santé", "pharmaceutique"],
        "de": ["Gesundheit", "pharmazeutisch"],
        "es": ["salud", "farmacéutico"],
        "zh": ["医疗", "制药"],
    },
    "Technology/Media": {
        "en": ["technology", "software", "IT"],
        "ar": ["تقنية", "برمجيات"],
        "ru": ["технологии", "программное обеспечение"],
        "tr": ["teknoloji", "yazılım"],
        "pt": ["tecnologia", "software"],
        "fr": ["technologie", "logiciel"],
        "zh": ["技术", "软件"],
    },
    "Services": {
        "en": ["services", "consulting", "outsourcing"],
        "ar": ["خدمات", "استشارات"],
        "ru": ["услуги", "консалтинг"],
        "tr": ["hizmetler", "danışmanlık"],
        "pt": ["serviços", "consultoria"],
        "es": ["servicios", "consultoría"],
        "fr": ["services", "conseil"],
        "zh": ["服务", "咨询"],
    },
}

_COMPANY_SUFFIXES = frozenset({
    "limited", "ltd", "inc", "corp", "corporation", "group", "plc",
    "llc", "llp", "co", "company", "holdings", "international", "industries",
    "petroleum", "energy", "pipeline",
})

# Subdomain prefixes that are never IR pages — reject during web-search result filtering.
_KNOWN_REJECT_SUBDOMAIN_PREFIXES_WS: tuple[str, ...] = (
    "saude.", "health.", "rh.", "careers.", "jobs.",
    "media.", "news.", "press.", "blog.", "shop.",
    "store.", "ecommerce.", "support.", "help.",
    "mail.", "webmail.", "intranet.", "portal.",
)

_EXCHANGE_DOMAINS: tuple[str, ...] = (
    "nseindia.com", "bseindia.com", "sec.gov",
    "sedar.com", "sgx.com", "kap.org.tr", "dfm.ae", "adx.ae",
)

# Third-party ESG/research publishers — never contain company-official annual reports.
_THIRD_PARTY_RESEARCH_DOMAINS = frozenset({
    "planet-tracker.org", "influencemap.org", "carbontracker.org",
    "shareaction.org", "sustainalytics.com",
})
# Path-scoped rejections for domains that host both ESG and legitimate data.
_THIRD_PARTY_ESG_PATH_PREFIXES: tuple[tuple[str, str], ...] = (
    ("msci.com", "/esg"),
    ("spglobal.com", "/esg"),
)

# FIX 1: identity scoring sets
_LEGAL_SUFFIXES_ID = frozenset({
    "plc", "jsc", "llc", "ltd", "inc", "corp", "corporation", "as", "sa",
    "nv", "bv", "ag", "gmbh", "oy", "ab", "asa", "se", "spa", "srl",
    "pjsc", "oao", "pao", "ojsc", "bhd", "tbk", "limited", "co",
})

_COMMON_GEO_WORDS_ID = frozenset({
    "united", "bank", "group", "holding", "holdings", "company", "companies",
    "international", "national", "global", "general", "africa", "american",
    "americas", "europe", "european", "asia", "asian", "pacific",
    "middle", "east", "north", "south", "west", "china", "india",
    "kingdom", "states", "federal", "for", "and", "the", "of",
})

# Cache for Groq language detection results (company_name.lower() → context dict)
_context_cache: dict[str, dict] = {}


def _extract_core_tokens_ws(company_name: str) -> list[str]:
    """Strip legal suffixes and generic words; return distinctive name tokens."""
    tokens = [t.lower() for t in company_name.split()]
    return [t for t in tokens
            if t not in _LEGAL_SUFFIXES_ID and t not in _COMMON_GEO_WORDS_ID and len(t) > 2]


def _name_acronym(company_name: str) -> str:
    """Derive acronym from significant words: 'United Bank Africa Plc' → 'uba'."""
    ignore = _LEGAL_SUFFIXES_ID
    tokens = [t for t in company_name.split() if len(t) >= 4 and t.lower() not in ignore]
    return "".join(t[0].lower() for t in tokens)


def _company_identity_score_ws(url: str, title: str, snippet: str,
                                company_name: str, ticker: str = "") -> float:
    """Score result identity vs target company.

    Returns 1.0 (domain), 0.5 (title), 0.2 (snippet only), 0.0 (no match → reject).
    When core tokens and ticker are both absent, falls back to name acronym.
    """
    core = _extract_core_tokens_ws(company_name)
    ticker_l = ticker.lower().strip()

    # If all tokens are filtered and no ticker, derive acronym as virtual ticker
    if not core and not ticker_l:
        acronym = _name_acronym(company_name)
        if len(acronym) >= 3:
            ticker_l = acronym
        else:
            return 1.0  # truly no criteria → allow

    try:
        _parsed = urlparse(url)
        domain = _parsed.netloc.lower()
        url_path = _parsed.path.lower()
    except Exception:
        domain = url.lower()
        url_path = ""

    domain_flat = domain.replace("-", "").replace(".", "")
    url_path_flat = url_path.replace("-", "").replace("_", "").replace("/", "")
    title_l = title.lower()
    snippet_l = snippet.lower()

    if ticker_l and len(ticker_l) >= 3 and ticker_l in domain_flat:
        return 1.0
    # Domain check: single-token uses strict prefix rule to prevent "zenith" matching
    # "zenithdrugs.com"; multi-token requires all (or all-but-one for 3+) tokens.
    if core:
        if len(core) == 1:
            _c = core[0]
            _root = domain.split(".")[0].replace("-", "").replace("_", "")
            _exact = (_root == _c)
            # prefix match: "zenithbank" ✓ (diff≤4), "zenithdrugs" ✗ (diff=5)
            _start = _root.startswith(_c) and len(_root) - len(_c) <= 4
            # suffix match: "bankofgeorgia" endswith "georgia" (diff≤7) ✓
            _end = _root.endswith(_c) and len(_root) - len(_c) <= 7
            if _exact or _start or _end:
                return 1.0
        else:
            matched_in_domain = sum(1 for t in core if t in domain)
            required_domain = len(core) if len(core) <= 2 else len(core) - 1
            if matched_in_domain >= required_domain:
                return 1.0

    # Path check — catches exchange URLs where identifier is in filename
    try:
        path = urlparse(url).path.lower().replace("-", "").replace("_", "")
    except Exception:
        path = ""

    if ticker_l and len(ticker_l) >= 3 and ticker_l in path:
        return 1.0
    if core and any(t in path for t in core):
        return 1.0

    if ticker_l and len(ticker_l) >= 3 and ticker_l in title_l:
        return 0.5
    # Title: single-token returns 0.4 (below >=0.5 collection threshold) so only domain-matched
    # results are collected for ambiguous names like "Zenith"; multi-token requires ALL tokens.
    if core:
        if len(core) == 1:
            if re.search(r'\b' + re.escape(core[0]) + r'\b', title_l):
                return 0.4  # intentionally below threshold — domain match required
        elif all(t in title_l for t in core):
            return 0.5
    if ticker_l and len(ticker_l) >= 3 and ticker_l in snippet_l:
        return 0.2
    if core and any(t in snippet_l for t in core):
        return 0.2
    # URL path check: aggregator sites (annualreports.com) embed the ticker/name in the
    # file path rather than the domain — e.g. NASDAQ_AAPL_2023.pdf.
    if ticker_l and len(ticker_l) >= 3 and ticker_l in url_path_flat:
        return 0.5
    if core and all(t in url_path_flat for t in core):
        return 0.5
    if core and any(t in url_path_flat for t in core):
        return 0.2
    return 0.0  # no match → reject


def detect_region(company_name: str, country: str) -> str:
    """Classify company region for targeted extra search queries.

    Returns one of: "india", "uae", "turkey", "uk", "us", "global"
    """
    name_lower = company_name.lower()
    c = country.upper()
    # UAE first — PJSC companies can also use "limited"
    if c == "AE" or any(kw in name_lower for kw in (
            "pjsc", "p.j.s.c", "dubai", "abu dhabi", "emaar", "adnoc",
            "emirates nbd", "dib", "etisalat", "du telecom")):
        return "uae"
    # India
    if c == "IN" or any(sfx in name_lower for sfx in (
            " limited", " ltd", " industries", " enterprises",
            " pharmaceuticals", "infosys", "wipro", "reliance", "tata")):
        return "india"
    # Turkey
    if c == "TR" or "a.ş" in name_lower:
        return "turkey"
    if c == "GB":
        return "uk"
    if c == "US":
        return "us"
    return "global"


# ── 0. annualreports.com source ──────────────────────────────────────────────

async def search_annualreports_com(
    company_name: str, doc_type: str, year: int,
) -> dict | None:
    """Search annualreports.com for the company's annual report PDF.

    Steps:
      1. Serper: site:annualreports.com "{company_name}" {year}
      2. Fetch the company page found
      3. Parse for PDF download links (prefer year-matching)
      4. Validate and return if score > 0.2
    """
    if not SERPER_API_KEY:
        return None

    query = f'site:annualreports.com "{company_name}" {year}'

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Step 1: find the company page on annualreports.com via Serper
        try:
            resp = await client.post(
                SERPER_URL,
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
                timeout=15,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception:
            return None

        company_page_url = None
        for item in data.get("organic", []):
            link = item.get("link", "")
            if "annualreports.com" in link:
                company_page_url = link
                break

        if not company_page_url:
            return None

        # Step 2: fetch the company page
        try:
            page_resp = await client.get(
                company_page_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if page_resp.status_code != 200:
                return None
        except Exception:
            return None

        # Step 3: parse for PDF/download links
        soup = BeautifulSoup(page_resp.text, "lxml")
        year_str = str(year)
        pdf_url = None

        # First pass: look for links that mention the target year
        for a in soup.find_all("a", href=True):
            href = a["href"]
            href_lower = href.lower()
            link_text = (a.get_text() or "").strip()
            if ".pdf" in href_lower or "download" in href_lower:
                if year_str in href or year_str in link_text:
                    if href.startswith("http"):
                        pdf_url = href
                    else:
                        pdf_url = "https://www.annualreports.com" + href
                    break

        # Second pass: first .pdf link on page
        if not pdf_url:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if ".pdf" in href.lower():
                    pdf_url = href if href.startswith("http") else "https://www.annualreports.com" + href
                    break

        if not pdf_url:
            return None

        # Step 4: validate
        score = await validate_pdf(pdf_url, company_name, year, doc_type)
        if score > 0.2:
            return {
                "url": pdf_url,
                "source": "annualreports.com",
                "confidence": "medium",
                "score": score,
            }

    return None


# ── 1. Language detection via Groq ───────────────────────────────────────────

async def detect_company_context(company_name: str) -> dict:
    """Use Groq to detect the company's country and native annual report term.

    Returns a dict with keys: country_code, language,
    native_annual_report_term, native_quarterly_report_term.
    Results are cached per company name.
    """
    cache_key = company_name.lower().strip()
    if cache_key in _context_cache:
        return _context_cache[cache_key]

    default = {
        "country_code": "",
        "language": "english",
        "native_annual_report_term": "",
        "native_quarterly_report_term": "",
    }

    if not GROQ_API_KEY:
        return default

    try:
        from groq import Groq

        prompt = (
            f'What country is this company most likely from based on its name? '
            f'What is the native language term for "annual report" in that country\'s language?\n\n'
            f'Company name: {company_name}\n\n'
            f'Respond in JSON only, no extra text:\n'
            f'{{"country_code":"2 letter ISO code","language":"english name of language",'
            f'"native_annual_report_term":"term in native language",'
            f'"native_quarterly_report_term":"term in native language"}}'
        )

        groq_client = Groq(api_key=GROQ_API_KEY)
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        text = resp.choices[0].message.content.strip()

        # Extract JSON from response
        if "{" in text and "}" in text:
            text = text[text.index("{") : text.rindex("}") + 1]
        result = {**default, **json.loads(text)}
        _context_cache[cache_key] = result
        return result
    except Exception:
        return default


# ── 2a. Multilingual query generation via Groq ──────────────────────────────

async def generate_multilingual_queries(
    company_name: str, doc_type: str, year: int, country: str, sector: str = ""
) -> list[str]:
    """Generate 4 search queries in native language + English via Groq Llama 3.3 70B.

    Uses country and sector context to generate queries in the appropriate languages
    with sector-specific keywords for better regional and industry-specific results.

    Args:
        company_name: Company name
        doc_type: Document type (annual_report, etc.)
        year: Target year
        country: ISO country code (e.g., "IN", "AE", "TR")
        sector: Business sector (e.g., "Energy", "Financial Services")

    Returns:
        List of 4 multilingual search queries optimized for the company's region and sector
    """
    if not GROQ_API_KEY:
        return []

    try:
        from groq import Groq

        doc_label = DOC_TYPE_LABELS.get(doc_type, "annual report")

        # Build sector context for the prompt
        sector_context = f"\nSector: {sector}" if sector else ""

        # Get sector keywords for this sector if available
        sector_keywords = ""
        if sector and sector in SECTOR_KEYWORDS_MULTILINGUAL:
            keywords_dict = SECTOR_KEYWORDS_MULTILINGUAL[sector]
            # Include first 2 keyword sets from the sector
            sample_keywords = list(keywords_dict.items())[:2]
            if sample_keywords:
                sector_keywords = "\nSector keywords: " + ", ".join(
                    f"{lang}: {'/'.join(kws)}" for lang, kws in sample_keywords
                )

        prompt = (
            f'Generate 4 Google search queries to find the {year} {doc_label} PDF for this company:\n\n'
            f'Company: {company_name}\n'
            f'Country: {country}{sector_context}{sector_keywords}\n'
            f'Year: {year}\n\n'
            f'Instructions:\n'
            f'- ALWAYS put the English query FIRST (index 0 and 1)\n'
            f'- Put the native language query SECOND (index 2 and 3)\n'
            f'- For UAE (AE): queries 0-1 in English, queries 2-3 in Arabic\n'
            f'- For Turkey (TR): queries 0-1 in English, queries 2-3 in Turkish\n'
            f'- For India (IN): all queries in English (primary business language)\n'
            f'- For Russia (RU): queries 0-1 in English, queries 2-3 in Russian\n'
            f'- For Brazil (BR): queries 0-1 in English, queries 2-3 in Portuguese\n'
            f'- For Saudi Arabia (SA): queries 0-1 in English, queries 2-3 in Arabic\n'
            f'- For China (CN): queries 0-1 in English, queries 2-3 in Chinese\n'
            f'- Include sector-specific terms if sector is provided\n'
            f'- Use filetype:pdf and site: operators strategically\n\n'
            f'Return as JSON array only, no extra text:\n'
            f'["english query 1", "english query 2", "native query 3", "native query 4"]'
        )

        groq_client = Groq(api_key=GROQ_API_KEY)
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()

        # Extract JSON array from response
        if "[" in text and "]" in text:
            text = text[text.index("[") : text.rindex("]") + 1]
            queries = json.loads(text)
            if isinstance(queries, list):
                return [q for q in queries if isinstance(q, str) and q.strip()]
    except Exception:
        pass

    return []


# ── 2b. Generate search queries ──────────────────────────────────────────────

async def generate_search_queries(company_name: str, doc_type: str, year: int) -> list[str]:
    """Build 6+ targeted Google queries using the exact requested year.

    Query 1-6 are fixed templates guaranteed to use the user-supplied year.
    Native-language extras are appended when Groq detects a non-English company.
    """
    doc_label = DOC_TYPE_LABELS.get(doc_type, "annual report")
    year_minus_1 = year - 1
    # fiscal-year short form, e.g. "2022-23" — useful for Indian companies
    fy_short = f"{year_minus_1}-{str(year)[2:]}"

    queries = [
        # Q1: exact name + doc type + year — highest precision
        f'"{company_name}" {doc_label} {year} filetype:pdf',
        # Q2: quoted name + year first — catches different orderings
        f'"{company_name}" {year} {doc_label} PDF',
        # Q3: unquoted + AR abbreviation + download
        f'{company_name} {year} AR PDF download',
        # Q4: fiscal-year range format (e.g. 2022-23) — important for India
        f'{company_name} {doc_label} {fy_short} filetype:pdf',
        # Q5: site-restricted to major filing archives
        f'{company_name} {year} {doc_label} site:sec.gov OR site:bseindia.com OR site:sedar.com',
        # Q6: archive keyword — helps find older reports in company archive sections
        f'{company_name} {year} {doc_label} archive PDF',
    ]

    # Add native-language queries via Groq (cached per company)
    context = await detect_company_context(company_name)
    native_term = context.get("native_annual_report_term", "").strip()
    if native_term and native_term.lower() not in ("", "annual report"):
        queries.append(f'{company_name} {native_term} {year} filetype:pdf')
        queries.append(f'{company_name} {year} {native_term} PDF download')

    # Add region-specific queries
    country_code = context.get("country_code", "")
    region = detect_region(company_name, country_code)

    if region == "india":
        queries += [
            f'site:bseindia.com "{company_name}" {year}',
            f'site:nseindia.com "{company_name}" {year}',
            f'"{company_name}" {fy_short} annual report filetype:pdf',
            f'"{company_name}" BSE annual report {year} PDF download',
        ]
    elif region == "uae":
        queries += [
            f'site:dfm.ae "{company_name}" {year}',
            f'site:adx.ae "{company_name}" {year}',
            f'"{company_name}" PJSC "{year}" annual report filetype:pdf',
            f'"{company_name}" Emirates annual report {year} PDF',
        ]

    return queries


# ── 3. Run a single query — Serper → Tavily fallback ─────────────────────────

import logging as _logging

def _notify_admin_search_exhausted(provider: str) -> None:
    _logging.critical(
        "[ADMIN ALERT] Search provider '%s' is exhausted. "
        "All search providers are down — web search phase is disabled. "
        "Top up Serper at serper.dev or Tavily at tavily.com.",
        provider,
    )
    if not all([ADMIN_EMAIL, SMTP_FROM, SMTP_PASSWORD]):
        return
    try:
        msg = MIMEText(
            f"Search provider '{provider}' is exhausted on Investor Doc Finder.\n\n"
            f"Web search phase is now disabled until credits are topped up.\n\n"
            f"- Top up Serper at serper.dev\n"
            f"- Top up Tavily at tavily.com"
        )
        msg["Subject"] = f"[IDF ALERT] {provider} search credits exhausted"
        msg["From"] = SMTP_FROM
        msg["To"] = ADMIN_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_FROM, SMTP_PASSWORD)
            smtp.send_message(msg)
        _logging.info("[ADMIN ALERT] Email sent to %s", ADMIN_EMAIL)
    except Exception as e:
        _logging.error("[ADMIN ALERT] Email send failed: %s", e)


async def _query_serper(
    client: httpx.AsyncClient, query: str
) -> list[tuple[str, str, str]] | None:
    """POST query to Serper. Returns results or None if exhausted/failed."""
    global _SERPER_EXHAUSTED
    if _SERPER_EXHAUSTED or not SERPER_API_KEY:
        return None
    try:
        resp = await client.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 10},
            timeout=15,
        )
        if resp.status_code in (402, 429, 403):
            _logging.warning("[Serper] Credits exhausted (HTTP %d). Switching to Tavily.", resp.status_code)
            _SERPER_EXHAUSTED = True
            return None
        if resp.status_code != 200:
            _logging.warning("[Serper] HTTP %d for query: %s", resp.status_code, query[:80])
            return []
    except Exception as e:
        _logging.warning("[Serper] Request failed: %s", e)
        return []

    data = resp.json()
    results = []
    for item in data.get("organic", []):
        link = item.get("link", "")
        if link and (".pdf" in link.lower() or "pdf" in link.lower()):
            results.append((link, item.get("title", ""), item.get("snippet", "")))
    return results


async def _query_tavily(
    client: httpx.AsyncClient, query: str
) -> list[tuple[str, str, str]] | None:
    """POST query to Tavily. Returns results or None if exhausted/failed."""
    global _TAVILY_EXHAUSTED
    if _TAVILY_EXHAUSTED or not TAVILY_API_KEY:
        return None
    try:
        resp = await client.post(
            TAVILY_URL,
            headers={"Content-Type": "application/json"},
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 10,
                "include_raw_content": False,
            },
            timeout=15,
        )
        if resp.status_code in (402, 429, 403):
            _logging.warning("[Tavily] Credits exhausted (HTTP %d).", resp.status_code)
            _TAVILY_EXHAUSTED = True
            return None
        if resp.status_code != 200:
            _logging.warning("[Tavily] HTTP %d for query: %s", resp.status_code, query[:80])
            return []
    except Exception as e:
        _logging.warning("[Tavily] Request failed: %s", e)
        return []

    data = resp.json()
    results = []
    for item in data.get("results", []):
        link = item.get("url", "")
        if link and (".pdf" in link.lower() or "pdf" in link.lower()):
            results.append((link, item.get("title", ""), item.get("content", "")))
    return results


async def run_serper_query(
    client: httpx.AsyncClient, query: str
) -> list[tuple[str, str, str]]:
    """Run a single search query with Serper → Tavily fallback.

    Returns (url, title, snippet) tuples for PDF results.
    Fires admin alert if both providers are exhausted.
    """
    # Try Serper first
    serper_result = await _query_serper(client, query)
    if serper_result is not None:
        return serper_result

    # Serper exhausted or missing — try Tavily
    tavily_result = await _query_tavily(client, query)
    if tavily_result is not None:
        return tavily_result

    # Both exhausted
    if _SERPER_EXHAUSTED and _TAVILY_EXHAUSTED:
        _notify_admin_search_exhausted("Tavily")

    return []


# ── 3b. EDGAR HTM → PDF resolver ─────────────────────────────────────────────

async def resolve_edgar_htm_to_pdf(client: httpx.AsyncClient, htm_url: str) -> str | None:
    """If url is an EDGAR filing index page, find the primary PDF inside it."""
    try:
        resp = await client.get(htm_url, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".pdf"):
                if href.startswith("http"):
                    return href
                return "https://www.sec.gov" + href
    except Exception:
        return None
    return None


# ── 4. Orchestrator ──────────────────────────────────────────────────────────

async def run_web_search(entity: dict, doc_type: str, year: int, sector: str = "") -> dict | None:
    """Search annualreports.com first, then run parallel Google CSE queries with multilingual support.

    Runs standard queries + Groq multilingual queries (with sector context) in parallel.

    Args:
        entity: Entity dict with company_name, country, etc.
        doc_type: Document type
        year: Target year
        sector: Business sector (optional, improves query relevance)

    Returns: {url, source, confidence, score} or None
    """
    company_name = entity.get("company_name", "")
    if not company_name:
        return None

    country = entity.get("country", "")
    ticker = entity.get("ticker", "")
    ir_url_entity = entity.get("ir_url", "")
    try:
        _ir_netloc_ws = urlparse(ir_url_entity).netloc.lower().lstrip("www.") if ir_url_entity else ""
    except Exception:
        _ir_netloc_ws = ""

    # Step 0: annualreports.com (most reliable for listed companies)
    ar_result = await search_annualreports_com(company_name, doc_type, year)
    if ar_result and ar_result["score"] >= 0.5:
        # FIX 1: identity check — annualreports.com can return wrong-company results
        if _company_identity_score_ws(ar_result["url"], "", "", company_name, ticker) > 0.0:
            return ar_result
        ar_result = None  # wrong company — fall through to Google CSE

    # Step 1: generate queries in parallel (standard + multilingual via Groq)
    # Pre-seed context cache with entity country so detect_region works without extra API call
    _context_cache.setdefault(company_name.lower().strip(), {})["country_code"] = country

    # Run both query generation methods in parallel
    standard_queries_task = asyncio.create_task(generate_search_queries(company_name, doc_type, year))
    multilingual_queries_task = asyncio.create_task(
        generate_multilingual_queries(company_name, doc_type, year, country, sector)
    )

    standard_queries, multilingual_queries = await asyncio.gather(
        standard_queries_task, multilingual_queries_task, return_exceptions=True
    )

    # Combine queries (handle exceptions)
    queries = []
    if isinstance(standard_queries, list):
        queries.extend(standard_queries)
    if isinstance(multilingual_queries, list):
        queries.extend(multilingual_queries)

    if not queries:
        return ar_result

    # Step 2: run all queries in parallel against Google CSE
    async with httpx.AsyncClient() as client:
        tasks = [run_serper_query(client, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # FIX 4: collect URLs with language tag for English-first ranking
    _EN_URL_KW = ("english", "_en_", "-en-", "_en.", "-en.", "eng_", "_eng", "english-version")
    _NON_EN_URL_KW = (
        "arabic", "_ar_", "_ar.", "-ar-", "uzbek", "_uz_", "russian", "_ru_", "_ru.",
        "turkish", "_tr_", "_tr.", "chinese", "_cn_", "french", "_fr_", "german", "_de_",
    )

    seen: set[str] = set()
    pending: list[tuple[str, str]] = []  # (url, "en" | "other")
    for result in results:
        if isinstance(result, Exception):
            continue
        for url, title, snippet in result:
            if url not in seen:
                # Reject third-party ESG/research publishers
                try:
                    _r_netloc = urlparse(url).netloc.lower().lstrip("www.")
                    _r_path = urlparse(url).path.lower()
                except Exception:
                    _r_netloc, _r_path = "", ""
                if any(d in _r_netloc for d in _THIRD_PARTY_RESEARCH_DOMAINS):
                    continue
                if any(_r_netloc.endswith(d) and _r_path.startswith(p)
                       for d, p in _THIRD_PARTY_ESG_PATH_PREFIXES):
                    continue
                if any(_r_netloc.startswith(p) for p in _KNOWN_REJECT_SUBDOMAIN_PREFIXES_WS):
                    continue

                id_score = _company_identity_score_ws(url, title, snippet, company_name, ticker)
                # URLs from the entity's known IR domain are always trusted, even when the
                # published report uses a parent-company name (e.g. Cementos Argos → grupoargos.com).
                try:
                    _url_netloc_ws = urlparse(url).netloc.lower().lstrip("www.")
                except Exception:
                    _url_netloc_ws = ""
                from_ir_domain = bool(
                    _ir_netloc_ws and (
                        _ir_netloc_ws in _url_netloc_ws or _url_netloc_ws.endswith(_ir_netloc_ws)
                    )
                )
                from_exchange = any(d in _r_netloc for d in _EXCHANGE_DOMAINS)
                if from_ir_domain or from_exchange or id_score >= 0.5:
                    seen.add(url)
                    url_lower = url.lower()
                    if any(kw in url_lower for kw in _EN_URL_KW):
                        bucket = "en"
                    elif any(kw in url_lower for kw in _NON_EN_URL_KW):
                        bucket = "other"
                    else:
                        bucket = "en"  # treat unknown as neutral/English
                    pending.append((url, bucket))

    # Resolve EDGAR .htm/.html filing index pages → primary PDF (in parallel).
    # Any URL that fails to resolve is dropped before validation.
    async def _maybe_resolve(client: httpx.AsyncClient, u: str) -> str | None:
        u_lower = u.lower()
        if "sec.gov" in u_lower and (u_lower.endswith(".htm") or u_lower.endswith(".html")):
            return await resolve_edgar_htm_to_pdf(client, u)
        return u

    english_urls: list[str] = []
    other_urls: list[str] = []
    if pending:
        async with httpx.AsyncClient(follow_redirects=True) as _resolver_client:
            resolved = await asyncio.gather(
                *[_maybe_resolve(_resolver_client, u) for u, _ in pending],
                return_exceptions=True,
            )
        buckets = [b for _, b in pending]
        for bucket, final_url in zip(buckets, resolved):
            if isinstance(final_url, Exception) or final_url is None:
                continue
            if bucket == "en":
                english_urls.append(final_url)
            else:
                other_urls.append(final_url)

    # English URLs ranked before non-English
    all_urls = english_urls + other_urls

    if not all_urls:
        # If annualreports.com found something (even weak), return it
        return ar_result

    # Step 3: validate and pick best (pass ir_url so IR-domain URLs get source_score bonus)
    scores = await asyncio.gather(
        *[validate_pdf(url, company_name, year, doc_type, ir_url_entity) for url in all_urls],
        return_exceptions=True,
    )

    # FIX 2: tier-preference selection — TIER 1 beats TIER 2 regardless of score
    best_url = None
    best_score = 0.0
    best_tier = 3
    for url, score in zip(all_urls, scores):
        if isinstance(score, Exception) or score <= 0.0:
            continue
        tier = doc_type_tier(url, doc_type)
        if tier < best_tier or (tier == best_tier and score > best_score):
            best_tier = tier
            best_score = score
            best_url = url

    # Compare with annualreports.com result (tier-aware)
    if ar_result and ar_result["score"] > 0.0:
        ar_tier = doc_type_tier(ar_result["url"], doc_type)
        if ar_tier < best_tier or (ar_tier == best_tier and ar_result["score"] > best_score):
            return ar_result

    if best_url and best_score > 0.3:
        # Extra gate: reject generic PDFs with no URL-level signal.
        # year_in_url is intentionally excluded: a publication that merely has "2024"
        # in its date-path (e.g. a newsletter) should not bypass this gate.
        url_lower_final = best_url.lower()
        company_words = [w for w in company_name.lower().split() if len(w) > 3
                         and w not in ("limited", "group", "holdings", "industries")]
        company_in_url = any(w in url_lower_final for w in company_words)
        annual_in_url = any(kw in url_lower_final for kw in
                            ("annual", "/ar/", "_ar.", "annualreport", "annual-report",
                             "ar20", "ar_20", "annrep"))
        # IR-domain URLs always pass (company_in_url covers these via domain netloc check)
        from_ir = bool(_ir_netloc_ws and _ir_netloc_ws in url_lower_final)
        # Official exchange/filing domains host PDFs with opaque hash-based paths (e.g. BSE,
        # NSE, SEC EDGAR) that contain no company name or doc-type keyword — bypass the gate.
        try:
            _url_netloc_final = urlparse(best_url).netloc.lower().lstrip("www.")
        except Exception:
            _url_netloc_final = ""
        _OFFICIAL_FILING_DOMAINS = (
            "sec.gov", "bseindia.com", "nseindia.com", "archives.nseindia.com",
            "nsearchives.nseindia.com", "kap.org.tr",
            "dfm.ae", "feeds.dfm.ae", "adx.ae", "apigateway.adx.ae",
            "saudiexchange.sa", "bursamalaysia.com", "sgx.com",
            "set.or.th", "jse.co.za", "ngxgroup.com", "stockex.co.tt", "jamstockex.com",
        )
        from_official_filing = any(
            _url_netloc_final == d or _url_netloc_final.endswith("." + d)
            for d in _OFFICIAL_FILING_DOMAINS
        )
        has_url_signal = company_in_url or annual_in_url or from_ir or from_official_filing
        if not has_url_signal:
            return ar_result
        return {"url": best_url, "source": "Web Search", "confidence": "low", "score": best_score}

    return ar_result  # May be None or a low-scoring fallback


if __name__ == "__main__":
    test_cases = [
        (
            {
                "company_name": "Apple",
                "normalized_name": "APPLE INC",
                "country": "US",
                "exchange_mic": "XNAS",
                "isin": "",
                "ir_url": "https://investor.apple.com",
                "ticker": "AAPL",
            },
            "annual_report",
            2023,
        ),
        (
            {
                "company_name": "Krishana Phoschem Limited",
                "normalized_name": "Krishana Phoschem Ltd",
                "country": "IN",
                "exchange_mic": "",
                "isin": "",
                "ir_url": "https://www.krishnaphoschem.com",
                "ticker": "",
            },
            "annual_report",
            2023,
        ),
        (
            {
                "company_name": "Sony",
                "normalized_name": "Sony Group Corp",
                "country": "JP",
                "exchange_mic": "XTKS",
                "isin": "",
                "ir_url": "",
                "ticker": "SONY",
            },
            "annual_report",
            2022,
        ),
    ]

    async def main():
        for entity, doc_type, year in test_cases:
            name = entity["company_name"]
            print(f"\n{'='*60}")
            print(f"  {name} | {doc_type} | {year}")
            print("=" * 60)
            result = await run_web_search(entity, doc_type, year)
            if result:
                print(f"  URL   : {result['url'][:100]}")
                print(f"  Source: {result['source']}")
                print(f"  Conf  : {result['confidence']}")
                print(f"  Score : {result['score']:.2f}")
            else:
                print("  No PDF found via web search")

    asyncio.run(main())