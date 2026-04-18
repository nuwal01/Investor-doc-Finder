"""
Agent — orchestrates the multi-phase document search pipeline.

Input:  parsed_query dict {company_name, doc_type, year, raw_query}, session_id (str)
Output: dict {url, source, confidence, score} or None

Phases:
  1. Entity Resolution   → identify company via OpenFIGI + Finnhub (runs first)
  2-4. Parallel Phase Execution (after entity resolution):
      - Exchange Direct   → query stock-exchange filing APIs
      - IR Website Crawl  → crawl investor-relations page for PDFs
      - Web Search        → AI-powered Google search via Serper + Groq multilingual

Early exit: If any parallel phase scores >= 0.70, cancel remaining and return.
Otherwise return highest scoring result.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from phases.entity_resolver import resolve_entity
from phases.exchange_direct import run_exchange_search
from phases.ir_crawler import run_ir_crawl
from phases.web_search import run_web_search
from utils.sse_manager import send_status

SCORE_THRESHOLD = 0.5
EARLY_EXIT_THRESHOLD = 0.70  # If any phase scores this high, return immediately


def _enrich(result: dict, parsed_query: dict, entity: dict) -> dict:
    """
    Merge entity + query metadata into the result dict before returning it.

    The enriched dict is sent to the frontend via SSE so that history.js can
    save a complete Firestore document (company_name, doc_type, year, etc.)
    without a second round-trip to the backend.
    """
    return {
        **result,
        "company_name":   entity.get("normalized_name") or parsed_query.get("company_name", ""),
        "normalized_name": entity.get("normalized_name", ""),
        "doc_type":        parsed_query.get("doc_type", ""),
        "year":            parsed_query.get("year", 0),
        "raw_query":       parsed_query.get("raw_query", ""),
        "country":         entity.get("country", ""),
        "exchange_mic":    entity.get("exchange_mic", ""),
    }

# Legacy thresholds (kept for backward compatibility in run_agent_silent)
PHASE2_THRESHOLD = 0.5   # exchange direct
PHASE3_THRESHOLD = 0.4   # IR crawl
PHASE4_THRESHOLD = 0.3   # web search


async def run_agent(parsed_query: dict, session_id: str, user_uid: str | None = None) -> dict | None:
    """Run the full search pipeline, streaming status updates via SSE.

    Args:
        parsed_query: {company_name, doc_type, year, raw_query, sector}
        session_id:   SSE session identifier

    Returns:
        {url, source, confidence, score} or None
    """
    company_name = parsed_query["company_name"]
    doc_type = parsed_query["doc_type"]
    year = parsed_query["year"]
    sector = parsed_query.get("sector", "")

    best_result: dict | None = None

    # ── Phase 1: Entity Resolution ───────────────────────────────────────
    doc_label = doc_type.replace("_", " ")
    await send_status(session_id, f"Searching for: {company_name} {doc_label} {year}...")

    try:
        entity = await resolve_entity(company_name, doc_type, year)
    except Exception as e:
        await send_status(session_id, f"Entity resolution failed: {e}", "error")
        return None

    display_name = entity.get("normalized_name") or company_name
    mic = entity.get("exchange_mic", "")
    ir_url = entity.get("ir_url", "")
    if mic:
        await send_status(session_id, f"Found: {display_name} on {mic}")
    else:
        await send_status(session_id, f"Identified: {display_name} (no exchange match)")

    if ir_url:
        await send_status(session_id, f"IR website: {ir_url}")
    else:
        await send_status(session_id, "Could not find IR website, relying on web search only")

    # ── Phases 2-3: Exchange + IR Crawl first (web search is last resort) ──
    await send_status(session_id, "Running exchange + IR crawl phases first...")

    phase_23_tasks: dict = {}
    if mic:
        await send_status(session_id, f"▸ Exchange search ({mic})")
        phase_23_tasks["exchange"] = asyncio.create_task(run_exchange_search(entity, doc_type, year))
    if ir_url:
        await send_status(session_id, "▸ IR website crawl")
        phase_23_tasks["ir_crawl"] = asyncio.create_task(run_ir_crawl(entity, doc_type, year))

    if phase_23_tasks:
        pending = set(phase_23_tasks.values())
        phase_names = {v: k for k, v in phase_23_tasks.items()}
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                phase_name = phase_names[task]
                try:
                    result = task.result()
                except Exception as e:
                    await send_status(session_id, f"✗ {phase_name} failed: {e}")
                    continue
                if result:
                    score = result.get("score", 0.0)
                    result["score"] = score
                    await send_status(session_id, f"✓ {phase_name} complete (score {score:.2f})")
                    if score >= EARLY_EXIT_THRESHOLD:
                        for p in pending:
                            p.cancel()
                        await send_status(
                            session_id,
                            f"High confidence result from {phase_name} (score {score:.2f}) — returning immediately!",
                            "done",
                        )
                        return _enrich(result, parsed_query, entity)
                    if best_result is None or score > best_result.get("score", 0.0):
                        best_result = result
                else:
                    await send_status(session_id, f"✗ {phase_name} found nothing")

    # ── Phase 4: Web Search — LAST RESORT, only if exchange + IR returned nothing ──
    if best_result is None:
        await send_status(session_id, f"▸ Web search (last resort — IR/exchange found nothing) sector: {sector or 'auto'}")
        try:
            web_result = await run_web_search(entity, doc_type, year, sector)
        except Exception as e:
            await send_status(session_id, f"✗ web_search failed: {e}")
            web_result = None
        if web_result:
            score = web_result.get("score", 0.0)
            web_result["score"] = score
            await send_status(session_id, f"✓ web_search complete (score {score:.2f})")
            if score >= EARLY_EXIT_THRESHOLD:
                await send_status(
                    session_id,
                    f"High confidence result from web_search (score {score:.2f}) — returning immediately!",
                    "done",
                )
                return _enrich(web_result, parsed_query, entity)
            best_result = web_result
        else:
            await send_status(session_id, "✗ web_search found nothing")
    else:
        await send_status(session_id, "▸ Skipping web search — IR/exchange already found a result")

    await send_status(session_id, "All search phases complete.")

    # ── Return best result or fail ───────────────────────────────────────
    if best_result:
        await send_status(
            session_id,
            f"Best result (score {best_result['score']:.2f}) below {SCORE_THRESHOLD} threshold, returning anyway.",
            "done",
        )
        return _enrich(best_result, parsed_query, entity)

    await send_status(session_id, "Document not found after all attempts.", "error")
    return None


async def run_agent_silent(parsed_query: dict, user_uid: str | None = None) -> dict | None:
    """Same pipeline as run_agent but without SSE status messages. Used by /bulk-search.

    Runs phases 2-4 in parallel with early exit on high-confidence results.
    """
    company_name = parsed_query["company_name"]
    doc_type     = parsed_query["doc_type"]
    year         = parsed_query["year"]
    sector       = parsed_query.get("sector", "")
    best_result: dict | None = None

    # Phase 1 — Entity Resolution
    try:
        entity = await resolve_entity(company_name, doc_type, year)
    except Exception:
        return None

    mic    = entity.get("exchange_mic", "")
    ir_url = entity.get("ir_url", "")

    # Phases 2-3 — Exchange + IR Crawl first
    phase_23_tasks: dict = {}
    if mic:
        phase_23_tasks["exchange"] = asyncio.create_task(run_exchange_search(entity, doc_type, year))
    if ir_url:
        phase_23_tasks["ir_crawl"] = asyncio.create_task(run_ir_crawl(entity, doc_type, year))

    if phase_23_tasks:
        pending = set(phase_23_tasks.values())
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    result = task.result()
                except Exception:
                    continue
                if result:
                    score = result.get("score", 0.0)
                    result["score"] = score
                    if score >= EARLY_EXIT_THRESHOLD:
                        for p in pending:
                            p.cancel()
                        return _enrich(result, parsed_query, entity)
                    if best_result is None or score > best_result.get("score", 0.0):
                        best_result = result

    # Phase 4 — Web Search: only if exchange + IR returned nothing
    if best_result is None:
        try:
            web_result = await run_web_search(entity, doc_type, year, sector)
        except Exception:
            web_result = None
        if web_result:
            score = web_result.get("score", 0.0)
            web_result["score"] = score
            if score >= EARLY_EXIT_THRESHOLD:
                return _enrich(web_result, parsed_query, entity)
            if best_result is None or score > best_result.get("score", 0.0):
                best_result = web_result

    if best_result:
        return _enrich(best_result, parsed_query, entity)
    return None


if __name__ == "__main__":
    import asyncio
    from utils.sse_manager import stream_events

    async def main():
        sid = "test-agent-1"
        query = {
            "company_name": "Apple",
            "doc_type": "annual_report",
            "year": 2023,
            "raw_query": "Apple annual report 2023",
        }

        async def consumer():
            async for event in stream_events(sid):
                tag = event["event"]
                data = event["data"]
                if tag == "result":
                    print(f"  [RESULT]  {data}")
                elif tag == "error":
                    print(f"  [ERROR]   {data}")
                elif tag == "done":
                    print(f"  [DONE]    {data}")
                else:
                    print(f"  [STATUS]  {data}")

        print("=== Agent Pipeline Test ===\n")
        _, result = await asyncio.gather(consumer(), run_agent(query, sid))
        print(f"\nFinal result: {result}")

    asyncio.run(main())
