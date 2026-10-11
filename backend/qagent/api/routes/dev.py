import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Query, HTTPException
from sse_starlette.sse import EventSourceResponse
from qagent.fixtures.loader import get_mock_run_events

router = APIRouter(prefix="/dev", tags=["Dev & Fixtures"])


@router.get("/events")
async def list_fixture_events():
    """Returns static array of all fixture events for testing."""
    return get_mock_run_events()


@router.get("/sse-replay")
async def sse_replay(
    delay_ms: int = Query(default=300, description="Delay between events in milliseconds", ge=50, le=2000),
    loop: bool = Query(default=False, description="Whether to loop the events indefinitely"),
):
    """
    Streams recorded QA run events over SSE.
    Frontend Coder 2 connects to this to design real-time charts, telemetry, and step cards.
    """
    events = get_mock_run_events()
    if not events:
        raise HTTPException(status_code=404, detail="No fixture events found")

    async def event_generator() -> AsyncGenerator[dict, None]:
        while True:
            for item in events:
                yield {
                    "event": item.get("type", "message"),
                    "data": json.dumps(item),
                    "id": str(item.get("seq", 0)),
                }
                await asyncio.sleep(delay_ms / 1000.0)

            if not loop:
                break

    return EventSourceResponse(event_generator())
