"""Findings evidence, network call detail, per-app flows and history."""
import statistics
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import iso
from qagent.checks.edge_cases import expand_flows
from qagent.domain import models as m
from qagent.domain.schemas import FlowResultDot, FlowSummaryResponse, NetworkCallDetail
from qagent.reports.evidence import evidence_graph

router = APIRouter(tags=["Observability"])


@router.get("/findings/{finding_id}/evidence")
async def finding_evidence(finding_id: str, session: AsyncSession = Depends(get_session)):
    """The evidence graph for one finding: screenshots, network calls, decisions, spans, trace, check inputs."""
    graph = await evidence_graph(session, finding_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return graph


@router.get("/network/{call_id}", response_model=NetworkCallDetail)
async def network_call(call_id: str, session: AsyncSession = Depends(get_session)):
    c = await session.get(m.NetworkCallRecord, call_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Network call not found")
    flow = await session.get(m.FlowRun, c.flow_run_id)
    base = None
    if flow:
        run = await session.get(m.Run, flow.run_id)
        base = f"apps/{run.app_id}/runs/{flow.run_id}/flows/{flow.flow_key}/network/{c.id}" if run else None
    return NetworkCallDetail(
        id=c.id, flow_run_id=c.flow_run_id, step_seq=c.step_seq, method=c.method, url=c.url, status=c.status,
        duration_ms=c.duration_ms, req_size=c.req_size, resp_size=c.resp_size, is_api=c.is_api,
        traceparent=c.traceparent, flow_key=flow.flow_key if flow else None,
        req_body_url=f"/api/artifacts/{flow.run_id}/flows/{flow.flow_key}/network/{c.id}/request.json"
        if flow and c.req_size else None,
        resp_body_url=f"/api/artifacts/{flow.run_id}/flows/{flow.flow_key}/network/{c.id}/response.json"
        if flow and c.resp_size else None,
        req_artifact_key=f"{base}/request.json" if base and c.req_size else None,
        resp_artifact_key=f"{base}/response.json" if base and c.resp_size else None,
    )


async def _flow_history(session: AsyncSession, app_id: str, flow_key: str, limit: int) -> List[FlowResultDot]:
    runs = {r.id: r for r in (await session.execute(select(m.Run).where(m.Run.app_id == app_id))).scalars().all()}
    rows = (await session.execute(
        select(m.FlowRun).where(m.FlowRun.run_id.in_(list(runs)), m.FlowRun.flow_key == flow_key))).scalars().all() \
        if runs else []
    rows.sort(key=lambda f: runs[f.run_id].started_at or 0, reverse=True)
    return [FlowResultDot(run_id=f.run_id, flow_run_id=f.id, status=f.status, duration_ms=f.duration_ms,
                          started_at=iso(runs[f.run_id].started_at)) for f in rows[:limit]]


@router.get("/apps/{app_id}/flows", response_model=List[FlowSummaryResponse])
async def app_flows(app_id: str, session: AsyncSession = Depends(get_session)):
    """Current flows and edge-case variants with their last 10 results, median duration and flakiness."""
    app = (await session.execute(select(m.App).where((m.App.id == app_id) | (m.App.slug == app_id)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    playbooks = (await session.execute(select(m.Playbook).where(m.Playbook.app_id == app.id))).scalars().all()
    out: List[FlowSummaryResponse] = []
    for pb in playbooks:
        version = await session.get(m.PlaybookVersion, pb.current_version_id) if pb.current_version_id else None
        if not version:
            continue
        for f in expand_flows(version.parsed):
            dots = await _flow_history(session, app.id, f.key, 10)
            durations = [d.duration_ms for d in dots if d.duration_ms]
            flips = sum(1 for a, b in zip(dots, dots[1:]) if a.status != b.status)
            out.append(FlowSummaryResponse(
                flow_key=f.key, variant_of=f.variant_of, severity=f.severity, covers=f.covers, checks=f.checks,
                last_results=dots, median_duration_ms=statistics.median(durations) if durations else None,
                flakiness=flips / (len(dots) - 1) if len(dots) > 1 else 0.0))
    return out


@router.get("/apps/{app_id}/flows/{flow_key:path}/history")
async def flow_history(app_id: str, flow_key: str, limit: int = 50, session: AsyncSession = Depends(get_session)):
    app = (await session.execute(select(m.App).where((m.App.id == app_id) | (m.App.slug == app_id)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    base = flow_key.split("#", 1)[0]
    issues = (await session.execute(
        select(m.Issue).where(m.Issue.app_id == app.id, m.Issue.flow_key == base,
                              m.Issue.status.in_(["open", "regressed"])))).scalars().all()
    return {"flow_key": flow_key, "results": [d.model_dump() for d in await _flow_history(session, app.id, flow_key, limit)],
            "recurring_issues": [{"id": i.id, "title": i.title, "severity": i.severity, "occurrences": i.occurrences}
                                 for i in issues if i.occurrences > 1]}
