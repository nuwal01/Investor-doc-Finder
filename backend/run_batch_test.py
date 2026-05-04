"""
Batch test for 10 companies. Run from the backend/ directory:
    python run_batch_test.py
"""

import asyncio
import logging
import os
import sys
from urllib.parse import urlparse

# Silence noisy logs during test
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.dirname(__file__))

from agent import run_agent_silent
from utils.pdf_validator import TRUSTED_EXCHANGE_DOMAINS, AGGREGATOR_DOMAINS, doc_type_tier

COMPANIES = [
    ("MTN Group Limited",                              "annual_report", 2024),
    ("Eskom Holdings SOC Ltd",                         "annual_report", 2024),
    ("PJSC LUKOIL",                                    "annual_report", 2024),
    ("Emaar Properties PJSC",                          "annual_report", 2024),
    ("SABIC",                                          "annual_report", 2024),
    ("UPL Limited",                                    "annual_report", 2024),
    ("DNO ASA",                                        "annual_report", 2024),
    ("Petrobras",                                      "annual_report", 2024),
    ("Gerdau S.A.",                                    "annual_report", 2024),
    ("Adani Ports and Special Economic Zone Limited",  "annual_report", 2024),
]


def _is_official(url: str, ir_url: str) -> bool:
    if not url:
        return False
    try:
        url_netloc = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return False
    if any(d in url_netloc for d in TRUSTED_EXCHANGE_DOMAINS):
        return True
    if ir_url:
        try:
            ir_netloc = urlparse(ir_url).netloc.lower().lstrip("www.")
            if ir_netloc and (ir_netloc in url_netloc or url_netloc.endswith(ir_netloc)):
                return True
        except Exception:
            pass
    if any(agg in url_netloc for agg in AGGREGATOR_DOMAINS):
        return False
    return False


def _year_in_url(url: str, year: int) -> bool:
    if not url:
        return False
    url_l = url.lower()
    yr = str(year)
    prev = str(year - 1)
    yr2 = yr[2:]
    variants = [yr, f"fy{yr}", f"fy{yr2}", f"{prev}-{yr2}", f"{yr}-{str(year+1)[2:]}",
                f"ar{yr}", f"{yr}ar"]
    return any(v in url_l for v in variants)


def _known_ir_url(company: str) -> str:
    """Return the KNOWN_IR_URL for this company (same lookup logic as entity_resolver)."""
    from phases.entity_resolver import KNOWN_IR_URLS
    name_lower = company.lower().strip()
    return next((url for key, url in KNOWN_IR_URLS.items() if key in name_lower), "")


async def run_one(company: str, doc_type: str, year: int) -> dict:
    query = {
        "company_name": company,
        "doc_type": doc_type,
        "year": year,
        "raw_query": f"{company} {doc_type.replace('_',' ')} {year}",
        "sector": "",
    }
    result = await run_agent_silent(query)
    return result or {}


async def main():
    print("=" * 80)
    print("BATCH TEST -- 10 companies -- annual_report 2024")
    print("=" * 80)

    for i, (company, doc_type, year) in enumerate(COMPANIES, 1):
        print(f"\n[{i:02d}] {company}")
        print("-" * 60)

        result = await run_one(company, doc_type, year)

        url    = result.get("url") or "None"
        score  = result.get("score", 0.0)
        source = result.get("source", "N/A")

        # Official: use KNOWN_IR_URLS as the expected IR domain for this company
        known_ir = _known_ir_url(company)
        official    = _is_official(url, known_ir) if url != "None" else False
        year_conf   = _year_in_url(url, year) if url != "None" else False
        tier        = doc_type_tier(url, doc_type) if url != "None" else "-"

        print(f"  URL      : {url}")
        print(f"  Score    : {score:.3f}")
        print(f"  Layer    : {source}")
        print(f"  Official : {'yes' if official else 'no'}")
        print(f"  Year OK  : {'yes' if year_conf else 'no'}")
        print(f"  Tier     : {tier}")

        if url == "None":
            print("  WARNING  : No result returned")
        elif score < 0.80:
            print(f"  WARNING  : Score below passing threshold (0.80)")


if __name__ == "__main__":
    asyncio.run(main())
