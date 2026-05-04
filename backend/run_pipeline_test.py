import asyncio
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from agent import run_agent_silent

QUERIES = [
    {"company_name": "Turkish Airlines",      "doc_type": "annual_report", "year": 2024, "raw_query": "Turkish Airlines annual report 2024", "ticker": "THYAO", "country": "TR"},
    {"company_name": "Bank Muscat",            "doc_type": "annual_report", "year": 2024, "raw_query": "Bank Muscat annual report 2024", "country": "OM"},
    {"company_name": "Nostrum Oil & Gas PLC",  "doc_type": "annual_report", "year": 2024, "raw_query": "Nostrum Oil & Gas PLC annual report 2024"},
    {"company_name": "Apple",                  "doc_type": "annual_report", "year": 2024, "raw_query": "Apple annual report 2024"},
    {"company_name": "Infosys",                "doc_type": "annual_report", "year": 2024, "raw_query": "Infosys annual report 2024"},
]


async def run_one(q: dict) -> tuple:
    label = q["raw_query"]
    print(f"[START] {label}", flush=True)
    try:
        r = await asyncio.wait_for(run_agent_silent(q), timeout=180)
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] {label}", flush=True)
        return (label, "TIMEOUT", 0.0, "N/A", "N/A")
    except Exception as e:
        print(f"[ERROR] {label}: {e}", flush=True)
        return (label, f"ERROR: {e}", 0.0, "N/A", "N/A")

    if r:
        return (label, r.get("url", "N/A"), r.get("score", 0.0), r.get("source", "N/A"), r.get("confidence", "N/A"))
    return (label, "None — not found", 0.0, "N/A", "N/A")


async def main():
    results = await asyncio.gather(*[run_one(q) for q in QUERIES])
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    for label, url, score, source, conf in results:
        print(f"Query  : {label}")
        print(f"URL    : {url}")
        print(f"Score  : {score:.3f}")
        print(f"Source : {source}")
        print(f"Conf   : {conf}")
        print()


asyncio.run(main())
