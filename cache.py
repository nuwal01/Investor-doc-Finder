"""
SQLite cache for verified results (Step 5).

Key: (company_canonical, fiscal_year, doc_type)
Value: url, matched_fy, is_pdf, source, verified_at

company_canonical accent-folds, lowercases, and drops generic/corporate/
descriptor tokens for stable matching across surface-form variants, e.g.
"Apple Inc." / "Apple Inc" / "apple", "ASML Holding NV" / "ASML", "Hermès" /
"Hermes". doc_type is normalised too ("annual report" -> "annual_report").

Writes also append new company/CIK rows to data/company_map.csv so future
queries resolve without hitting the EDGAR tickers API.
"""

import csv
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from verify import _GENERIC_TOKENS, _normalize

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "cache.db"
COMPANY_MAP = Path(__file__).parent / "data" / "company_map.csv"

# Tokens dropped when building the company key. Reuses verify._GENERIC_TOKENS
# (the vetted distinguishing-token list — already covers inc/ltd/corp/corporation/
# company/co/india/group/industries/international/national/…) and adds only the
# corporate forms it lacks (plc/llc) plus ENTITY-TYPE descriptors (holding/
# holdings/pharmaceuticals/pharma) — words that denote a company's STRUCTURE, not
# its industry, so "X Holdings"/"X" and "X Pharmaceuticals"/"X" are the same
# issuer. 2-char corporate forms (SA/NV/AG/BV) need no listing: the len>2 filter
# drops them.
#
# "oil" was DELIBERATELY EXCLUDED (investigated Prompt J). It is an INDUSTRY word
# and a genuine discriminator: stripping it merges DISTINCT companies — "Marathon
# Oil" collapses onto "Marathon". It was load-bearing only for the Tullow Oil <->
# Tullow merge, and no structural guard can strip it for "Tullow Oil" while
# sparing the identically-shaped "Marathon Oil" (both are <core> + "oil"). Losing
# that merge is benign — at worst a duplicate cache row if the resolver returns
# "Tullow" one run and "Tullow Oil" the next — whereas merging two real companies
# would be a correctness bug. Industry descriptors therefore stay in the key.
_STRIP_TOKENS: frozenset[str] = _GENERIC_TOKENS | frozenset({
    "plc", "llc", "holding", "holdings", "pharmaceuticals", "pharma",
})


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS results (
                company_canonical TEXT NOT NULL,
                fiscal_year       INTEGER NOT NULL,
                doc_type          TEXT NOT NULL,
                url               TEXT NOT NULL,
                matched_fy        TEXT,
                is_pdf            INTEGER DEFAULT 0,
                source            TEXT,
                form_type         TEXT,
                pdf_path          TEXT,
                verified_at       TEXT NOT NULL,
                PRIMARY KEY (company_canonical, fiscal_year, doc_type)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_co ON results (company_canonical)")
        # Migrations for DBs created before a column existed (idempotent).
        cols = {r["name"] for r in c.execute("PRAGMA table_info(results)")}
        if "form_type" not in cols:
            c.execute("ALTER TABLE results ADD COLUMN form_type TEXT")
        if "pdf_path" not in cols:
            c.execute("ALTER TABLE results ADD COLUMN pdf_path TEXT")


def _key(name: str) -> str:
    """Canonical company key. Accent-fold + lowercase (verify._normalize), split on
    any non-alphanumeric run, drop <=2-char tokens and generic/corporate/descriptor
    tokens, join the rest. Folds punctuation / spacing / accent / suffix variants
    onto one key: "ASML Holding NV"/"ASML" -> "asml"; "Avianca S.A."/"Avianca SA"
    -> "avianca"; "R R Kabel"/"RR Kabel" -> "kabel"; "Hermès"/"Hermes" -> "hermes".
    Industry words like "oil" are NOT stripped (see _STRIP_TOKENS), so "Tullow Oil"
    and "Tullow" deliberately do NOT merge — the price of not merging "Marathon
    Oil" onto "Marathon".

    Never returns empty: if every token is generic and thus stripped (e.g.
    "International Industries Ltd"), it backs off to the len>2 tokens, then to the
    raw tokens — so an all-generic name is preserved rather than collapsing to
    nothing."""
    toks = re.sub(r"[^a-z0-9]+", " ", _normalize(name)).split()
    kept = [t for t in toks if len(t) > 2 and t not in _STRIP_TOKENS]
    if not kept:
        kept = [t for t in toks if len(t) > 2] or toks
    if not kept:
        # No alphanumeric tokens at all (e.g. "!!!") — fall back to the
        # normalized name itself so the key is never empty.
        return _normalize(name).strip() or name
    return " ".join(kept)


def _norm_doc_type(doc_type: str) -> str:
    """Canonical doc_type: lowercase, runs of whitespace -> single underscore.
    Collapses the "annual report" / "annual_report" split onto the underscore
    form (the majority of existing rows). "10-K" -> "10-k" (hyphen preserved)."""
    return re.sub(r"\s+", "_", (doc_type or "").strip().lower())


def cache_get(company: str, fiscal_year: int, doc_type: str) -> dict | None:
    _init()
    k = _key(company)
    dt = _norm_doc_type(doc_type)
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM results WHERE company_canonical=? AND fiscal_year=? AND doc_type=?",
            (k, fiscal_year, dt),
        ).fetchone()
    if row:
        logger.info(f"Cache HIT: {k!r} FY{fiscal_year} {dt}")
        return dict(row)
    logger.debug(f"Cache MISS: {k!r} FY{fiscal_year} {dt}")
    return None


def cache_put(company: str, fiscal_year: int, doc_type: str, result: dict, intent: dict | None = None) -> None:
    _init()
    k = _key(company)
    dt = _norm_doc_type(doc_type)
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO results
              (company_canonical, fiscal_year, doc_type, url, matched_fy, is_pdf, source, form_type, verified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                k, fiscal_year, dt,
                result.get("url", ""),
                result.get("matched_fy"),
                1 if result.get("is_pdf") else 0,
                result.get("source", ""),
                result.get("form_type", ""),
                now,
            ),
        )
    logger.info(f"Cache WRITE: {k!r} FY{fiscal_year} → {result.get('url','')[:60]}")

    # Write-back: append newly resolved CIK to company_map.csv
    if intent and intent.get("cik") and intent.get("ticker_or_id"):
        _append_company_map(intent)


def _append_company_map(intent: dict) -> None:
    """Add a newly resolved company to data/company_map.csv (idempotent)."""
    cik = intent.get("cik", "")
    ticker = intent.get("ticker_or_id", "")
    name = intent.get("company_name", "")
    country = intent.get("country", "")

    if not cik or not name:
        return

    existing = set()
    if COMPANY_MAP.exists():
        with open(COMPANY_MAP, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing.add(row.get("cik", "").strip())

    if cik.lstrip("0") in {c.lstrip("0") for c in existing}:
        return  # already in table

    with open(COMPANY_MAP, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([name, ticker, country, cik, "", name])
    logger.info(f"company_map.csv: appended {name!r} CIK={cik}")
