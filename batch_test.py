"""Batch stress-test the IDF agent across a diverse set of international companies."""
import json
import logging
import sys
import time

logging.basicConfig(level=logging.WARNING)  # quiet; we print our own summary
sys.path.insert(0, ".")

from agent import run_agent

COMPANIES = [
    "Tullow Oil plc",
    "Kosmos Energy Ltd",
    "Turkcell",
    "Hermès",
    "Sasol",
    "Silknet JSC",
    "Anglo American plc",
    "Hikma Pharmaceuticals",
    "Shopify",
    "ASML Holding",
    "Avianca S.A",
    "R R Kabel Ltd",
    "Aeromexico",
    "Tecpetrol",
    "AMBIPAR",
]
YEAR = "2023"

results = []
print(f"{'STATUS':6} | {'COMPANY':24} | {'TIME':6} | {'FMT':4} | {'FY':9} | {'SOURCE':12} | DETAIL", flush=True)
print("-" * 140, flush=True)

for name in COMPANIES:
    q = f"{name} {YEAR} annual report"
    t0 = time.time()
    try:
        r = run_agent(q)
    except Exception as e:
        r = {"ok": False, "reason": f"EXC: {type(e).__name__}: {e}"}
    dt = round(time.time() - t0, 1)
    r["_elapsed"] = dt
    r["_query"] = q
    r["_company"] = name
    results.append(r)

    ok = r.get("ok")
    status = "OK" if ok else "NOTFND"
    if ok:
        detail = r.get("url", "")[:90]
        fmt = "PDF" if r.get("is_pdf") else "HTML"
        fy = str(r.get("matched_fy") or "")
        src = str(r.get("source") or "")
    else:
        detail = "reason: " + str(r.get("reason", ""))[:82]
        fmt = ""
        fy = ""
        src = ""
    print(f"{status:6} | {name[:24]:24} | {dt:5}s | {fmt:4} | {fy:9} | {src:12} | {detail}", flush=True)

    # incremental dump so progress is visible mid-run
    with open("batch_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

ok_n = sum(1 for r in results if r.get("ok"))
print("-" * 140, flush=True)
print(f"DONE — {ok_n}/{len(results)} verified", flush=True)
