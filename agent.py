"""
LangGraph agent — wires every IDF component into a stateful graph (Step 4).

Graph flow:
  parse_intent → check_cache → [HIT → return_result]
                             → [MISS → resolve → route → fetch_source]
  fetch_source → verify_candidates → [PASS → cache_write → return_result → END]
                                   → [FAIL + sources left → fetch_source  (loop)]
                                   → [FAIL + exhausted   → give_up        → END]

Guardrails baked in:
  • MAX_ATTEMPTS  = 6  source attempts before give_up
  • MAX_WALL_SEC  = 45 seconds wall-clock before give_up
"""

import csv
import logging
import re
import time
from pathlib import Path
from typing import Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from cache import cache_get, cache_put
from fund_filter import fund_reject_result
from intent import parse_intent as _parse_intent
from resolver import resolve as _resolve
from verify import verify as _verify

logger = logging.getLogger(__name__)

MAX_ATTEMPTS   = 6
MAX_WALL_SEC   = 45

# Lazy last-resort fallback sources: only fetched when the primary verified nothing
# (see _fetch_source_node / find_web_mirror_candidates). A give_up with only these
# still pending counts as "sources exhausted", not "still searching" (see _give_up_node).
_LAZY_FALLBACK_SOURCES = frozenset({"web_search_mirror"})


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    query:               str
    intent:              dict
    pending_sources:     list
    candidates:          list
    verified:            Optional[dict]   # single hit from the cache-HIT path
    verified_candidates: list             # accumulated across all fetched sources
    attempt_count:       int
    start_time:          float
    search_cut_short:    bool             # cap cut the verify loop short mid-source
    final_result:        Optional[dict]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def _parse_intent_node(state: AgentState) -> dict:
    logger.info(f"[parse_intent] {state.get('query')!r}")
    intent = _parse_intent(state["query"])
    return {"intent": intent, "start_time": time.time()}


