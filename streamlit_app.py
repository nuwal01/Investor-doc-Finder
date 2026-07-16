"""
IDF Streamlit UI (Step 7).

Run:
  streamlit run streamlit_app.py

Features:
  • Search box + example-query buttons
  • Real-time pipeline trace (captured from logging)
  • Result card with format badge + clickable download link
  • Persistent session state (result survives page interactions)
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from agent import run_agent
from pdf_delivery import resolve_pdf


def _resolve_pdf(result: dict) -> tuple[bytes, str] | None:
    """Session-cached wrapper around pdf_delivery.resolve_pdf so Streamlit's
    per-interaction reruns don't re-fetch (already-PDF) or re-convert (EDGAR
    ~8-45s). The outcome — including None — is cached keyed to the result URL; a
    genuine retry is a fresh search (new URL key)."""
    url = result.get("url", "")
    cache = st.session_state.setdefault("_pdf_cache", {})
    if url in cache:
        return cache[url]
    out = resolve_pdf(result)
    cache[url] = out
    return out

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IDF — Investor Doc Finder",
    page_icon="📄",
    layout="centered",
)

# ── Log capture ───────────────────────────────────────────────────────────────

class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []
        self.setFormatter(logging.Formatter("%(levelname)-8s [%(name)s]  %(message)s"))

    def emit(self, record: logging.LogRecord):
        self.records.append(self.format(record))


def _run_with_logs(query: str) -> tuple[dict, list[str]]:
    capture = _LogCapture()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(capture)
    try:
        result = run_agent(query)
    except Exception as exc:
        result = {"ok": False, "reason": str(exc)}
    finally:
        root.removeHandler(capture)
    return result, capture.records


# ── Session state defaults ────────────────────────────────────────────────────

for _k, _v in [("result", None), ("logs", []), ("last_query", "")]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📄 Investor Doc Finder")
st.caption(
    "Enter any company + year and get a verified annual report or 10-K link. "
    "Works for US (SEC EDGAR), India (Screener.in), and global companies (web search)."
)
st.divider()

# ── Example buttons ───────────────────────────────────────────────────────────

EXAMPLES = [
    "Apple 2022 annual report",
    "Microsoft 2023 10-K",
    "Tesla 2021 annual report",
    "Infosys FY2023 annual report",
]

st.markdown("**Try an example:**")
cols = st.columns(len(EXAMPLES))
for i, ex in enumerate(EXAMPLES):
    with cols[i]:
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.last_query = ex
            st.rerun()

# ── Search form ───────────────────────────────────────────────────────────────

with st.form("search"):
    query = st.text_input(
        "Query",
        value=st.session_state.last_query,
        placeholder='e.g. "Reliance Industries 2022 annual report"',
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("🔍 Find Document", type="primary", use_container_width=True)

if submitted and query.strip():
    st.session_state.last_query = query.strip()
    with st.spinner("Searching… this takes up to 45 s on first run"):
        result, logs = _run_with_logs(query.strip())
    st.session_state.result = result
    st.session_state.logs = logs

# ── Result card ───────────────────────────────────────────────────────────────

result = st.session_state.result
if result is not None:
    st.divider()
    if result.get("ok"):
        url       = result["url"]
        is_pdf    = result.get("is_pdf", False)
        fmt_badge = "🟢 PDF" if is_pdf else "🟡 HTML"
        doc_type  = result.get("doc_returned", "document")
        company   = result.get("company", "")
        fy        = result.get("matched_fy", "")
        source    = result.get("source", "")
        form_type = result.get("form_type", "")
        country   = result.get("country", "")

        st.success("✅ Document found")

        source_line = f"Format: {fmt_badge} &nbsp;&nbsp; Source: `{source}`"
        if form_type:
            source_line += f" &nbsp;&nbsp; Form: `{form_type}`"

        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**{company}**  `{country}`")
            st.markdown(f"Fiscal year matched: **{fy}**")
            st.markdown(f"Document: {doc_type}")
            st.markdown(source_line, unsafe_allow_html=True)
        with c2:
            err = None
            try:
                pdf = _resolve_pdf(result)
            except Exception as exc:  # network / conversion failure — never crash
                pdf, err = None, str(exc)

            if pdf:
                data, fname = pdf
                st.download_button(
                    "📥 Download PDF", data=data, file_name=fname,
                    mime="application/pdf", use_container_width=True, type="primary",
                )
            else:
                if err:
                    st.error(f"PDF unavailable — {err}")
                elif source == "edgar":
                    st.error("PDF conversion unavailable (wkhtmltopdf missing or "
                             "conversion failed).")
                st.link_button("📥 Open original", url, use_container_width=True,
                               type="primary")

        st.code(url, language="text")

    else:
        reason = result.get("reason", "unknown")
        st.error(f"❌ Not found — {reason}")

        # Tiered fallback link (present only on give_up). Rendered DISTINCTLY per
        # confidence so a curated/verified domain is never styled like an unverified
        # web-search guess.
        fallback = result.get("fallback")
        if fallback:
            fb_url = fallback.get("url", "")
            conf   = fallback.get("confidence")
            tier   = fallback.get("tier")
            if conf == "verified":
                st.markdown("#### 🔗 Company investor-relations site")
                st.caption("Curated official domain (verified).")
                st.link_button("Open IR site", fb_url, type="primary")
            elif conf == "uncertain":
                st.warning(
                    "⚠️ **Possible** investor-relations site — this may not be the exact "
                    "company you're looking for if your search terms were ambiguous."
                )
                st.link_button("Open (uncertain match)", fb_url)
            else:  # "unverified" — Tier 2 live search
                st.info(
                    "🔎 **Unverified suggestion** — a best-effort *“investor relations”* "
                    "web-search result. **Not checked**: it may be the wrong company or not a "
                    "report at all. Treat as a lead, not a verified document."
                )
                st.markdown(f"↗︎ [{fb_url}]({fb_url})")
            st.caption(f"Fallback: tier {tier} · confidence `{conf}`")

        st.markdown(
            "**Suggestions:** Try a more specific query, check the company name spelling, "
            "or add the country name (e.g. 'Reliance Industries **India** 2022 annual report')."
        )

    # ── Pipeline trace ────────────────────────────────────────────────────────
    logs = st.session_state.logs
    with st.expander(
        f"Pipeline trace ({len(logs)} log lines)",
        expanded=not result.get("ok"),
    ):
        if logs:
            st.code("\n".join(logs), language="text")
        else:
            st.caption("No log records captured.")
