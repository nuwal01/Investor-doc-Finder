"""
Investor Doc Finder — FastAPI server with SSE streaming.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from agent import run_agent, run_agent_silent
from auth_middleware import db, verify_token
from utils.query_parser import parse_query
from utils.sse_manager import stream_events

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(title="Investor Doc Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str


class BulkCompanyRequest(BaseModel):
    company_name: str
    doc_type: str = "annual_report"
    year: int


class BulkSearchRequest(BaseModel):
    companies: list[BulkCompanyRequest]


async def _persist_search(uid: str, result: dict) -> None:
    """Save a search result to Firestore history as a background task.

    Runs the blocking Firestore call in a thread so it cannot block or be
    cancelled by the SSE event-generator's lifecycle.
    """
    if not db:
        print("[history] db is None — skipping save")
        return

    def _do_save():
        from firebase_admin import firestore as fs
        _, doc_ref = db.collection("users").document(uid).collection("searches").add(
            {**result, "fetched_at": fs.SERVER_TIMESTAMP}
        )
        return doc_ref.id

    try:
        doc_id = await asyncio.to_thread(_do_save)
        print(f"[history] Saved search → doc {doc_id} for uid {uid[:8]}…")
    except Exception as e:
        print(f"[history] Save failed: {e}")


@app.post("/search")
async def search(req: SearchRequest, request: Request):
    """Main search endpoint with SSE streaming. Requires a valid Firebase ID token."""
    user = await verify_token(request)
    user_uid = user["uid"]

    session_id = str(uuid.uuid4())
    parsed = parse_query(req.query)

    async def event_generator():
        # Start the agent pipeline as a background task
        agent_task = asyncio.create_task(run_agent(parsed, session_id, user_uid=user_uid))

        # Stream all SSE events from the agent
        async for event in stream_events(session_id):
            yield ServerSentEvent(data=json.dumps(event))

        # Await agent completion
        result = await agent_task
        if result:
            # ── Fire-and-forget Firestore save (background task so it can't
            #    be cancelled by EventSourceResponse closing the generator) ──
            asyncio.create_task(_persist_search(user_uid, result))

            yield ServerSentEvent(
                data=json.dumps({"event": "result", "data": json.dumps(result)}),
            )

    return EventSourceResponse(event_generator())


# ── Bulk search endpoint ──────────────────────────────────────────────────────


@app.post("/bulk-search")
async def bulk_search(req: BulkSearchRequest, request: Request):
    """Bulk search endpoint — runs all companies in parallel and streams SSE events."""
    user = await verify_token(request)
    user_uid = user["uid"]

    companies = req.companies
    if len(companies) == 0:
        raise HTTPException(status_code=400, detail="No companies provided")
    if len(companies) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 companies per request")

    current_year = datetime.now().year
    for c in companies:
        if c.year < 1990 or c.year > current_year + 1:
            raise HTTPException(status_code=400, detail=f"Invalid year {c.year} for '{c.company_name}'")
        if not c.company_name.strip():
            raise HTTPException(status_code=400, detail="Company name cannot be empty")

    total: int = len(companies)
    event_queue: asyncio.Queue = asyncio.Queue()
    semaphore = asyncio.Semaphore(5)

    async def fetch_one(company: BulkCompanyRequest, index: int) -> None:
        async with semaphore:
            name     = company.company_name.strip()
            doc_type = company.doc_type.strip()
            year     = company.year

            await event_queue.put({"type": "company_start", "index": index, "company_name": name})

            parsed = {
                "company_name": name,
                "doc_type":     doc_type,
                "year":         year,
                "raw_query":    f"{name} {doc_type.replace('_', ' ')} {year}",
            }

            try:
                result = await run_agent_silent(parsed, user_uid)
            except Exception:
                result = None

            if result:
                # Persist to Firestore
                if db:
                    try:
                        from firebase_admin import firestore as fs
                        db.collection("users").document(user_uid).collection("searches").add(
                            {**result, "fetched_at": fs.SERVER_TIMESTAMP}
                        )
                    except Exception:
                        pass

                await event_queue.put({
                    "type":         "company_result",
                    "index":        index,
                    "company_name": result.get("company_name", name),
                    "url":          result.get("url", ""),
                    "source":       result.get("source", ""),
                    "confidence":   result.get("confidence", "low"),
                    "score":        result.get("score", 0.0),
                })
            else:
                await event_queue.put({
                    "type":         "company_error",
                    "index":        index,
                    "company_name": name,
                    "reason":       "Document not found",
                })

    async def run_all() -> None:
        tasks = [asyncio.create_task(fetch_one(c, i)) for i, c in enumerate(companies)]
        await asyncio.gather(*tasks, return_exceptions=True)
        await event_queue.put({"type": "bulk_complete"})

    asyncio.create_task(run_all())

    async def event_generator():
        found  = 0
        failed = 0
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=600)
            except asyncio.TimeoutError:
                yield ServerSentEvent(
                    data=json.dumps({"type": "bulk_complete", "total": total, "found": found, "failed": failed})
                )
                break

            if event["type"] == "company_result":
                found  += 1
            elif event["type"] == "company_error":
                failed += 1
            elif event["type"] == "bulk_complete":
                event.update({"total": total, "found": found, "failed": failed})

            yield ServerSentEvent(data=json.dumps(event))

            if event["type"] == "bulk_complete":
                break

    return EventSourceResponse(event_generator())


# ── History endpoints ─────────────────────────────────────────────────────────


@app.get("/user/history")
async def get_history(request: Request):
    """Return the 50 most recent searches for the authenticated user."""
    user = await verify_token(request)
    uid = user["uid"]

    from firebase_admin import firestore as fs
    docs = (
        db.collection("users")
        .document(uid)
        .collection("searches")
        .order_by("fetched_at", direction=fs.Query.DESCENDING)
        .limit(50)
        .stream()
    )

    history = []
    for doc in docs:
        data = doc.to_dict()
        data["searchId"] = doc.id
        # Convert Firestore Timestamp to ISO string for JSON serialisation
        if "fetched_at" in data and data["fetched_at"] is not None:
            try:
                data["fetched_at"] = data["fetched_at"].isoformat()
            except AttributeError:
                pass
        history.append(data)

    return history


@app.delete("/user/history/{search_id}")
async def delete_history_item(search_id: str, request: Request):
    """Delete a single search history document."""
    user = await verify_token(request)
    uid = user["uid"]

    db.collection("users").document(uid).collection("searches").document(search_id).delete()
    return {"deleted": True}


@app.delete("/user/history")
async def clear_history(request: Request):
    """Delete all search history for the authenticated user."""
    user = await verify_token(request)
    uid = user["uid"]

    docs = db.collection("users").document(uid).collection("searches").stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1

    return {"deleted": count}


# ── Library endpoints ────────────────────────────────────────────────────────


class LibraryItem(BaseModel):
    url: str
    company_name: str
    doc_type: str
    year: int
    source: str = ""
    confidence: str = ""
    score: float = 0.0
    country: str = ""
    sector: str = ""


@app.post("/user/library")
async def save_to_library(item: LibraryItem, request: Request):
    """Save a document to the user's personal library."""
    user = await verify_token(request)
    uid = user["uid"]

    from firebase_admin import firestore as fs
    ref = db.collection("users").document(uid).collection("library").document()
    ref.set({**item.model_dump(), "saved_at": fs.SERVER_TIMESTAMP})
    return {"success": True, "doc_id": ref.id}


