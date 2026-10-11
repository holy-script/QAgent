from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from qagent.api.deps import get_session
from qagent.api.mappers import finding_out, iso, network_out, run_out, step_out
from qagent.api.sse import stream_run_events
from qagent.domain import models as m
from qagent.domain.schemas import (
    CreateRunRequest, Finding, ReplayRequest, FlowRunResponse, LogEntryResponse, NetworkCall, RunResponse, SpanResponse,
)
from qagent.runs.manager import RunManager, RunStartError, get_run_manager

router = APIRouter(prefix="/runs", tags=["Runs"])


async def _get_run(session: AsyncSession, run_id: str) -> m.Run:
    run = await session.get(m.Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("", response_model=List[RunResponse])
async def list_runs(app_id: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
                    session: AsyncSession = Depends(get_session)):
    stmt = select(m.Run).order_by(m.Run.started_at.desc().nullslast()).limit(limit)
    if app_id:
        stmt = stmt.where(m.Run.app_id == app_id)
    return [run_out(r) for r in (await session.execute(stmt)).scalars().all()]


@router.post("", response_model=RunResponse, status_code=202)
async def create_run(payload: CreateRunRequest, manager: RunManager = Depends(get_run_manager)):
    try:
        run = await manager.start_run(payload)
    except RunStartError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return run_out(run)


@router.post("/{run_id}/replay", response_model=RunResponse, status_code=202)
async def replay_run(run_id: str, payload: ReplayRequest, manager: RunManager = Depends(get_run_manager)):
    """Re-runs a finished run deterministically from its decision tape; `overrides` tweak gating and budgets."""
    try:
        run = await manager.replay_run(run_id, payload.overrides)
    except RunStartError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return run_out(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    return run_out(await _get_run(session, run_id))


@router.post("/{run_id}/stop", response_model=RunResponse)
async def stop_run(run_id: str, session: AsyncSession = Depends(get_session),
                   manager: RunManager = Depends(get_run_manager)):
    run = await _get_run(session, run_id)
    if not await manager.stop(run_id) and run.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Run is not active in this server process")
    return run_out(run)


@router.get("/{run_id}/events")
async def run_events(
    run_id: str,
    after: int = Query(0, ge=0, description="Resume after this event seq"),
    last_event_id: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
    manager: RunManager = Depends(get_run_manager),
):
    """SSE stream of run events. Resumes from `after` or the standard Last-Event-ID header."""
    await _get_run(session, run_id)
    cursor = after
    if last_event_id and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))
    return EventSourceResponse(
        stream_run_events(manager, manager.session_factory, run_id, cursor)
    )


@router.get("/{run_id}/flows", response_model=List[FlowRunResponse])
async def run_flows(run_id: str, session: AsyncSession = Depends(get_session)):
    await _get_run(session, run_id)
    flows = (await session.execute(select(m.FlowRun).where(m.FlowRun.run_id == run_id))).scalars().all()
    ids = [f.id for f in flows]
    steps = (await session.execute(
        select(m.Step).where(m.Step.flow_run_id.in_(ids)).order_by(m.Step.seq)
    )).scalars().all() if ids else []
    step_ids = [st.id for st in steps]
    timings = {t.step_id: t for t in (await session.execute(
        select(m.StepTiming).where(m.StepTiming.step_id.in_(step_ids)))).scalars().all()} if step_ids else {}
    decisions = {d.step_id: d for d in (await session.execute(
        select(m.Decision).where(m.Decision.step_id.in_(step_ids)))).scalars().all()} if step_ids else {}
    findings = (await session.execute(
        select(m.FindingRecord).where(m.FindingRecord.flow_run_id.in_(ids)))).scalars().all() if ids else []

    out = []
    for f in flows:
        f_findings = [x for x in findings if x.flow_run_id == f.id]
        out.append(FlowRunResponse(
            id=f.id, run_id=f.run_id, flow_key=f.flow_key, status=f.status, step_count=f.step_count,
            duration_ms=f.duration_ms, failure_reason=f.failure_reason,
            steps=[
                step_out(st, run_id, f.flow_key, timings.get(st.id), decisions.get(st.id), f_findings)
                for st in steps if st.flow_run_id == f.id
            ],
        ))
    return out


@router.get("/{run_id}/findings", response_model=List[Finding])
async def run_findings(run_id: str, session: AsyncSession = Depends(get_session)):
    await _get_run(session, run_id)
    flow_ids = (await session.execute(select(m.FlowRun.id).where(m.FlowRun.run_id == run_id))).scalars().all()
    rows = (await session.execute(
        select(m.FindingRecord).where(m.FindingRecord.flow_run_id.in_(flow_ids)).order_by(m.FindingRecord.step_seq)
    )).scalars().all() if flow_ids else []
    return [finding_out(f) for f in rows]


@router.get("/{run_id}/network", response_model=List[NetworkCall])
async def run_network(run_id: str, only_api: bool = False, flow_key: Optional[str] = None,
                      session: AsyncSession = Depends(get_session)):
    await _get_run(session, run_id)
    flows = (await session.execute(select(m.FlowRun).where(m.FlowRun.run_id == run_id))).scalars().all()
    keys = {f.id: f.flow_key for f in flows if flow_key is None or f.flow_key == flow_key}
    if not keys:
        return []
    stmt = select(m.NetworkCallRecord).where(m.NetworkCallRecord.flow_run_id.in_(list(keys)))
    if only_api:
        stmt = stmt.where(m.NetworkCallRecord.is_api.is_(True))
    rows = (await session.execute(stmt.order_by(m.NetworkCallRecord.step_seq))).scalars().all()
    return [network_out(c, run_id, keys[c.flow_run_id]) for c in rows]


@router.get("/{run_id}/spans", response_model=List[SpanResponse])
async def run_spans(run_id: str, session: AsyncSession = Depends(get_session)):
    await _get_run(session, run_id)
    rows = (await session.execute(
        select(m.SpanRecord).where(m.SpanRecord.run_id == run_id).order_by(m.SpanRecord.start_ns)
    )).scalars().all()
    return [SpanResponse.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{run_id}/logs", response_model=List[LogEntryResponse])
async def run_logs(run_id: str, level: Optional[str] = None, source: Optional[str] = None,
                   session: AsyncSession = Depends(get_session)):
    await _get_run(session, run_id)
    stmt = select(m.LogEntryRecord).where(m.LogEntryRecord.run_id == run_id)
    if level:
        stmt = stmt.where(m.LogEntryRecord.level == level)
    if source:
        stmt = stmt.where(m.LogEntryRecord.source == source)
    rows = (await session.execute(stmt.order_by(m.LogEntryRecord.ts))).scalars().all()
    return [
        LogEntryResponse(
            id=r.id, run_id=r.run_id, flow_run_id=r.flow_run_id, step_seq=r.step_seq, level=r.level,
            source=r.source, message=r.message, data=r.data or {}, ts=iso(r.ts) or "",
        )
        for r in rows
    ]
