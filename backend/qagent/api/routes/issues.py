from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import iso
from qagent.domain import models as m
from qagent.domain.schemas import IssueDetailResponse, IssueOccurrence, IssueResponse, ReportResponse
from qagent.api.routes.reports import report_out

router = APIRouter(tags=["Issues"])


def issue_out(i: m.Issue) -> IssueResponse:
    return IssueResponse(
        id=i.id, app_id=i.app_id, fingerprint=i.fingerprint, title=i.title, severity=i.severity, status=i.status,
        kind=i.kind, check_key=i.check_key, flow_key=i.flow_key, requirement_keys=i.requirement_keys or [],
        first_seen_run_id=i.first_seen_run_id, last_seen_run_id=i.last_seen_run_id,
        last_pass_run_id=i.last_pass_run_id, occurrences=i.occurrences, updated_at=iso(i.updated_at))


@router.get("/apps/{app_id}/issues", response_model=List[IssueResponse])
async def list_issues(app_id: str, status: Optional[str] = None, severity: Optional[str] = None,
                      session: AsyncSession = Depends(get_session)):
    app = (await session.execute(select(m.App).where((m.App.id == app_id) | (m.App.slug == app_id)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    stmt = select(m.Issue).where(m.Issue.app_id == app.id)
    if status:
        stmt = stmt.where(m.Issue.status == status)
    if severity:
        stmt = stmt.where(m.Issue.severity == severity)
    return [issue_out(i) for i in (await session.execute(stmt.order_by(m.Issue.updated_at.desc()))).scalars().all()]


@router.get("/issues/{issue_id}", response_model=IssueDetailResponse)
async def get_issue(issue_id: str, session: AsyncSession = Depends(get_session)):
    issue = await session.get(m.Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    findings = (await session.execute(
        select(m.FindingRecord).where(m.FindingRecord.issue_id == issue_id))).scalars().all()
    runs = {r.id: r for r in (await session.execute(
        select(m.Run).where(m.Run.id.in_([f.run_id for f in findings if f.run_id])))).scalars().all()} if findings else {}
    occurrences = sorted(
        (IssueOccurrence(run_id=f.run_id, finding_id=f.id, step_seq=f.step_seq, severity=f.severity,
                         started_at=iso(runs[f.run_id].started_at) if f.run_id in runs else None)
         for f in findings if f.run_id), key=lambda o: o.started_at or "")
    return IssueDetailResponse(**issue_out(issue).model_dump(), occurrence_list=occurrences)


@router.get("/issues/{issue_id}/report", response_model=ReportResponse)
async def issue_report(issue_id: str, session: AsyncSession = Depends(get_session)):
    """The latest bug report for the issue."""
    report = (await session.execute(
        select(m.Report).where(m.Report.issue_id == issue_id, m.Report.kind == "bug")
        .order_by(m.Report.generated_at.desc().nullslast()))).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail="No bug report yet for this issue")
    return report_out(report)
