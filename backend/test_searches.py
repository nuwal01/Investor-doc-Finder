"""
Quick diagnostic: run 4 test searches and print exact results.
Run from: backend/  →  python test_searches.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

TEST_CASES = [
    {
        "label": "1 — United Bank for Africa Plc (annual_report 2024)",
        "query": {
            "company_name": "United Bank for Africa Plc",
            "doc_type": "annual_report",
            "year": 2024,
            "raw_query": "United Bank for Africa Plc annual report 2024",
        },
        "expected_domain": "ubagroup.com",
    },
    {
        "label": "2 — Batelco / BTEL (annual_report 2023)",
        "query": {
            "company_name": "Batelco",
            "doc_type": "annual_report",
            "year": 2023,
            "raw_query": "Batelco annual report 2023",
        },
        "expected_domain": "beyon.com",
    },
    {
        "label": "3 — UltraTech Cement Limited (annual_report 2024)",
        "query": {
            "company_name": "UltraTech Cement Limited",
            "doc_type": "annual_report",
            "year": 2024,
            "raw_query": "UltraTech Cement Limited annual report 2024",
        },
        "expected_domain": "ultratechcement.com",
    },
    {
        "label": "4 — UzAuto Motors JSC (annual_report 2024)",
        "query": {
            "company_name": "UzAuto Motors JSC",
            "doc_type": "annual_report",
            "year": 2024,
            "raw_query": "UzAuto Motors JSC annual report 2024",
        },
        "expected_domain": "uzautomotors.com",
    },
]


def _check_year(url: str, year: int) -> str:
    url_lower = url.lower()
    yr = str(year)
    prev = str(year - 1)
    yr2 = yr[2:]
    prev2 = prev[2:]
    fy_variants = [f"fy{yr}", f"fy{yr2}", f"{prev}-{yr2}", f"{prev}-{yr}",
                   f"{yr}-{str(year+1)[2:]}", f"{yr}-{str(year+1)}"]
    if yr in url_lower or any(v in url_lower for v in fy_variants):
        return f"EXACT ({year})"
    if prev in url_lower:
        return f"PRIOR YEAR ({year-1})"
    return "NO YEAR IN URL"


def _check_language(url: str) -> str:
    url_lower = url.lower()
    en_kw = ("english", "_en_", "-en-", "_en.", "-en.", "eng_", "_eng")
    non_en = {"arabic": "_ar", "uzbek": "_uz", "russian": "_ru",
              "turkish": "_tr", "chinese": "_cn", "french": "_fr"}
    for lang, kw in non_en.items():
        if kw in url_lower or lang in url_lower:
            return lang.upper()
    if any(k in url_lower for k in en_kw):
        return "ENGLISH (explicit)"
    return "UNKNOWN / neutral"


async def run_tests():
    from agent import run_agent_silent

    for tc in TEST_CASES:
        print("\n" + "=" * 70)
        print(f"TEST {tc['label']}")
        print("=" * 70)

        result = await run_agent_silent(tc["query"])

        if not result:
            print("  RESULT  : None — no document found")
            continue

        url    = result.get("url", "")
        source = result.get("source", "")
        score  = result.get("score", 0.0)
        conf   = result.get("confidence", "")

        year_match  = _check_year(url, tc["query"]["year"])
        lang        = _check_language(url)
        domain_ok   = tc["expected_domain"] in url.lower()

        print(f"  URL     : {url}")
        print(f"  Source  : {source}")
        print(f"  Score   : {score:.3f}")
        print(f"  Conf    : {conf}")
        print(f"  Year    : {year_match}")
        print(f"  Language: {lang}")
        domain_str = ("OK  EXPECTED (" + tc["expected_domain"] + ")") if domain_ok else ("FAIL  got: " + url.split("/")[2] + " | expected: " + tc["expected_domain"])
        print(f"  Domain  : {domain_str}")


if __name__ == "__main__":
    asyncio.run(run_tests())