def _check_cache_node(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    company = intent.get("company_name", "")
    fy      = intent.get("fiscal_year")
    dtype   = intent.get("doc_type", "annual_report")

    if not company or not fy:
        return {}

    hit = cache_get(company, fy, dtype)
    if hit:
        logger.info(f"[check_cache] HIT → {hit.get('url','')[:70]}")
        return {"verified": hit}
    return {}


def _resolve_node(state: AgentState) -> dict:
    logger.info("[resolve] looking up company IDs")
    intent = _resolve(state.get("intent") or {})
    return {"intent": intent}


def _route_node(state: AgentState) -> dict:
    intent  = state.get("intent") or {}

    # Resolver flagged this query as too ambiguous — skip all sources
    if intent.get("_give_up_reason"):
        logger.info(f"[route] early give_up: {intent['_give_up_reason']}")
        return {"pending_sources": [], "attempt_count": 0}

    country = (intent.get("country") or "").upper()
    has_cik = bool(intent.get("cik"))

    if country == "US" or has_cik:
        sources = ["edgar", "web_search"]
    elif country == "IN":
        sources = ["nse", "company_site", "aggregators", "web_search"]
    else:
        # web_search_mirror is a LAZY fallback: _fetch_source_node skips it unless the
        # primary web_search verified nothing (see there). It only runs the scoped
        # third-party mirror query, so companies that resolve cleanly pay no extra cost.
        sources = ["web_search", "web_search_mirror"]

    logger.info(f"[route] country={country!r}  chain={sources}")
    return {"pending_sources": sources, "attempt_count": 0}


def _fetch_source_node(state: AgentState) -> dict:
    pending  = list(state.get("pending_sources") or [])
    if not pending:
        return {"candidates": [], "pending_sources": []}

    name    = pending.pop(0)
    intent  = state.get("intent") or {}

    # Lazy mirror fallback: web_search_mirror runs the scoped third-party report-mirror
    # query, and only earns its latency when the primary web_search verified nothing.
    # If a candidate already verified, skip it entirely — no dispatch, no mirror Exa
    # call, no attempt counted. (Applies to web_search_mirror only; every other source
    # is unaffected.)
    if name == "web_search_mirror" and state.get("verified_candidates"):
        logger.info("[fetch_source] web_search_mirror skipped — primary already verified a candidate")
        return {"candidates": [], "pending_sources": pending}

    attempt = (state.get("attempt_count") or 0) + 1

    logger.info(f"[fetch_source] source={name!r}  attempt={attempt}")
    candidates = _dispatch(name, intent)
    logger.info(f"[fetch_source] {name!r} → {len(candidates)} candidate(s)")

    return {"candidates": candidates, "pending_sources": pending, "attempt_count": attempt}


_FORM_TYPES = ("10-K", "20-F", "40-F")


def _parse_form_type(note: str) -> str:
    """Extract the SEC form type (10-K / 20-F / 40-F) from a candidate note.

    EDGAR notes are formatted like ``EDGAR 20-F: <company> FY2023 ...`` so the
    form type is a plain substring. Returns "" when none is present (e.g. a
    web_search candidate).
    """
    note = note or ""
    for form in _FORM_TYPES:
        if form in note:
            return form
    return ""


def _verify_node(state: AgentState) -> dict:
    candidates = state.get("candidates") or []
    intent     = state.get("intent") or {}
    start_time = state.get("start_time") or time.time()
    # Accumulate ACROSS sources: keep every verified candidate so the final
    # selection can compare them by precedence instead of taking first-match.
    accumulated = list(state.get("verified_candidates") or [])
    # True only if the cap cut this loop short with candidates still unverified —
    # a genuine "ran out of time mid-search" signal give_up uses to keep the
    # timeout label (vs. the loop completing, which means the source was exhausted).
    cut_short = False

    for i, cand in enumerate(candidates):
        # Between-candidates wall-clock enforcement. _after_verify only checks
        # MAX_WALL_SEC *between sources*, so a single source returning many slow
        # candidates (e.g. web_search's 8-candidate result) could blow the budget
        # inside this loop with no check — the AMBIPAR 56s > 45s overrun. Stop
        # before starting the next candidate once the budget is spent; whatever
        # already verified is kept, and _after_verify routes to cache_write/give_up.
        elapsed = time.time() - start_time
        if elapsed >= MAX_WALL_SEC:
            logger.warning(
                f"[verify] wall-clock budget spent ({elapsed:.0f}s >= {MAX_WALL_SEC}s) — "
                f"stopping after {i}/{len(candidates)} candidate(s) from this source"
            )
            cut_short = True
            break
        logger.info(
            f"[verify] {i+1}/{len(candidates)} (t={elapsed:.0f}s): {cand.get('url','')[:70]}"
        )
        res = _verify(cand, intent)
        if res["ok"]:
            verified = {
                "url":          cand["url"],
                "source":       cand["source"],
                "note":         cand.get("note", ""),
                "is_pdf":       res["is_pdf"],
                "matched_fy":   res["matched_fy"],
                "content_type": res.get("content_type", ""),
                "form_type":    _parse_form_type(cand.get("note", "")),
            }
            accumulated.append(verified)
            logger.info(
                f"[verify] PASS → {cand['url'][:70]} "
                f"(source={verified['source']}, is_pdf={verified['is_pdf']})"
            )
        else:
            logger.warning(f"[verify] fail: {res['reason']}")

    logger.info(f"[verify] verified so far: {len(accumulated)} candidate(s)")
    return {"verified_candidates": accumulated, "candidates": [], "search_cut_short": cut_short}


# ── Final-result precedence ────────────────────────────────────────────────────
# source_priority — lower wins. The spec defines two tiers:
#   0 = EDGAR (or other regulatory source)
#   1 = web_search
# NSE filings are regulatory/exchange-official, so they join EDGAR at tier 0.
# company_site and aggregators are non-regulatory scrapes, so they sit with
# web_search at tier 1. (Only edgar-vs-web_search is exercised by the ASML test;
# the rest are grouped by the same regulatory/non-regulatory rule.)
_REGULATORY_SOURCES = frozenset({"edgar", "nse"})


def _source_priority(source: str) -> int:
    return 0 if source in _REGULATORY_SOURCES else 1


def _select_final(candidates: list[dict]) -> dict:
    """Pick the winning verified candidate by explicit precedence.

    Ascending sort; candidates[0] is the winner:
      1. source_priority  — a regulatory source (0) beats a non-regulatory one
                            (1) REGARDLESS of file format.
      2. PDF before HTML  — tiebreaker ONLY among same-priority candidates.

    NOTE: the format tiebreaker uses ``0 if is_pdf else 1`` so PDF sorts first.
    Sorting the raw ``is_pdf`` bool ascending would put HTML (False) first,
    contradicting the "PDF is preferred over HTML" rule — so it is inverted.
    No format conversion happens here: if an HTML candidate wins, it is returned
    as HTML (HTML→PDF conversion is deliberately out of scope).
    """
    if not candidates:
        return {}
    return sorted(
        candidates,
        key=lambda c: (_source_priority(c.get("source", "")),
                       0 if c.get("is_pdf") else 1),
    )[0]


def _cache_write_node(state: AgentState) -> dict:
    verified_candidates = state.get("verified_candidates") or []
    # Cache the SAME candidate the precedence rule will return, not first-match.
    winner   = _select_final(verified_candidates) or state.get("verified") or {}
    intent   = state.get("intent") or {}
    company  = intent.get("company_name", "")
    fy       = intent.get("fiscal_year")
    dtype    = intent.get("doc_type", "annual_report")
    if company and fy and winner.get("url"):
        cache_put(company, fy, dtype, winner, intent)
    return {}


def _return_result_node(state: AgentState) -> dict:
    verified_candidates = state.get("verified_candidates") or []
    # Normal path accumulates a list; the cache-HIT path sets a single `verified`
    # dict and skips fetch/verify entirely. Select the final result by explicit
    # precedence (not first-match) whenever multiple verified candidates exist.
    winner = _select_final(verified_candidates) if verified_candidates \
        else (state.get("verified") or {})

    intent   = state.get("intent") or {}
    is_pdf   = winner.get("is_pdf", False)
    dtype    = intent.get("doc_type", "annual_report")
    # form_type rides on the verified candidate (fresh path) or the cached row
    # (cache-HIT path); fall back to parsing the note if it's still missing.
    form_type = winner.get("form_type") or _parse_form_type(winner.get("note", ""))

    # EDGAR primary docs are XBRL .htm, never native PDF — the UI converts them
    # to PDF on demand (in memory). The label keys off source, not a converted
    # artifact: conversion now happens lazily at download time, not here.
    if dtype == "annual_report" and is_pdf:
        doc_returned = "annual report PDF (IR)"
    elif dtype == "annual_report" and winner.get("source") == "edgar":
        doc_returned = "10-K / regulatory filing (EDGAR HTML converted to PDF)"
    elif dtype == "annual_report":
        doc_returned = "10-K / regulatory filing (HTML) — glossy PDF via web_search"
    else:
        doc_returned = "10-K filing"

    final = {
        "ok":          True,
        "url":         winner.get("url", ""),
        "source":      winner.get("source", ""),
        "form_type":   form_type,
        "is_pdf":      is_pdf,
        "doc_returned": doc_returned,
        "matched_fy":  winner.get("matched_fy"),
        "company":     intent.get("company_name", ""),
        "country":     intent.get("country"),
        "fiscal_year": intent.get("fiscal_year"),
    }
    logger.info(
        f"[return_result] source={final['source']} is_pdf={final['is_pdf']} "
        f"url={final['url'][:70]} (chosen from {len(verified_candidates)} verified)"
    )
    return {"final_result": final}


# ── give_up fallback (tiered) ───────────────────────────────────────────────────
# On a give_up, offer a best-effort fallback link so the user isn't left empty-handed.
# Tier 1 = curated official_domain from company_map.csv (keyed on the ORIGINAL user
# string, raw_company, NOT the resolver-overwritable company_name). Tier 2 = a live
# "investor relations" web search, always labelled unverified. Read-only: never writes
# company_map.csv and never guesses a domain.

_COMPANY_MAP = Path(__file__).parent / "data" / "company_map.csv"


def _norm_token(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _lookup_official_domain(raw_company: str) -> str:
    """Curated official_domain for raw_company, or '' if none. Keyed on the original
    user string, matched against the CSV's ticker / company_name / canonical_name."""
    if not raw_company or not _COMPANY_MAP.exists():
        return ""
    key       = _norm_token(raw_company)
    key_upper = raw_company.strip().upper()
    try:
        with open(_COMPANY_MAP, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                domain = (row.get("official_domain") or "").strip()
                if not domain:
                    continue
                if key_upper and (row.get("ticker") or "").strip().upper() == key_upper:
                    return domain
                if key and key in (_norm_token(row.get("company_name")),
                                   _norm_token(row.get("canonical_name"))):
                    return domain
    except Exception as exc:  # pragma: no cover — defensive only
        logger.debug(f"[give_up] official_domain lookup failed: {exc}")
    return ""


def _company_diverged(company_name: str, raw_company: str) -> bool:
    """Same divergence test the verify.py identity gate uses: resolved and requested
    share no distinctive token. Imports verify's helper so the check stays identical."""
    try:
        from verify import _distinctive_tokens
    except Exception:  # pragma: no cover — defensive only
        return False
    resolved  = _distinctive_tokens(company_name or "")
    requested = _distinctive_tokens(raw_company or "")
    return bool(requested and resolved and not (set(requested) & set(resolved)))


def _giveup_live_search(raw_company: str, country) -> str:
    """Tier 2: live '{raw_company} investor relations' search; first URL or ''."""
    if not raw_company:
        return ""
    try:
        from sources.web_search import _search
        urls = _search(f"{raw_company} investor relations", country)
        return urls[0] if urls else ""
    except Exception as exc:
        logger.debug(f"[give_up] tier-2 live search failed: {exc}")
        return ""


def _as_domain_url(domain: str) -> str:
    d = (domain or "").strip()
    return d if d.startswith(("http://", "https://")) else f"https://{d}"


def _giveup_fallback(intent: dict) -> Optional[dict]:
    """Tiered fallback for a give_up. Returns None if nothing to offer."""
    raw_company = (intent.get("raw_company") or "").strip()
    if not raw_company:
        return None

    domain = _lookup_official_domain(raw_company)
    if domain:  # Tier 1 — curated
        diverged = _company_diverged(intent.get("company_name", ""), raw_company)
        confidence = "uncertain" if diverged else "verified"
        logger.info(f"[give_up] tier-1 fallback ({confidence}) for {raw_company!r}: {domain}")
        return {"tier": 1, "url": _as_domain_url(domain), "confidence": confidence}

    url = _giveup_live_search(raw_company, intent.get("country"))  # Tier 2 — live search
    if url:
        logger.info(f"[give_up] tier-2 fallback (unverified) for {raw_company!r}: {url[:70]}")
        return {"tier": 2, "url": url, "confidence": "unverified"}
    return None


def _give_up_node(state: AgentState) -> dict:
    intent   = state.get("intent") or {}
    elapsed  = time.time() - (state.get("start_time") or time.time())
    attempts = state.get("attempt_count") or 0

    # A guardrail (wall-clock / max-attempts) only means "still mid-search" if real
    # work was LEFT when it tripped: the candidate loop cut short mid-source
    # (search_cut_short), or a PRODUCTIVE source still queued. web_search_mirror is
    # excluded — it is the lazy last-resort fallback that only runs once the primary
    # verified nothing, so "only the mirror remains" is effectively exhaustion, not
    # active search. Without this, Aeromexico flips label run-to-run purely on whether
    # its slow web_search discovery finishes just under or just over the 45s cap (and
    # so whether the mirror gets reached) — the diagnostic showed the mirror finds
    # nothing either way. If everything productive was already tried and the cap merely
    # tripped on the way out, the honest outcome is a discovery gap, not a performance
    # timeout; labeling that "timeout" wrongly implies a retry would help.
    productive_pending = [s for s in (state.get("pending_sources") or [])
                          if s not in _LAZY_FALLBACK_SOURCES]
    still_searching = bool(state.get("search_cut_short")) or bool(productive_pending)

    if intent.get("_give_up_reason"):
        reason = intent["_give_up_reason"]
    elif elapsed >= MAX_WALL_SEC and still_searching:
        reason = f"Wall-clock timeout ({elapsed:.0f}s > {MAX_WALL_SEC}s)"
    elif attempts >= MAX_ATTEMPTS and still_searching:
        reason = f"Max attempts reached ({attempts})"
    else:
        reason = "No verifiable annual report found for this company via current sources"

    final = {
        "ok":          False,
        "reason":      reason,
        "company":     intent.get("company_name", ""),
        "fiscal_year": intent.get("fiscal_year"),
        "fallback":    _giveup_fallback(intent),
    }
    logger.info(f"[give_up] {reason}")
    return {"final_result": final}


# ── Routing functions ─────────────────────────────────────────────────────────

def _after_cache(state: AgentState) -> str:
    return "return_result" if state.get("verified") else "resolve"


def _after_verify(state: AgentState) -> str:
    elapsed  = time.time() - (state.get("start_time") or time.time())
    attempts = state.get("attempt_count") or 0
    verified = state.get("verified_candidates") or []

    # Hybrid tier-0 short-circuit: once a tier-0 (regulatory) source has verified a
    # candidate, nothing a later source could produce can outrank it — `_select_final`
    # sorts tier-0 (`_source_priority == 0`, i.e. edgar/nse) above every tier-1 source
    # REGARDLESS of format. So stop fetching the rest of the route and go straight to
    # the winner, skipping the wasted tier-1 fetches. This does NOT fire for tier-1
    # verifications: comparing tier-1 candidates against each other is the whole reason
    # full accumulation exists, so tier-1-only routes still run in full as before. Uses
    # the same `_source_priority` mapping as `_select_final` (no duplicate tier list).
    if any(_source_priority(c.get("source", "")) == 0 for c in verified):
        logger.info(
            "[after_verify] tier-0 (regulatory) candidate verified — short-circuiting "
            "remaining sources and proceeding to result"
        )
        return "cache_write"

    # Otherwise keep visiting remaining sources so verified candidates from ALL sources
    # accumulate and can be compared by precedence — do NOT stop at the first
    # verified hit. Guardrails still bound the total work.
    if (
        state.get("pending_sources")
        and attempts < MAX_ATTEMPTS
        and elapsed < MAX_WALL_SEC
    ):
        return "fetch_source"
    # Sources exhausted (or a guardrail tripped): return the best of whatever we
    # verified; give up only if nothing verified at all.
    if state.get("verified_candidates"):
        return "cache_write"
    return "give_up"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("parse_intent",      _parse_intent_node)
    g.add_node("check_cache",       _check_cache_node)
    g.add_node("resolve",           _resolve_node)
    g.add_node("route",             _route_node)
    g.add_node("fetch_source",      _fetch_source_node)
    g.add_node("verify_candidates", _verify_node)
    g.add_node("cache_write",       _cache_write_node)
    g.add_node("return_result",     _return_result_node)
    g.add_node("give_up",           _give_up_node)

    g.add_edge(START,              "parse_intent")
    g.add_edge("parse_intent",     "check_cache")
    g.add_conditional_edges("check_cache", _after_cache,
                            {"return_result": "return_result", "resolve": "resolve"})
    g.add_edge("resolve",          "route")
    g.add_edge("route",            "fetch_source")
    g.add_edge("fetch_source",     "verify_candidates")
    g.add_conditional_edges("verify_candidates", _after_verify,
                            {"cache_write": "cache_write",
                             "fetch_source": "fetch_source",
                             "give_up": "give_up"})
    g.add_edge("cache_write",      "return_result")
    g.add_edge("return_result",    END)
    g.add_edge("give_up",          END)

    return g.compile()


# ── Public entry point ────────────────────────────────────────────────────────

def _initial_state(query: str) -> "AgentState":
    return {
        "query":               query,
        "intent":              {},
        "pending_sources":     [],
        "candidates":          [],
        "verified":            None,
        "verified_candidates": [],
        "attempt_count":       0,
        "start_time":          0.0,
        "search_cut_short":    False,
        "final_result":        None,
    }


def run_agent(query: str) -> dict:
    """Run the full IDF pipeline for a free-text query."""
    # Fund/ETF pre-filter: reject before any discovery/verification (funds are out
    # of scope; their 2-page tailored shareholder reports would false-reject on the
    # Signal-3 length gate). Runs before the LLM parse — no cost for a fund query.
    rejected = fund_reject_result(query)
    if rejected is not None:
        logger.info(f"[fund_filter] rejected fund/ETF query {query!r} — {rejected['reason'][:60]}")
        return rejected
    graph = build_graph()
    try:
        final_state = graph.invoke(_initial_state(query))
        return final_state.get("final_result") or {
            "ok": False, "reason": "Agent returned no result"
        }
    except Exception as exc:
        logger.error(f"Agent raised: {exc}")
        return {"ok": False, "reason": str(exc)}


# Plain-language status for each graph node, for a live progress display. These
# are ADDITIVE — the internal logging.info() strings are unchanged; these are
# derived by observing graph.stream() deltas, so no node internals are touched.
_STEP_MESSAGES = {
    "parse_intent":      "Understanding your query…",
    "check_cache":       "Checking the cache…",
    "resolve":           "Resolving the company…",
    "route":             "Deciding where to look…",
    "verify_candidates": "Verifying the document…",
    "cache_write":       "Saving the verified result…",
}
_SOURCE_MESSAGES = {
    "edgar":             "Checking SEC EDGAR…",
    "nse":               "Checking NSE India…",
    "company_site":      "Checking the company's investor-relations site…",
    "aggregators":       "Checking report aggregators…",
    "web_search":        "Searching the web…",
    "web_search_mirror": "Searching report mirrors…",
}


def run_agent_stream(query: str):
    """Generator variant of run_agent: yields a structured progress event as each
    graph step completes, then a final result event. Additive — run_agent stays
    the synchronous entry point and is unchanged.

    Events (JSON-serialisable dicts):
      {"type": "step",   "step": <node>, "message": <plain-language status>}
      {"type": "result", "result": <same dict run_agent returns>}
    """
    # Fund/ETF pre-filter (see run_agent): reject before any discovery. Emit only a
    # single result event — no step events — so the UI shows the message immediately.
    rejected = fund_reject_result(query)
    if rejected is not None:
        logger.info(f"[fund_filter] rejected fund/ETF query {query!r}")
        yield {"type": "result", "result": rejected}
        return
    graph = build_graph()
    result = None
    pending: list = []
    try:
        # stream_mode="updates" (default): each chunk is {node_name: state_delta}
        # emitted right after that node runs — the real step-by-step timeline.
        for chunk in graph.stream(_initial_state(query)):
            for node, delta in chunk.items():
                delta = delta or {}
                if node == "route":
                    pending = list(delta.get("pending_sources") or [])
                    yield {"type": "step", "step": node, "message": _STEP_MESSAGES[node]}
                elif node == "fetch_source":
                    # The source just fetched is the one popped off the queue since
                    # the previous step; name it, then track the remaining queue.
                    src = pending[0] if pending else None
                    pending = list(delta.get("pending_sources") or [])
                    yield {"type": "step", "step": node,
                           "message": _SOURCE_MESSAGES.get(src, "Searching for the document…")}
                elif node in _STEP_MESSAGES:
                    yield {"type": "step", "step": node, "message": _STEP_MESSAGES[node]}
                if node in ("return_result", "give_up") and delta.get("final_result"):
                    result = delta["final_result"]
    except Exception as exc:
        logger.error(f"Agent (stream) raised: {exc}")
        result = {"ok": False, "reason": str(exc)}
    yield {"type": "result",
           "result": result or {"ok": False, "reason": "Agent returned no result"}}


# ── Source dispatcher ─────────────────────────────────────────────────────────

def _dispatch(name: str, intent: dict) -> list[dict]:
    try:
        if name == "edgar":
            from sources.edgar import fetch_10k_candidates
            return fetch_10k_candidates(intent)
        if name == "nse":
            from sources.nse import NSESource
            return NSESource().find_candidates(intent)
        if name == "company_site":
            from sources.company_site import CompanySiteSource
            return CompanySiteSource().find_candidates(intent)
        if name == "aggregators":
            from sources.aggregators import AggregatorsSource
            return AggregatorsSource().find_candidates(intent)
        if name == "web_search":
            from sources.web_search import WebSearchSource
            return WebSearchSource().find_candidates(intent)
        if name == "web_search_mirror":
            from sources.web_search import find_web_mirror_candidates
            return find_web_mirror_candidates(intent)
        logger.warning(f"Unknown source: {name!r}")
    except Exception as exc:
        logger.error(f"Source {name!r} error: {exc}")
    return []
