"""SQLite-backed search history, keyed by an anonymous client session id.

Separate concern from cache.py's verified-document cache: this is a per-session,
append-only log of what was searched and how it resolved, powering the "Recent
searches" panel. It uses its OWN database file (history.db) and never touches
cache.db.

Postgres was the original plan, but no Postgres instance exists in this
environment (no server, no connection string, no deploy infra), and the project
already persists with SQLite — so history uses SQLite too: zero new
infrastructure, identical behaviour locally and in deployment.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "history.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT NOT NULL,
                query_text       TEXT NOT NULL,
                resolved_company TEXT,
                matched_fy       TEXT,
                result_url       TEXT,
                status           TEXT NOT NULL,
                created_at       TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_session ON history (session_id, id)")


def add_entry(session_id: str, query_text: str, result: dict) -> None:
    """Append one completed search (ok or give_up) for a session. No-op without a
    session id or query. result_url takes the verified URL, else a give_up
    fallback URL (there is no persistent pdf_path — EDGAR PDFs render in memory)."""
    session_id = (session_id or "").strip()
    query_text = (query_text or "").strip()
    if not session_id or not query_text:
        return
    _init()
    status = "ok" if result.get("ok") else "give_up"
    url = result.get("url") or (result.get("fallback") or {}).get("url") or None
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            """INSERT INTO history
                 (session_id, query_text, resolved_company, matched_fy, result_url, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, query_text,
             result.get("company") or None,
             (str(result.get("matched_fy")) if result.get("matched_fy") else None),
             url, status, now),
        )
    logger.info(f"History WRITE: session={session_id[:8]}… {status} {query_text[:50]!r}")


def get_history(session_id: str, limit: int = 50) -> list[dict]:
    """A session's past searches, most recent first. Empty list for an unknown
    session — never another session's rows."""
    session_id = (session_id or "").strip()
    if not session_id:
        return []
    _init()
    with _conn() as c:
        rows = c.execute(
            """SELECT query_text, resolved_company, matched_fy, result_url, status, created_at
               FROM history WHERE session_id = ? ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    # ponytail: one runnable check — session isolation + recency order + empty case.
    import tempfile
    DB_PATH = Path(tempfile.gettempdir()) / "idf_history_selftest.db"
    for sfx in ("", "-wal", "-shm"):
        p = Path(str(DB_PATH) + sfx)
        if p.exists():
            p.unlink()

    add_entry("sess-A", "Apple 2022 annual report", {"ok": True, "company": "Apple Inc.", "matched_fy": "2022", "url": "http://x/a"})
    add_entry("sess-A", "Tesla 2021 annual report", {"ok": False, "reason": "nope", "company": "Tesla, Inc."})
    add_entry("sess-B", "Reliance 2022", {"ok": True, "company": "Reliance", "matched_fy": "FY2022-23", "url": "http://x/r"})

    a = get_history("sess-A")
    assert [h["query_text"] for h in a] == ["Tesla 2021 annual report", "Apple 2022 annual report"], a
    assert a[0]["status"] == "give_up" and a[1]["status"] == "ok"
    assert len(get_history("sess-B")) == 1
    assert get_history("sess-UNKNOWN") == []
    print("ok")
