"""Fund/ETF pre-filter — reject fund/ETF queries before the pipeline runs.

Why: SEC Tailored Shareholder Reports (2-page annual reports for mutual funds /
ETFs, mandatory since July 2024) are legitimate documents but OUT OF SCOPE for
this tool, which finds operating-company annual reports and 10-K filings. They
would false-reject on verify.py's Signal-3 length floor. Rather than a length-
gate exception (funds aren't an edge case to accommodate — they don't belong
here at all), detect these queries UPSTREAM and return a clear "not supported"
message with no retrieval or verification.

Detection is deliberately HIGH-PRECISION over high-recall: an ambiguous query is
better let through to the normal pipeline (where it may correctly give_up, or at
worst length-reject) than to wrongly block a legitimate operating-company query.
So it fires ONLY on unambiguous fund-vehicle markers and pure ETF brand names,
and deliberately does NOT fire on:
  - bare "trust" / "index"  — REITs ("Camden Property Trust") and index providers
    ("MSCI", "S&P Global") are operating companies with normal-length 10-Ks; and
  - fund-MANAGER names ("BlackRock", "Franklin Resources", "Vanguard", "Invesco",
    "Schwab", "Fidelity") — these are operating companies that file their own 10-Ks.

KNOWN false negatives (intentionally let through, per the precision-first choice):
bare fund TICKERS (IVV, QQQ — no cheap local fund-ticker source exists) and funds
named without a marker word ("Pershing Square Holdings", "Invesco QQQ Trust").
Those flow through the normal pipeline and typically give_up or length-reject —
the accepted residual risk.
"""
import re

# Unambiguous fund/ETF VEHICLE markers (whole-word / phrase, case-insensitive).
# Bare "trust" and bare "index" are excluded on purpose (see module docstring).
_FUND_MARKERS = (
    r"\betfs?\b",                       # ETF / ETFs
    r"\bexchange[-\s]traded\b",         # exchange-traded fund
    r"\bmutual\s+fund",
    r"\bindex\s+fund",
    r"\bfund\b",                        # "... Income Fund", "closed-end fund"
    r"\bclosed[-\s]end\b",
    r"\bunit\s+trust\b",
    r"\binvestment\s+trust\b",          # UK closed-end funds (NOT bare "trust")
    r"\bucits\b", r"\bsicav\b", r"\boeic\b",   # EU / UK fund vehicles
)

# Pure ETF/fund BRAND names — essentially never an operating company queried for a
# 10-K. Manager names (BlackRock/Vanguard/Invesco/Franklin/Schwab/Fidelity/State
# Street) are deliberately EXCLUDED: they file their own 10-Ks as operating cos.
_FUND_FAMILIES = (
    r"\bishares\b", r"\bspdr\b", r"\bproshares\b", r"\bvaneck\b",
    r"\bwisdomtree\b", r"\bflexshares\b", r"\bglobal\s+x\b", r"\bdirexion\b",
)

_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _FUND_MARKERS + _FUND_FAMILIES)


def is_fund_query(query: str) -> tuple[bool, str | None]:
    """(True, matched_signal) if the query unambiguously names a fund/ETF, else
    (False, None). High-precision — see the module docstring for FN/FP tradeoffs."""
    for pat in _PATTERNS:
        m = pat.search(query or "")
        if m:
            return True, m.group(0).strip()
    return False, None


def fund_reject_result(query: str) -> dict | None:
    """The distinct 'not supported' result for a fund/ETF query, or None to let the
    query flow through to the normal pipeline. Called BEFORE any discovery or
    verification, so a detected fund never reaches retrieval/verify()."""
    is_fund, signal = is_fund_query(query)
    if not is_fund:
        return None
    return {
        "ok": False,
        "unsupported": True,   # distinct from a normal give_up (ok:false)
        "reason": (
            "Fund/ETF documents are not supported. This query looks like a mutual "
            f"fund or ETF (matched {signal!r}). This tool finds annual reports and "
            "10-K filings for operating companies; fund shareholder reports "
            "(Form N-CSR / tailored shareholder reports) are out of scope."
        ),
        "company": query,
        "fiscal_year": None,
        "fallback": None,
    }
