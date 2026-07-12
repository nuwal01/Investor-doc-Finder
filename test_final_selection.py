"""
Tests for the final-result precedence logic added to agent.py
(_select_final / accumulate-then-sort in _return_result_node).

Fully offline: the LLM, resolver, cache, source dispatch, and verifier are all
stubbed, so the graph's control flow and selection are exercised without any
network, API keys, or SQLite state.
"""

import agent
from sources import web_search as ws


# ── Fix 3: form_type parsing ──────────────────────────────────────────────────

def test_parse_form_type_extracts_each_form():
    assert agent._parse_form_type("EDGAR 20-F: Asml FY2023 (fpi) — HTML") == "20-F"
    assert agent._parse_form_type("EDGAR 10-K: Apple FY2022 — PDF") == "10-K"
    assert agent._parse_form_type("EDGAR 40-F: Shopify FY2023 — HTML") == "40-F"


def test_parse_form_type_absent_returns_empty():
    assert agent._parse_form_type("PDF scraped from example.com") == ""
    assert agent._parse_form_type("") == ""
    assert agent._parse_form_type(None) == ""


# ── Fix 4: UK-listed detection ────────────────────────────────────────────────

def test_is_uk_listed():
    assert ws._is_uk_listed({"country": "GB"}) is True
    assert ws._is_uk_listed({"country": None, "company_name": "Tullow Oil plc"}) is True
    assert ws._is_uk_listed({"country": "US", "company_name": "Apple Inc"}) is False


# ── _select_final unit tests ──────────────────────────────────────────────────

def test_regulatory_source_beats_web_pdf_regardless_of_format():
    """EDGAR HTML must win over a web_search PDF — source_priority is primary."""
    winner = agent._select_final([
        {"source": "web_search", "is_pdf": True,  "url": "web.pdf"},
        {"source": "edgar",      "is_pdf": False, "url": "edgar.htm"},
    ])
    assert winner["source"] == "edgar"
    assert winner["is_pdf"] is False   # returned as HTML, no conversion


def test_pdf_preferred_as_tiebreaker_within_same_priority():
    """Same source (same priority) → PDF wins over HTML (is_pdf inverted)."""
    winner = agent._select_final([
        {"source": "web_search", "is_pdf": False, "url": "web.htm"},
        {"source": "web_search", "is_pdf": True,  "url": "web.pdf"},
    ])
    assert winner["is_pdf"] is True
    assert winner["url"] == "web.pdf"


def test_nse_treated_as_regulatory():
    assert agent._source_priority("nse") == 0
    assert agent._source_priority("edgar") == 0
    assert agent._source_priority("web_search") == 1
    assert agent._source_priority("company_site") == 1
    assert agent._source_priority("aggregators") == 1


def test_select_final_empty_list_is_safe():
    assert agent._select_final([]) == {}


# ── end-to-end graph tests (accumulate then sort) ─────────────────────────────

_INTENT = {
    "company_name": "Asml Holding", "raw_company": "ASML Holding",
    "country": "US", "ticker_or_id": None, "cik": "0000937966",
    "fiscal_year": 2023, "fy_candidates": ["2023"],
    "doc_type": "annual_report",
}


def _stub_common(monkeypatch, dispatched):
    """Stub LLM/resolver/cache so run_agent runs fully offline."""
    monkeypatch.setattr(agent, "_parse_intent", lambda q: dict(_INTENT))
    monkeypatch.setattr(agent, "_resolve", lambda intent: intent)
    monkeypatch.setattr(agent, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(agent, "cache_put", lambda *a, **k: None)

    def fake_verify(cand, intent):
        return {
            "ok": True,
            "reason": "stub",
            "matched_fy": "2023",
            "is_pdf": cand["url"].endswith(".pdf"),
            "content_type": "application/pdf" if cand["url"].endswith(".pdf") else "text/html",
        }

    monkeypatch.setattr(agent, "_verify", fake_verify)

    def fake_dispatch(name, intent):
        dispatched.append(name)
        if name == "edgar":
            return [{"url": "https://sec.gov/edgar/asml-20f.htm",
                     "source": "edgar", "note": "20-F"}]
        if name == "web_search":
            return [{"url": "https://example.com/asml-annual-report-2023.pdf",
                     "source": "web_search", "note": "IR PDF"}]
        return []

    monkeypatch.setattr(agent, "_dispatch", fake_dispatch)


def test_edgar_html_selected_over_web_search_pdf_end_to_end(monkeypatch):
    """The ASML scenario, offline: a tier-0 (EDGAR) candidate verifies, so the
    pipeline SHORT-CIRCUITS — web_search is NOT fetched, since nothing tier-1 could
    outrank a tier-0 winner. (Before the tier-0 short-circuit, both sources ran and
    EDGAR won on precedence; now EDGAR wins without the extra tier-1 fetch.)"""
    dispatched = []
    _stub_common(monkeypatch, dispatched)

    result = agent.run_agent("ASML Holding 2023 annual report")

    assert result["ok"] is True
    assert result["source"] == "edgar"          # precedence winner
    assert result["is_pdf"] is False            # HTML, unconverted
    assert result["form_type"] == "20-F"        # Fix 3: parsed from the note
    # Tier-0 (EDGAR) verified → pipeline short-circuits; web_search is NOT fetched.
    assert "edgar" in dispatched and "web_search" not in dispatched


def test_web_search_pdf_wins_when_edgar_fails_verification(monkeypatch):
    """If the only verified candidate is the web_search PDF, it is returned."""
    dispatched = []
    _stub_common(monkeypatch, dispatched)

    def fake_verify(cand, intent):
        ok = cand["source"] != "edgar"   # EDGAR candidate fails verification
        return {
            "ok": ok,
            "reason": "stub-fail" if not ok else "stub",
            "matched_fy": "2023" if ok else None,
            "is_pdf": cand["url"].endswith(".pdf"),
            "content_type": "application/pdf" if cand["url"].endswith(".pdf") else "text/html",
        }

    monkeypatch.setattr(agent, "_verify", fake_verify)

    result = agent.run_agent("ASML Holding 2023 annual report")

    assert result["ok"] is True
    assert result["source"] == "web_search"
    assert result["is_pdf"] is True
