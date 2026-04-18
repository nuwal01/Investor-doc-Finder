"""
SSE Manager — manages Server-Sent Events streaming between the agent pipeline
and FastAPI responses.

Provides a per-session async queue so pipeline phases can push status updates
that the HTTP response streams to the client in real time.
"""

import asyncio
from collections import defaultdict
from typing import AsyncGenerator

_queues: dict[str, asyncio.Queue] = {}

STREAM_TIMEOUT = 120  # seconds


async def send_status(session_id: str, message: str, event_type: str = "status") -> None:
    """Push a status update into the queue for the given session."""
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()
    await _queues[session_id].put({"message": message, "event_type": event_type})


async def stream_events(session_id: str) -> AsyncGenerator[dict, None]:
    """Yield SSE-formatted dicts from the session queue until done/error."""
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()

    queue = _queues[session_id]

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=STREAM_TIMEOUT)
            except asyncio.TimeoutError:
                yield {"event": "error", "data": "Stream timed out"}
                break

            event_type = item["event_type"]
            message = item["message"]

            yield {"event": event_type, "data": message}

            if event_type in ("done", "error"):
                break
    finally:
        _queues.pop(session_id, None)


if __name__ == "__main__":
    async def main():
        sid = "test-session-1"

        # Producer: push status updates
        async def producer():
            await send_status(sid, "Starting search...")
            await asyncio.sleep(0.1)
            await send_status(sid, "Resolving entity...")
            await asyncio.sleep(0.1)
            await send_status(sid, "Found PDF: https://example.com/report.pdf", "result")
            await asyncio.sleep(0.1)
            await send_status(sid, "Complete", "done")

        # Consumer: stream events
        async def consumer():
            events = []
            async for event in stream_events(sid):
                events.append(event)
                print(f"  [{event['event']:>8s}]  {event['data']}")
            return events

        print("=== SSE Manager Test ===\n")
        _, events = await asyncio.gather(producer(), consumer())
        print(f"\nTotal events: {len(events)}")
        print(f"Queues remaining: {len(_queues)}")

    asyncio.run(main())
