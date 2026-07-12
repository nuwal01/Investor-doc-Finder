"""
Query -> structured intent via LLM.

The LLM extracts: company_name, country, fiscal_year, ticker_or_id, doc_type.
fy_candidates is computed deterministically here (not by the LLM) so the
fiscal-year expansion rule is always applied correctly.

Fiscal-year expansion rule:
  country == "IN", year N  →  ["FY<N-1>-<N[-2:]>", "FY<N>-<N+1[-2:]>"]
                                e.g. 2021 → ["FY2020-21", "FY2021-22"]
  country == "US" or None  →  [str(N)]
                                e.g. 2022 → ["2022"]
"""

import json
import logging
import re

from llm_client import call_llm

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a precise data extractor. "
    "Return ONLY valid JSON with no explanation and no markdown."
)

_PROMPT = """\
Extract investor document search intent from this query.

Query: "{query}"

Return a JSON object with EXACTLY these keys:
{{
  "company_name": "<canonical company name, title-cased>",
  "raw_company": "<exactly what the user typed for the company name>",
  "country": "<ISO-2 country code such as US, IN, GB — infer from the company; null if truly unknown>",
  "ticker_or_id": "<stock ticker if visible in the query, else null>",
  "fiscal_year": <4-digit integer year or null>,
  "doc_type": "<'annual_report' unless user explicitly said '10-K' or '10K', then '10-K'>"
}}

Notes:
- For Indian companies the company name often ends with "Limited" or "Ltd" and the ticker
  may look like an all-caps abbreviation (e.g. "MBAPL", "RELIANCE").
- If the year is ambiguous (e.g. "FY2020-21"), use the ENDING year (2021 for FY2020-21).
- Do NOT include a "fy_candidates" key — it will be computed separately.
"""


def parse_intent(query: str) -> dict:
    """Parse a free-text query into a structured intent object."""
    logger.info(f"Intent: parsing {query!r}")
    prompt = _PROMPT.format(query=query.replace('"', "'"))

    try:
        raw = call_llm(prompt, system=_SYSTEM, json_mode=True)
    except Exception as exc:
        logger.error(f"Intent: LLM call failed: {exc}")
        return _fallback(query)

    intent = _parse_json(raw, query)
    intent = _normalise(intent, query)

    logger.info(
        f"Intent: company={intent['company_name']!r}  country={intent['country']}  "
        f"FY={intent['fiscal_year']}  doc_type={intent['doc_type']}  "
        f"fy_candidates={intent['fy_candidates']}"
    )
    return intent


# ── internal helpers ─────────────────────────────────────────────────────────

def _parse_json(raw: str, query: str) -> dict:
    raw = raw.strip()
    # Strip markdown code fences if the model added them anyway
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"Intent: JSON parse error: {exc} — raw: {raw[:300]}")
        return _fallback(query)


def _normalise(intent: dict, query: str) -> dict:
    """Fill defaults, validate types, compute fy_candidates."""
    intent.setdefault("company_name", query)
    intent.setdefault("raw_company", query)
    intent.setdefault("country", None)
    intent.setdefault("ticker_or_id", None)
    intent.setdefault("fiscal_year", None)
    intent.setdefault("doc_type", "annual_report")

    # Ensure fiscal_year is int or None
    fy = intent.get("fiscal_year")
    if fy is not None:
        try:
            intent["fiscal_year"] = int(fy)
        except (TypeError, ValueError):
            intent["fiscal_year"] = None

    # Deterministic fy_candidates — do not trust the LLM for this
    intent["fy_candidates"] = _fy_candidates(intent["fiscal_year"], intent["country"])

    # Normalise country to uppercase
    if intent["country"]:
        intent["country"] = str(intent["country"]).upper()

    return intent


def _fy_candidates(fiscal_year: int | None, country: str | None) -> list[str]:
    """Expand a bare year into the correct candidate labels."""
    if fiscal_year is None:
        return []
    n = int(fiscal_year)
    if country == "IN":
        # Indian financial year: April-March.
        # "2021" could mean either FY2020-21 (ended Mar 2021) or FY2021-22 (ended Mar 2022).
        return [f"FY{n - 1}-{str(n)[2:]}", f"FY{n}-{str(n + 1)[2:]}"]
    # US and unknown: year labels match the fiscal_year directly
    return [str(n)]


def _fallback(query: str) -> dict:
    """
    Best-effort intent without LLM: extract year via regex, strip it and
    common doc keywords from the company name guess so the resolver has a
    fighting chance at finding the right CIK.
    """
    import re as _re

    # ── Year extraction ───────────────────────────────────────────────────────
    # Priority 1: FY-format labels like "FY2023-24" — the \b boundary check
    # fails here because the digit runs into alphanumeric "FY", so we handle
    # it first.  "FY2023-24" → ending year = 2024 (per spec: use ending year).
    fy_label_m = _re.search(r'\bFY(\d{4})-(\d{2})\b', query, _re.IGNORECASE)
    if fy_label_m:
        start_yr = int(fy_label_m.group(1))
        end_yy   = int(fy_label_m.group(2))
        # Ending year: start_yr + 1 when the 2-digit tail wraps correctly
        fiscal_year = start_yr + 1 if end_yy == (start_yr + 1) % 100 else start_yr
    else:
        year_m = _re.search(r"\b(20\d\d)\b", query)
        fiscal_year = int(year_m.group(1)) if year_m else None

    # ── Company name extraction ───────────────────────────────────────────────
    cleaned = query
    # Remove FY-format labels first so they never pollute the company token list
    cleaned = _re.sub(r'\bFY\d{4}-\d{2}\b', '', cleaned, flags=_re.IGNORECASE)
    # Remove any remaining bare 4-digit year (standalone word boundary version)
    cleaned = _re.sub(r'\b20\d\d\b', '', cleaned)
    for noise in ("annual report", "10-k", "10k", "annual", "report", "filing"):
        cleaned = _re.sub(rf"\b{noise}\b", "", cleaned, flags=_re.IGNORECASE)
    company_guess = " ".join(cleaned.split()).strip(" ,.-")

    # Crude India detection: common Indian suffixes / exchange codes
    country = None
    if _re.search(r"\b(nse|bse|india|ltd\.?|limited|pvt)\b", query, _re.IGNORECASE):
        country = "IN"

    logger.warning(f"Intent: LLM unavailable — fallback: company={company_guess!r}  year={fiscal_year}  country={country}")
    return _normalise({
        "company_name": company_guess or query,
        "raw_company":  query,
        "country":      country,
        "ticker_or_id": None,
        "fiscal_year":  fiscal_year,
        "doc_type":     "10-K" if _re.search(r"\b10[-\s]?k\b", query, _re.IGNORECASE) else "annual_report",
    }, query)
