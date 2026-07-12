"""
IDF FastAPI backend (Step 8).

Run:
  uvicorn api:app --reload --port 8000

Endpoints:
  GET  /              → API info
  GET  /health        → liveness check
  POST /api/search    → run the IDF agent; returns verified result or not-found
  GET  /api/cache     → list the 20 most-recently cached results
  GET  /docs          → auto-generated Swagger UI (built into FastAPI)
"""

import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import run_agent
from cache import DB_PATH, _init

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="IDF — Investor Doc Finder API",
    description=(
        "Give a free-text query like **'Apple 2022 annual report'** and get back "
        "a verified PDF or regulatory filing URL. "
        "Covers US (SEC EDGAR), India (Screener.in), and global companies (web search)."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=300,
                       example="Apple 2022 annual report")

class SearchResponse(BaseModel):
    ok:           bool
    url:          str | None = None
    company:      str | None = None
    country:      str | None = None
    fiscal_year:  int | None = None
    matched_fy:   str | None = None
    is_pdf:       bool       = False
    doc_returned: str | None = None
    source:       str | None = None
    reason:       str | None = None   # present only when ok=False


class CacheRow(BaseModel):
    company_canonical: str
    fiscal_year:       int
    doc_type:          str
    url:               str
    matched_fy:        str | None
    is_pdf:            bool
    source:            str | None
    verified_at:       str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
def root():
    return {
        "service": "IDF — Investor Doc Finder",
        "version": "0.1.0",
        "docs":    "/docs",
        "search":  "POST /api/search",
        "cache":   "GET  /api/cache",
    }


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse, tags=["search"])
def search(req: SearchRequest):
    """
    Run the IDF agent for the given query.

    Returns a verified document URL on success, or `ok=false` with a `reason`
    when no document could be found/verified.  Typical latency: 5–20 s on first
    run (network + LLM); subsequent calls for the same company/year are served
    from the SQLite cache in < 50 ms.
    """
    result = run_agent(req.query)
    return SearchResponse(**{k: result.get(k) for k in SearchResponse.model_fields})


@app.get("/api/cache", response_model=list[CacheRow], tags=["cache"])
def list_cache(limit: int = 20):
    """Return the most recent `limit` verified results from the SQLite cache."""
    _init()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM results ORDER BY verified_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [CacheRow(**dict(r)) for r in rows]
