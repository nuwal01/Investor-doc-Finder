"""
IDF FastAPI backend — thin wrapper around run_agent() for the HTML frontend.

Run:
  uvicorn api:app --reload --port 8000

Then open http://localhost:8000/  (frontend is served from ./frontend).

Endpoints:
  POST /search   → {"query": str} → the EXACT dict run_agent() returns, plus a
                   "logs" key (captured pipeline trace). Both ok:true and
                   ok:false shapes are passed through unmodified.
  /              → static frontend (mounted last so it can't shadow /search)
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import run_agent, run_agent_stream
from pdf_delivery import resolve_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(title="IDF — Investor Doc Finder")

# CORS: localhost origins for local dev (frontend is same-origin when served
# off this app, but keep it for the dev-server case).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=300,
                       json_schema_extra={"example": "Apple 2022 annual report"})


# ── Log capture (same behaviour as streamlit_app._LogCapture / _run_with_logs;
# copied, not imported, because importing streamlit_app runs Streamlit at import).
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
    root.addHandler(capture)
    try:
        result = run_agent(query)
    except Exception as exc:
        result = {"ok": False, "reason": str(exc)}
    finally:
        root.removeHandler(capture)
    return result, capture.records


@app.post("/search")
def search(req: SearchRequest) -> dict:
    """Run the agent; return run_agent()'s dict verbatim plus a 'logs' key."""
    result, logs = _run_with_logs(req.query.strip())
    return {**result, "logs": logs}


@app.get("/search/stream")
def search_stream(query: str = Query(..., min_length=3, max_length=300)):
    """Server-Sent Events: emit a progress event as each pipeline step completes,
    then a final 'result' event carrying the same dict POST /search returns (plus
    'logs'). Separate GET endpoint so POST /search stays unchanged for clients
    that don't stream; the browser consumes this with EventSource.
    """
    def gen():
        # ponytail: root handler captures all logging during the run (same pattern
        # as _run_with_logs); fine for this single-user local tool.
        capture = _LogCapture()
        root = logging.getLogger()
        root.addHandler(capture)
        try:
            for event in run_agent_stream(query.strip()):
                if event.get("type") == "result":
                    event = {**event, "logs": capture.records}
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            payload = {"type": "result", "result": {"ok": False, "reason": str(exc)},
                       "logs": capture.records}
            yield f"data: {json.dumps(payload)}\n\n"
        finally:
            root.removeHandler(capture)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/download")
def download(
    url: str = Query(..., min_length=8),
    source: str = Query(""),
    is_pdf: bool = Query(False),
    company: str = Query(""),
    fy: str = Query(""),
):
    """Resolve a result to PDF bytes in memory and serve it as a browser download.

    GET (not POST) so the endpoint is a plain, linkable/testable download URL and
    the browser handles it natively. Reuses pdf_delivery.resolve_pdf — the SAME
    logic the Streamlit UI uses; no conversion/fetch logic is duplicated here.
    """
    result = {"url": url, "source": source, "is_pdf": is_pdf,
              "company": company, "matched_fy": fy}
    try:
        out = resolve_pdf(result)
    except Exception as exc:  # network / conversion failure — never crash
        raise HTTPException(status_code=502, detail=f"Could not retrieve document: {exc}")
    if out is None:
        raise HTTPException(
            status_code=422,
            detail="No downloadable PDF for this source — open the original link instead.",
        )
    pdf_bytes, filename = out
    # RFC 5987: ASCII fallback + UTF-8 name so accented filenames (e.g. Hermès) survive.
    ascii_name = filename.encode("ascii", "ignore").decode() or "document.pdf"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": disposition})


# Mount the frontend LAST — StaticFiles at "/" would otherwise shadow /search.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
