"""
Query Parser — parses raw user queries into structured search parameters.

Input:  raw string like "Reliance Industries annual report 2023"
Output: dict {company_name, doc_type, year, raw_query}
"""

import re
import os
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

VALID_DOC_TYPES = ["annual_report", "quarterly_report", "investor_presentation"]

# ── Sector Detection Keywords ────────────────────────────────────────────────

SECTOR_KEYWORDS = {
    "Financial Services": ["bank", "financial", "insurance", "fund", "capital", "asset management",
                           "investment", "securities", "credit", "finance", "banking"],
    "Energy": ["energy", "oil", "gas", "petroleum", "coal", "power", "electricity", "solar",
               "wind", "renewable", "nuclear", "utility"],
    "Materials": ["materials", "mining", "metals", "steel", "aluminum", "copper", "chemicals",
                  "cement", "paper", "forestry", "mining"],
    "Utilities": ["utilities", "water", "electric", "gas distribution", "utility"],
    "Telecommunications": ["telecom", "telecommunications", "mobile", "broadband", "wireless",
                           "communications", "tower", "network"],
    "Real Estate": ["real estate", "property", "reit", "land", "development", "construction"],
    "Transportation": ["transport", "logistics", "shipping", "airline", "railway", "port",
                       "freight", "cargo", "delivery"],
    "Infrastructure": ["infrastructure", "construction", "engineering", "roads", "highways",
                       "bridges", "ports", "airports"],
    "Consumer Discretionary": ["consumer", "retail", "automobile", "auto", "automotive", "hotel",
                               "restaurant", "entertainment", "media", "apparel", "luxury"],
    "Conglomerate": ["conglomerate", "holding", "group", "diversified", "holdings"],
    "Consumer Staples": ["staples", "food", "beverage", "grocery", "fmcg", "consumer goods",
                         "packaged goods", "tobacco", "household"],
    "Industrials": ["industrial", "manufacturing", "machinery", "equipment", "defense",
                    "aerospace", "electrical", "automation"],
    "Agriculture": ["agriculture", "farming", "agro", "crop", "fertilizer", "seeds", "dairy",
                    "livestock", "plantation"],
    "Healthcare": ["healthcare", "pharmaceutical", "pharma", "biotech", "medical", "hospital",
                   "diagnostics", "drugs", "medicine", "health"],
    "Technology/Media": ["technology", "software", "IT", "internet", "tech", "digital", "cloud",
                         "semiconductor", "electronics", "media", "telecom"],
    "Services": ["services", "consulting", "outsourcing", "BPO", "staffing", "education",
                 "training", "hospitality"],
}

# Keyword → doc_type mapping
DOC_TYPE_KEYWORDS = {
    "annual_report": [
        "annual report", "annual-report", "yearly report", "10-k", "10k",
        "annual filing", "annual results",
    ],
    "quarterly_report": [
        "quarterly report", "quarterly-report", "quarter report", "10-q", "10q",
        "quarterly results", "quarterly filing", "q1", "q2", "q3", "q4",
    ],
    "investor_presentation": [
        "investor presentation", "investor deck", "earnings presentation",
        "investor ppt", "corporate presentation", "earnings call presentation",
        "investor day", "analyst presentation",
    ],
}

# Flattened list of all keywords for stripping from company name
ALL_DOC_KEYWORDS = []
for keywords in DOC_TYPE_KEYWORDS.values():
    ALL_DOC_KEYWORDS.extend(keywords)


def _extract_year(query: str) -> tuple[int | None, str]:
    """Extract a 4-digit year (1900-2099) from the query.
    Returns (year, query_with_year_removed)."""
    match = re.search(r"\b(19|20)\d{2}\b", query)
    if match:
        year = int(match.group())
        cleaned = query[: match.start()] + query[match.end() :]
        return year, cleaned.strip()
    return None, query


def _match_doc_type(query: str) -> str | None:
    """Try keyword matching to determine doc_type. Returns None if ambiguous."""
    query_lower = query.lower()
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in query_lower:
                return doc_type
    return None


def _classify_with_llm(query: str) -> str:
    """Use Groq llama-3.3-70b-versatile to classify the doc_type."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = (
        "Classify the following investor query into exactly one document type.\n"
        "Valid types: annual_report, quarterly_report, investor_presentation\n"
        "Reply with ONLY the document type, nothing else.\n\n"
        f"Query: {query}"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=20,
    )

    result = response.choices[0].message.content.strip().lower()

    # Validate the LLM response
    if result in VALID_DOC_TYPES:
        return result
    # Fallback: default to annual_report
    return "annual_report"


def _detect_sector(query: str, company_name: str) -> str:
    """Detect the business sector from the query or company name.

    Returns the sector name or empty string if not detected.
    """
    combined = f"{query.lower()} {company_name.lower()}"

    # Count matches for each sector
    sector_scores = {}
    for sector, keywords in SECTOR_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > 0:
            sector_scores[sector] = matches

    # Return sector with most matches, or empty string
    if sector_scores:
        return max(sector_scores, key=sector_scores.get)
    return ""


def _extract_company_name(query: str) -> str:
    """Remove year and doc-type keywords from the query to isolate the company name."""
    # Remove year
    cleaned = re.sub(r"\b(19|20)\d{2}\b", "", query)

    # Remove doc type keywords (longest first to avoid partial matches)
    sorted_keywords = sorted(ALL_DOC_KEYWORDS, key=len, reverse=True)
    for kw in sorted_keywords:
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    # Clean up extra whitespace and punctuation artifacts
    cleaned = re.sub(r"[^\w\s&.\'-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def parse_query(raw_query: str) -> dict:
    """Parse a raw user query into structured search parameters.

    Returns:
        dict with keys: company_name, doc_type, year, raw_query, sector
    """
    year, query_without_year = _extract_year(raw_query)

    if year is None:
        year = datetime.now().year - 1

    doc_type = _match_doc_type(raw_query)

    if doc_type is None:
        doc_type = _classify_with_llm(raw_query)

    company_name = _extract_company_name(raw_query)

    sector = _detect_sector(raw_query, company_name)

    return {
        "company_name": company_name,
        "doc_type": doc_type,
        "year": year,
        "raw_query": raw_query,
        "sector": sector,
    }


if __name__ == "__main__":
    test_queries = [
        "Reliance Industries annual report 2023",
        "TCS quarterly results Q3 2024",
        "Infosys investor presentation 2022",
        "HDFC Bank financial performance",
    ]

    for q in test_queries:
        result = parse_query(q)
        print(f"\nQuery: {q}")
        print(f"  Company : {result['company_name']}")
        print(f"  Doc Type: {result['doc_type']}")
        print(f"  Year    : {result['year']}")
