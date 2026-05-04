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

Early exit: If any parallel phase scores >= 0.90, cancel remaining and return.
Otherwise collect all results, filter by minimum passing score (0.80), and return best.
"""

import asyncio
import logging
from phases.entity_resolver import resolve_entity, resolve_known_pdf_url
from phases.exchange_direct import run_exchange_search
from phases.ir_crawler import run_ir_crawl
from phases.web_search import run_web_search
from utils.pdf_validator import AGGREGATOR_DOMAINS, TRUSTED_EXCHANGE_DOMAINS, check_url_alive, validate_pdf
from utils.sse_manager import send_status

# A result scoring below this is considered unreliable and is excluded from final selection.
MIN_PASSING_SCORE = 0.80

# Lower threshold applied only to web search results — obscure/EM companies legitimately
# score 0.65–0.75 from web search but are still the best available result.
WEB_SEARCH_MIN_SCORE = 0.65

# If any single result reaches this score, cancel remaining phases and return immediately.
# Raised from 0.70 — the old threshold was too low and allowed a quarterly report from a
# trusted exchange domain to trigger early exit before the actual annual report was found.
EARLY_EXIT_THRESHOLD = 0.90

# Legacy threshold kept for run_agent_silent backward-compat scoring checks.
SCORE_THRESHOLD = 0.5

# Trusted exchange/IR domains that block HEAD requests with 403 even when the file
# exists — skip the liveness check and trust validate_pdf's score instead.
_SKIP_LIVENESS = (
    "infosys.com", "sec.gov", "nseindia.com", "bseindia.com",
    "kap.org.tr", "dfm.ae", "adx.ae", "saudiexchange.sa",
)


def _source_tier(result: dict) -> int:
    """Return sort priority for tiebreaking (lower = higher priority).

    0 — company IR domain (IR crawl)
    1 — trusted exchange domain
    2 — web search / aggregator / other
    """
    source = result.get("source", "").lower()
    url = result.get("url", "").lower()
    if "ir crawl" in source:
        return 0
    if any(d in url for d in TRUSTED_EXCHANGE_DOMAINS):
        return 1
    return 2


def _enrich(result: dict, parsed_query: dict, entity: dict) -> dict:
    """Merge entity + query metadata into result dict before returning."""
    return {
        **result,
        "company_name":    entity.get("normalized_name") or parsed_query.get("company_name", ""),
        "normalized_name": entity.get("normalized_name", ""),
        "doc_type":        parsed_query.get("doc_type", ""),
        "year":            parsed_query.get("year", 0),
        "raw_query":       parsed_query.get("raw_query", ""),
        "country":         entity.get("country", ""),
        "exchange_mic":    entity.get("exchange_mic", ""),
    }


def _pick_best(results: list[dict]) -> dict | None:
    """Filter to passing scores, sort by score desc then source tier. Return best or None.

    FIX 4: Never returns a sub-threshold result. If nothing passes MIN_PASSING_SCORE
    the pipeline returns None and the frontend shows a graceful failure message.
    """
    passing = [r for r in results if r.get("score", 0.0) >= MIN_PASSING_SCORE]
    if not passing:
        for r in results:
            logging.warning(
                "[Agent] Candidate rejected: score=%.3f threshold=%.2f source=%s url=%s",
                r.get("score", 0.0), MIN_PASSING_SCORE,
                r.get("source", "?"), (r.get("url") or "N/A")[:100],
            )
        return None
    passing.sort(key=lambda r: (-r.get("score", 0.0), _source_tier(r)))
    return passing[0]


async def _pick_best_alive(results: list[dict]) -> dict | None:
    """Same as _pick_best but verifies the winning URL is reachable before returning.

    Iterates candidates in score order, skipping any whose HEAD/GET check fails.
    Falls back to None (graceful failure) if every candidate is dead.
    """
    passing = [
        r for r in results
        if r.get("score", 0.0) >= (
            WEB_SEARCH_MIN_SCORE
            if r.get("source", "").lower() == "web search"
            else MIN_PASSING_SCORE
        )
    ]
    if not passing:
        for r in results:
            logging.warning(
                "[Agent] Candidate rejected: score=%.3f threshold=%.2f source=%s url=%s",
                r.get("score", 0.0), MIN_PASSING_SCORE,
                r.get("source", "?"), (r.get("url") or "N/A")[:100],
            )
        return None
    passing.sort(key=lambda r: (-r.get("score", 0.0), _source_tier(r)))
    for candidate in passing:
        url = candidate.get("url", "")
        if not url:
            continue
        # known_pdf_pattern results already had validate_pdf run against them (which
        # makes a HEAD request internally), so a redundant check_url_alive call would
        # just fail on 403 CDNs that block scrapers even though the PDF exists.
        if candidate.get("source") == "known_pdf_pattern":
            return candidate
        if any(d in url.lower() for d in _SKIP_LIVENESS):
            return candidate  # trust these domains without liveness check
        if await check_url_alive(url):
            return candidate
        logging.warning("[Agent] Liveness check failed — skipping %s", url[:120])
    logging.warning("[Agent] All %d passing candidates failed liveness check", len(passing))
    return None


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

    all_results: list[dict] = []

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
                    all_results.append(result)
                    if score >= EARLY_EXIT_THRESHOLD:
                        if await check_url_alive(result.get("url", "")):
                            for p in pending:
                                p.cancel()
                            await send_status(
                                session_id,
                                f"High confidence result from {phase_name} (score {score:.2f}) — returning immediately!",
                                "done",
                            )
                            return _enrich(result, parsed_query, entity)
                        else:
                            await send_status(session_id, f"High-score URL failed liveness check — continuing search")
                else:
                    await send_status(session_id, f"✗ {phase_name} found nothing")

    # ── Phase 3.5: Known PDF URL patterns ────────────────────────────────────
    # validate_pdf already makes a HEAD request internally and treats 403 as
    # "file likely exists" (score 0.05 for file_validity), so check_url_alive
    # is skipped here — it returns False for 403 even when the PDF is real.
    if not any(r.get("score", 0.0) >= MIN_PASSING_SCORE for r in all_results):
        _known_pdf_urls = resolve_known_pdf_url(company_name, year)
        if _known_pdf_urls:
            await send_status(session_id, f"▸ Trying {len(_known_pdf_urls)} known PDF pattern(s)...")
            for _kp_url in _known_pdf_urls:
                _kp_score = await validate_pdf(
                    _kp_url, company_name, year, doc_type,
                    ir_url=entity.get("ir_url", ""),
                )
                if _kp_score >= MIN_PASSING_SCORE:
                    _kp_result = {"url": _kp_url, "score": _kp_score, "source": "known_pdf_pattern"}
                    all_results.append(_kp_result)
                    await send_status(session_id, f"✓ Known PDF pattern matched (score {_kp_score:.2f})")
                    if _kp_score >= EARLY_EXIT_THRESHOLD:
                        await send_status(
                            session_id,
                            f"High confidence known PDF (score {_kp_score:.2f}) — returning immediately!",
                            "done",
                        )
                        return _enrich(_kp_result, parsed_query, entity)

    # ── Phase 4: Web Search — LAST RESORT, only if no passing result yet ──
    # A sub-threshold result from exchange/IR still triggers web search.
    _has_passing = any(r.get("score", 0.0) >= MIN_PASSING_SCORE for r in all_results)
    if not _has_passing:
        await send_status(
            session_id,
            f"▸ Web search (last resort — no passing result yet) sector: {sector or 'auto'}",
        )
        try:
            web_result = await run_web_search(entity, doc_type, year, sector)
        except Exception as e:
            await send_status(session_id, f"✗ web_search failed: {e}")
            web_result = None
        if web_result:
            score = web_result.get("score", 0.0)
            web_result["score"] = score
            if WEB_SEARCH_MIN_SCORE <= score < MIN_PASSING_SCORE:
                web_result["confidence"] = "low"
            await send_status(session_id, f"✓ web_search complete (score {score:.2f})")
            all_results.append(web_result)
            if score >= EARLY_EXIT_THRESHOLD:
                if await check_url_alive(web_result.get("url", "")):
                    await send_status(
                        session_id,
                        f"High confidence result from web_search (score {score:.2f}) — returning immediately!",
                        "done",
                    )
                    return _enrich(web_result, parsed_query, entity)
                else:
                    await send_status(session_id, "High-score web URL failed liveness check — falling through")
        else:
            await send_status(session_id, "✗ web_search found nothing")
    else:
        await send_status(session_id, "▸ Skipping web search — passing result already found")

    await send_status(session_id, "All search phases complete.")

    # ── Return best result (with liveness check) ──────────────────────────
    best_result = await _pick_best_alive(all_results)
    if best_result:
        score = best_result.get("score", 0.0)
        await send_status(
            session_id,
            f"Best result (score {score:.2f}) — returning.",
            "done",
        )
        return _enrich(best_result, parsed_query, entity)

    await send_status(session_id, "Document not found after all attempts.", "error")
    return None


async def run_agent_silent(parsed_query: dict, user_uid: str | None = None) -> dict | None:
    """Same pipeline as run_agent but without SSE status messages. Used by /bulk-search."""
    company_name = parsed_query["company_name"]
    doc_type     = parsed_query["doc_type"]
    year         = parsed_query["year"]
    sector       = parsed_query.get("sector", "")
    all_results: list[dict] = []

    # Phase 1 — Entity Resolution
    try:
        entity = await resolve_entity(company_name, doc_type, year)
    except Exception:
        return None

    # Propagate user-provided hints (ticker, country, exchange_mic) into the entity
    # so downstream phases (KAP, BSE, etc.) can use them as overrides.
    for _hint in ("ticker", "country", "exchange_mic"):
        _v = parsed_query.get(_hint)
        if _v and not entity.get(_hint):
            entity[_hint] = _v

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
                    all_results.append(result)
                    if score >= EARLY_EXIT_THRESHOLD:
                        if await check_url_alive(result.get("url", "")):
                            for p in pending:
                                p.cancel()
                            return _enrich(result, parsed_query, entity)

    # Phase 3.5 — Known PDF URL patterns (no check_url_alive — see run_agent comment)
    if not any(r.get("score", 0.0) >= MIN_PASSING_SCORE for r in all_results):
        for _kp_url in resolve_known_pdf_url(company_name, year):
            _kp_score = await validate_pdf(
                _kp_url, company_name, year, doc_type,
                ir_url=entity.get("ir_url", ""),
            )
            if _kp_score >= MIN_PASSING_SCORE:
                _kp_result = {"url": _kp_url, "score": _kp_score, "source": "known_pdf_pattern"}
                all_results.append(_kp_result)
                if _kp_score >= EARLY_EXIT_THRESHOLD:
                    return _enrich(_kp_result, parsed_query, entity)

    # Phase 4 — Web Search: only if no passing result yet
    if not any(r.get("score", 0.0) >= MIN_PASSING_SCORE for r in all_results):
        try:
            web_result = await run_web_search(entity, doc_type, year, sector)
        except Exception:
            web_result = None
        if web_result:
            score = web_result.get("score", 0.0)
            web_result["score"] = score
            if WEB_SEARCH_MIN_SCORE <= score < MIN_PASSING_SCORE:
                web_result["confidence"] = "low"
            all_results.append(web_result)
            if score >= EARLY_EXIT_THRESHOLD:
                if await check_url_alive(web_result.get("url", "")):
                    return _enrich(web_result, parsed_query, entity)

    best_result = await _pick_best_alive(all_results)
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
