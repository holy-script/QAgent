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
    CheckResultResponse, CreateRunRequest, Finding, FlowRunResponse, LogEntryResponse, NetworkCall,
    NetworkCallDetail, ReplayRequest, RunResponse, SpanResponse, StepSummary, TapeEntry,
)
from qagent.storage import db
from qagent.runs.manager import RunManager, RunStartError, get_run_manager

router = APIRouter(prefix="/runs", tags=["Runs"])


async def _get_run(session: AsyncSession, run_id: str) -> m.Run:
    run = await session.get(m.Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


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


@router.delete("/{run_id}")
async def delete_run(run_id: str, session: AsyncSession = Depends(get_session),
                     manager: RunManager = Depends(get_run_manager)):
    """Deletes one run with its steps, findings, evidence, reports and stored files. Bugs it was the only proof of go too."""
    import asyncio
    from qagent.storage.objects import object_store
    from qagent.storage.purge import purge_run
    run = await _get_run(session, run_id)
    if run_id in manager.active:
        raise HTTPException(status_code=409, detail="This run is still in progress. Stop it first.")
    counts = await purge_run(session, run_id)
    await session.commit()
    removed = await asyncio.to_thread(object_store.delete_prefix, f"apps/{run.app_id}/runs/{run_id}/")
    return {"deleted": counts, "files_removed": removed}


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
    manager: RunManager = Depends(get_run_manager),
):
    """SSE stream of run events. Resumes from `after` or the standard Last-Event-ID header."""
    # Deliberately not `Depends(get_session)`: that would pin a pooled DB connection for the whole stream.
    async with db.async_session_factory() as session:
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
async def run_network(run_id: str, only_api: bool = False, is_api: Optional[bool] = None,
                      min_status: Optional[int] = None, flow_key: Optional[str] = None,
                      session: AsyncSession = Depends(get_session)):
    await _get_run(session, run_id)
    flows = (await session.execute(select(m.FlowRun).where(m.FlowRun.run_id == run_id))).scalars().all()
    keys = {f.id: f.flow_key for f in flows if flow_key is None or f.flow_key == flow_key}
    if not keys:
        return []
    stmt = select(m.NetworkCallRecord).where(m.NetworkCallRecord.flow_run_id.in_(list(keys)))
    if only_api or is_api is True:
        stmt = stmt.where(m.NetworkCallRecord.is_api.is_(True))
    elif is_api is False:
        stmt = stmt.where(m.NetworkCallRecord.is_api.is_(False))
    if min_status is not None:
        stmt = stmt.where(m.NetworkCallRecord.status >= min_status)
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


