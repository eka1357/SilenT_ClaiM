"""Server-Sent Events endpoint (GET /api/stream) with reconnect resume support."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.container import get_container

router = APIRouter(prefix="/api", tags=["stream"])


def _parse_last_event_id(header_val: str | None, query_val: int | None) -> int | None:
    if query_val is not None:
        return query_val
    if header_val is None:
        return None
    stripped = header_val.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


@router.get("/stream")
async def stream_events(
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    since_id: Annotated[int | None, Query()] = None,
) -> StreamingResponse:
    """Stream real-time Silent Claim SSE events with integer event IDs."""
    container = get_container(request)
    resume_id = _parse_last_event_id(last_event_id, since_id)
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        container.bus.subscribe(last_event_id=resume_id),
        media_type="text/event-stream",
        headers=headers,
    )
