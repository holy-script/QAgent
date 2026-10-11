import asyncio
import json
from typing import AsyncGenerator, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain.events import EventEnvelope
from qagent.domain.models import EventRecord, Run
from qagent.runs.manager import RunManager

def is_terminal(event_type: str, payload: dict) -> bool:
    """The stream ends with the run's report (or an error); RUN_FINISHED is followed by report events."""
    return event_type in ("error", "report.failed") or (
        event_type == "report.ready" and payload.get("kind") == "run")


def _sse(seq: int, type_: str, data: dict) -> dict:
    return {"id": str(seq), "event": type_, "data": json.dumps(data)}


def _record_to_dict(r: EventRecord) -> dict:
    return {
        "run_id": r.run_id,
        "seq": r.seq,
        "type": r.type,
        "payload": r.payload,
        "ts": r.ts.isoformat() if hasattr(r.ts, "isoformat") else str(r.ts),
    }


async def stream_run_events(
    manager: RunManager,
    session_factory: Callable[[], AsyncSession],
    run_id: str,
    after_seq: int = 0,
) -> AsyncGenerator[dict, None]:
    """
    Replays persisted events with seq > after_seq, then follows the live run.
    Subscribing before the replay query means no event can fall between the two; the
    `last` cursor drops anything delivered twice.
    """
    queue = manager.subscribe(run_id)
    last = after_seq
    try:
        async with session_factory() as session:
            rows = (await session.execute(
                select(EventRecord).where(EventRecord.run_id == run_id, EventRecord.seq > after_seq)
                .order_by(EventRecord.seq)
            )).scalars().all()
        for row in rows:
            last = row.seq
            yield _sse(row.seq, row.type, _record_to_dict(row))
            if is_terminal(row.type, row.payload or {}):
                return

        if queue is None:
            return  # run is not live in this process: nothing more will arrive

        while True:
            try:
                env: EventEnvelope = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                if manager.active.get(run_id) is None:
                    return
                continue
            if env.seq <= last:
                continue
            last = env.seq
            yield _sse(env.seq, env.type.value, env.model_dump(mode="json"))
            if is_terminal(env.type.value, env.payload):
                return
    finally:
        if queue is not None:
            manager.unsubscribe(run_id, queue)
