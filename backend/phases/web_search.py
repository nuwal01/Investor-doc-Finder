"""
Web Search — generates targeted search queries and finds investor PDFs via Serper.

Input:  entity dict, doc_type (str), year (int)
Output: dict {url, source, confidence} or None

Pipeline:
  0. Search annualreports.com first (reliable universal source)
  1. Build 6+ specialised Google search queries (fixed templates + native language)
  2. All queries run in parallel against Serper API
  3. Collected PDF URLs are validated and the best is returned
"""

import asyncio
import json
import os
import sys

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.pdf_validator import validate_pdf

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SERPER_URL = "https://google.serper.dev/search"

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

# Cache for Groq language detection results (company_name.lower() → context dict)
_context_cache: dict[str, dict] = {}


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


def _has_company_word_in_content(url: str, title: str, snippet: str, company_name: str) -> bool:
    """Return True if at least one significant company name word appears in URL or title.

    Snippet is excluded: it often mentions unrelated companies as comparisons,
    causing false positives for obscure companies.
    """
    words = [
        w.lower() for w in company_name.split()
        if len(w) > 3 and w.lower() not in _COMPANY_SUFFIXES
    ]
    if not words:
        return True  # No meaningful words to filter on
    # Check URL and title only (stronger signals)
    url_and_title = (url + " " + title).lower()
    return any(w in url_and_title for w in words)


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
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Step 1: find the company page on annualreports.com
        try:
            resp = await client.post(
                SERPER_URL, json={"q": query, "num": 5}, headers=headers, timeout=15,
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


# ── 3. Run a single Serper query ─────────────────────────────────────────────

async def run_serper_query(client: httpx.AsyncClient, query: str) -> list[tuple[str, str, str]]:
    """POST a query to Serper and return (url, title, snippet) tuples for PDF results."""
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": 10}

    try:
        resp = await client.post(SERPER_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    data = resp.json()
    results = []
    for item in data.get("organic", []):
        link = item.get("link", "")
        if link and (".pdf" in link.lower() or "pdf" in link.lower()):
            results.append((
                link,
                item.get("title", ""),
                item.get("snippet", ""),
            ))

    return results


# ── 4. Orchestrator ──────────────────────────────────────────────────────────

async def run_web_search(entity: dict, doc_type: str, year: int, sector: str = "") -> dict | None:
    """Search annualreports.com first, then run parallel Serper queries with multilingual support.

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

    # Step 0: annualreports.com (most reliable for listed companies)
    ar_result = await search_annualreports_com(company_name, doc_type, year)
    if ar_result and ar_result["score"] >= 0.5:
        return ar_result

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

    # Step 2: run all queries in parallel against Serper
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
    english_urls: list[str] = []
    other_urls: list[str] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        for url, title, snippet in result:
            if url not in seen and _has_company_word_in_content(url, title, snippet, company_name):
                seen.add(url)
                url_lower = url.lower()
                if any(kw in url_lower for kw in _EN_URL_KW):
                    english_urls.append(url)
                elif any(kw in url_lower for kw in _NON_EN_URL_KW):
                    other_urls.append(url)
                else:
                    english_urls.append(url)  # treat unknown as neutral/English

    # English URLs ranked before non-English
    all_urls = english_urls + other_urls

    if not all_urls:
        # If annualreports.com found something (even weak), return it
        return ar_result

    # Step 3: validate and pick best
    scores = await asyncio.gather(
        *[validate_pdf(url, company_name, year, doc_type) for url in all_urls],
        return_exceptions=True,
    )

    best_url = None
    best_score = 0.0
    for url, score in zip(all_urls, scores):
        if isinstance(score, Exception):
            continue
        if score > best_score:
            best_score = score
            best_url = url

    # Compare with annualreports.com result
    if ar_result and ar_result["score"] > best_score:
        return ar_result

    if best_url and best_score > 0.3:
        # Extra gate: reject generic PDFs with no URL-level signal.
        # A URL that has no company name, no year, and no annual keyword in the path
        # is almost certainly a false positive from an off-topic Serper result.
        url_lower_final = best_url.lower()
        company_words = [w for w in company_name.lower().split() if len(w) > 3
                         and w not in ("limited", "group", "holdings", "industries")]
        company_in_url = any(w in url_lower_final for w in company_words)
        year_in_url = str(year) in url_lower_final
        annual_in_url = any(kw in url_lower_final for kw in
                            ("annual", "/ar/", "_ar.", "annualreport", "annual-report",
                             "ar20", "ar_20", "annrep"))
        has_url_signal = company_in_url or year_in_url or annual_in_url
        if not has_url_signal and best_score < 0.7:
            # No reliable URL signal → don't return a likely false positive
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