@router.get("/{run_id}/steps", response_model=List[StepSummary])
async def run_steps(run_id: str, flow_key: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    """Flat list of steps (with timings, decision and findings) across the run's flows."""
    flows = await run_flows(run_id, session)
    return [st for f in flows if flow_key in (None, f.flow_key) for st in f.steps]


@router.get("/{run_id}/checks", response_model=List[CheckResultResponse])
async def run_checks(run_id: str, flow_key: Optional[str] = None, passed: Optional[bool] = None,
                     session: AsyncSession = Depends(get_session)):
    """Every check result with its bound inputs and where each came from."""
    await _get_run(session, run_id)
    flows = {f.id: f.flow_key for f in (await session.execute(
        select(m.FlowRun).where(m.FlowRun.run_id == run_id))).scalars().all()}
    stmt = select(m.CheckResult).where(m.CheckResult.run_id == run_id)
    if passed is not None:
        stmt = stmt.where(m.CheckResult.passed.is_(passed))
    rows = (await session.execute(stmt.order_by(m.CheckResult.created_at))).scalars().all()
    return [CheckResultResponse(
        id=c.id, run_id=c.run_id, flow_run_id=c.flow_run_id, flow_key=flows.get(c.flow_run_id), step_seq=c.step_seq,
        check_key=c.check_key, kind=c.kind, passed=c.passed, expected=c.expected, actual=c.actual,
        inputs=c.inputs or {}, judged_by=c.judged_by, confidence=c.confidence)
        for c in rows if flow_key in (None, flows.get(c.flow_run_id))]


app_router = APIRouter(prefix="/apps", tags=["Runs"])


@app_router.post("/{app_id}/runs", response_model=RunResponse, status_code=202)
async def create_app_run(app_id: str, payload: CreateRunRequest, manager: RunManager = Depends(get_run_manager)):
    """Starts a run for an app: {playbook_id?, flow_keys?, include_edge_cases, mode}."""
    try:
        run = await manager.start_run(payload.model_copy(update={"app_id": app_id}))
    except RunStartError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return run_out(run)


@router.get("/{run_id}/artifacts")
async def run_artifacts(run_id: str, flow_key: Optional[str] = None, step_seq: Optional[int] = None,
                        kind: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    """Artifacts of a run (optionally one step): id, kind, key and a stable URL, e.g. to list a step's wait frames."""
    from urllib.parse import quote
    run = await _get_run(session, run_id)
    flows = {f.id: f.flow_key for f in (await session.execute(
        select(m.FlowRun).where(m.FlowRun.run_id == run_id))).scalars().all()}
    stmt = select(m.Artifact).where(m.Artifact.run_id == run_id)
    if step_seq is not None:
        stmt = stmt.where(m.Artifact.step_seq == step_seq)
    if kind:
        stmt = stmt.where(m.Artifact.kind == kind)
    out = []
    for a in (await session.execute(stmt.order_by(m.Artifact.object_key))).scalars().all():
        fk = flows.get(a.flow_run_id or "")
        if flow_key and fk != flow_key:
            continue
        marker = f"/flows/{fk}/" if fk else ""
        rel = a.object_key.split(marker, 1)[1] if marker and marker in a.object_key else None
        out.append({"id": a.id, "kind": a.kind, "flow_key": fk, "step_seq": a.step_seq, "content_type": a.content_type,
                    "size_bytes": a.size_bytes, "object_key": a.object_key,
                    "url": f"/api/artifacts/{run_id}/flows/{quote(fk, safe='')}/{rel}" if rel else f"/api/artifacts/{a.id}/content"})
    return out


@router.get("/{run_id}/tape", response_model=List[TapeEntry])
async def run_tape(run_id: str, session: AsyncSession = Depends(get_session)):
    """Every model call of the run in the order it happened: plans, step decisions, judgements, report calls."""
    await _get_run(session, run_id)
    flows = {f.id: f.flow_key for f in (await session.execute(
        select(m.FlowRun).where(m.FlowRun.run_id == run_id))).scalars().all()}
    steps = {st.id: st for st in (await session.execute(
        select(m.Step).where(m.Step.flow_run_id.in_(list(flows) or [""])))).scalars().all()}
    out: List[TapeEntry] = []
    for d in (await session.execute(select(m.Decision).where(m.Decision.step_id.in_(list(steps) or [""])))).scalars():
        st = steps[d.step_id]
        out.append(TapeEntry(
            kind="decision", phase=1, flow_key=flows.get(st.flow_run_id), step_seq=st.seq, decider=d.decider,
            model_version=d.model_version, label=d.question, outcome=st.action_label,
            confidence=d.confidence, branch=d.branch, latency_ms=d.latency_ms, input_tokens=d.input_tokens,
            output_tokens=d.output_tokens, cost_usd=(d.response or {}).get("cost_usd", 0.0) or 0.0,
            replayed=d.decider == "replay"))
    phase = {"planner": 0, "judge": 2, "report": 3, "bug_narrative": 3}
    for c in (await session.execute(select(m.ModelCall).where(m.ModelCall.run_id == run_id)
                                    .order_by(m.ModelCall.created_at))).scalars():
        r = c.response or {}
        outcome = {"judge": ("true" if r.get("passed") else "false") if "passed" in r else "",
                   "planner": r.get("summary", "plan written")}.get(c.purpose, "")
        out.append(TapeEntry(
            kind=c.purpose, phase=phase.get(c.purpose, 3), flow_key=flows.get(c.flow_run_id or ""), decider=c.decider,
            model_version=c.model_version, label=c.label, outcome=outcome, confidence=r.get("confidence"),
            latency_ms=c.latency_ms, input_tokens=c.input_tokens, output_tokens=c.output_tokens,
            cost_usd=c.cost_usd, replayed=c.replayed))
    out.sort(key=lambda e: (e.phase, e.flow_key or "", e.step_seq or 0))
    return out
