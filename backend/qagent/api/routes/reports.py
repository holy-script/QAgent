from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import iso
from qagent.browser.pdf import html_to_pdf
from qagent.domain import models as m
from qagent.domain.schemas import ReportResponse
from qagent.reports.pipeline import _add_artifact, _default_claude, generate_reports
from qagent.storage import db
from qagent.storage.objects import object_store

router = APIRouter(tags=["Reports"])


def report_out(r: m.Report) -> ReportResponse:
    return ReportResponse(
        id=r.id, app_id=r.app_id, run_id=r.run_id, kind=r.kind, issue_id=r.issue_id, status=r.status,
        content=r.content or {}, markdown_artifact_id=r.markdown_artifact_id, html_artifact_id=r.html_artifact_id,
        pdf_artifact_id=r.pdf_artifact_id, model_version=r.model_version, generated_at=iso(r.generated_at))


@router.get("/runs/{run_id}/report", response_model=ReportResponse)
async def run_report(run_id: str, session: AsyncSession = Depends(get_session)):
    report = (await session.execute(
        select(m.Report).where(m.Report.run_id == run_id, m.Report.kind == "run"))).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail="No report yet for this run")
    return report_out(report)


@router.post("/runs/{run_id}/report", response_model=ReportResponse)
async def regenerate_report(run_id: str, session: AsyncSession = Depends(get_session)):
    """Rebuilds the run report and its bug reports from stored facts (narrative is regenerated too)."""
    run = await session.get(m.Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Run is still in progress")
    result = await generate_reports(db.async_session_factory, run_id, _default_claude(run.mode))
    async with db.async_session_factory() as fresh:
        return report_out(await fresh.get(m.Report, result["run_report_id"]))


@router.get("/reports/{report_id}/export")
async def export_report(report_id: str, format: str = "md", session: AsyncSession = Depends(get_session)):
    """Markdown or HTML as stored; PDF is the HTML printed by Playwright (generated on first request)."""
    report = await session.get(m.Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if format not in ("md", "html", "pdf"):
        raise HTTPException(status_code=422, detail="format must be md, html or pdf")

    artifact_id = {"md": report.markdown_artifact_id, "html": report.html_artifact_id, "pdf": report.pdf_artifact_id}[format]
    if format == "pdf" and not artifact_id:
        html_art = await session.get(m.Artifact, report.html_artifact_id)
        html = object_store.get_bytes(html_art.object_key) if html_art else None
        if not html:
            raise HTTPException(status_code=404, detail="Report HTML is not available")
        pdf = await html_to_pdf(html.decode())
        run = await session.get(m.Run, report.run_id)
        art = _add_artifact(session, run, html_art.object_key.replace(".html", ".pdf"), pdf, "application/pdf",
                            "report_pdf")
        report.pdf_artifact_id = art.id
        await session.commit()
        artifact_id = art.id
    art = await session.get(m.Artifact, artifact_id) if artifact_id else None
    data = object_store.get_bytes(art.object_key) if art else None
    if data is None:
        raise HTTPException(status_code=404, detail="Report file not found")
    media = {"md": "text/markdown", "html": "text/html", "pdf": "application/pdf"}[format]
    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": f'inline; filename="report-{report_id[:8]}.{format}"'})
