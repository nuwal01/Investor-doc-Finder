"""
SQLite cache for verified results (Step 5).

Key: (company_canonical, fiscal_year, doc_type)
Value: url, matched_fy, is_pdf, source, verified_at

company_canonical strips common suffixes and lowercases for stable matching
across e.g. "Apple Inc." vs "Apple Inc" vs "apple".

Writes also append new company/CIK rows to data/company_map.csv so future
queries resolve without hitting the EDGAR tickers API.
"""

import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "cache.db"
COMPANY_MAP = Path(__file__).parent / "data" / "company_map.csv"

_SUFFIXES = (" inc.", " inc", " corp.", " corp", " ltd.", " ltd", " limited", " llc", " plc")


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
    n = name.lower().strip()
    for sfx in _SUFFIXES:
        if n.endswith(sfx):
            n = n[: -len(sfx)].strip()
    return n


def cache_get(company: str, fiscal_year: int, doc_type: str) -> dict | None:
    _init()
    k = _key(company)
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM results WHERE company_canonical=? AND fiscal_year=? AND doc_type=?",
            (k, fiscal_year, doc_type),
        ).fetchone()
    if row:
        logger.info(f"Cache HIT: {k!r} FY{fiscal_year} {doc_type}")
        return dict(row)
    logger.debug(f"Cache MISS: {k!r} FY{fiscal_year} {doc_type}")
    return None


def cache_put(company: str, fiscal_year: int, doc_type: str, result: dict, intent: dict | None = None) -> None:
    _init()
    k = _key(company)
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO results
              (company_canonical, fiscal_year, doc_type, url, matched_fy, is_pdf, source, form_type, verified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                k, fiscal_year, doc_type,
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
