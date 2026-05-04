import asyncio, sys, os, logging
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
os.chdir(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from agent import run_agent_silent

QUERIES = [
    {"company_name": "Turkish Airlines", "doc_type": "annual_report", "year": 2024,
     "raw_query": "Turkish Airlines annual report 2024"},
    {"company_name": "Bank Muscat",      "doc_type": "annual_report", "year": 2024,
     "raw_query": "Bank Muscat annual report 2024"},
]

async def run_one(q):
    print(f"[START] {q['raw_query']}", flush=True)
    try:
        r = await asyncio.wait_for(run_agent_silent(q), timeout=120)
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] {q['raw_query']}", flush=True)
        return (q["raw_query"], "TIMEOUT", 0.0, "N/A")
    except Exception as e:
        return (q["raw_query"], f"ERROR: {e}", 0.0, "N/A")
    if r:
        return (q["raw_query"], r.get("url","N/A"), r.get("score",0.0), r.get("source","N/A"))
    return (q["raw_query"], "None — not found", 0.0, "N/A")

async def main():
    results = await asyncio.gather(*[run_one(q) for q in QUERIES])
    print("\n" + "="*70)
    for label, url, score, source in results:
        print(f"Query  : {label}")
        print(f"URL    : {url}")
        print(f"Score  : {score:.3f}")
        print(f"Source : {source}")
        print()

asyncio.run(main())
