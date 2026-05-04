import asyncio, sys, os, logging
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
os.chdir(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from phases.entity_resolver import resolve_entity
from phases.ir_crawler import run_ir_crawl

async def main():
    for name in ["Turkish Airlines", "Bank Muscat"]:
        print(f"\n{'='*60}", flush=True)
        print(f"  {name}", flush=True)
        e = await resolve_entity(name, "annual_report", 2024)
        print(f"  MIC     : {e['exchange_mic']}", flush=True)
        print(f"  country : {e['country']}", flush=True)
        print(f"  ir_url  : {e['ir_url']}", flush=True)
        try:
            r = await asyncio.wait_for(run_ir_crawl(e, "annual_report", 2024), timeout=90)
            print(f"  IR result: {r}", flush=True)
        except asyncio.TimeoutError:
            print("  IR crawl TIMEOUT", flush=True)

asyncio.run(main())
