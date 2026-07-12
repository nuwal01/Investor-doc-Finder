"""
IDF CLI — uses the full LangGraph agent (Step 4+).

Usage:
  python main.py                              # default: Apple 2022 annual report
  python main.py "Microsoft 2023 annual report"
  python main.py "Reliance Industries 2022 annual report"
  python main.py --step1                      # Step-1 regression (hard-coded, no LLM)
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent import run_agent
from sources.edgar import fetch_10k_candidates
from verify import verify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# Step-1 regression intent (hard-coded, no LLM)
_APPLE_2022 = {
    "company_name": "Apple Inc.", "raw_company": "Apple",
    "country": "US", "ticker_or_id": "AAPL",
    "fiscal_year": 2022, "fy_candidates": ["2022"],
    "doc_type": "annual_report", "cik": "0000320193",
}


def main() -> None:
    args = sys.argv[1:]

    if "--step1" in args:
        _step1_regression()
        return

    query = " ".join(args) if args else "Apple 2022 annual report"
    logger.info("=" * 62)
    logger.info(f"IDF  query: {query!r}")
    logger.info("=" * 62)

    result = run_agent(query)
    _print(result)


def _step1_regression() -> None:
    """Hard-coded Apple 2022 EDGAR fetch — no LLM, no cache, no graph."""
    logger.info("=" * 62)
    logger.info("Step 1 regression — EDGAR hard-coded path")
    logger.info("=" * 62)
    candidates = fetch_10k_candidates(_APPLE_2022)
    if not candidates:
        print("[FAIL] EDGAR returned no candidates"); sys.exit(1)

    for i, cand in enumerate(candidates, 1):
        res = verify(cand, _APPLE_2022)
        if res["ok"]:
            print("\n" + "=" * 62)
            print("  VERIFIED (step1)")
            print(f"  URL    : {cand['url']}")
            print(f"  Format : {'PDF' if res['is_pdf'] else 'HTML'}")
            print(f"  FY     : {res['matched_fy']}")
            print("=" * 62)
            return
        logger.warning(f"Candidate {i} failed: {res['reason']}")

    print("[FAIL] No candidate passed"); sys.exit(1)


def _print(result: dict) -> None:
    sep = "=" * 62
    if result.get("ok"):
        is_pdf = result.get("is_pdf", False)
        print(f"\n{sep}")
        print("  VERIFIED")
        print(f"  URL          : {result['url']}")
        print(f"  Source       : {result.get('source', '')}")
        print(f"  Document     : {result.get('doc_returned', '')}")
        print(f"  Format       : {'PDF' if is_pdf else 'HTML'}")
        print(f"  Matched FY   : {result.get('matched_fy', '')}")
        print(f"  Company      : {result.get('company', '')}  ({result.get('country', '')})")
        print(sep)
    else:
        print(f"\n{sep}")
        print("  NOT FOUND")
        print(f"  Reason: {result.get('reason', 'unknown')}")
        print(sep)
        sys.exit(1)


if __name__ == "__main__":
    main()