@app.get("/user/library")
async def get_library(request: Request):
    """Return all saved library documents for the authenticated user."""
    user = await verify_token(request)
    uid = user["uid"]

    from firebase_admin import firestore as fs
    docs = (
        db.collection("users")
        .document(uid)
        .collection("library")
        .order_by("saved_at", direction=fs.Query.DESCENDING)
        .stream()
    )

    library = []
    for doc in docs:
        data = doc.to_dict()
        data["doc_id"] = doc.id
        if "saved_at" in data and data["saved_at"] is not None:
            try:
                data["saved_at"] = data["saved_at"].isoformat()
            except AttributeError:
                pass
        library.append(data)

    return {"library": library}


@app.delete("/user/library/{doc_id}")
async def delete_library_item(doc_id: str, request: Request):
    """Remove a document from the user's library."""
    user = await verify_token(request)
    uid = user["uid"]

    db.collection("users").document(uid).collection("library").document(doc_id).delete()
    return {"success": True}


# ── Profile / health ──────────────────────────────────────────────────────────


@app.get("/user/profile")
async def user_profile(request: Request):
    """Return basic profile info for the authenticated user."""
    user = await verify_token(request)
    return {
        "uid": user["uid"],
        "email": user.get("email", ""),
        "created_at": datetime.now().isoformat(),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.on_event("startup")
async def startup():
    print("Investor Doc Finder API is running")
