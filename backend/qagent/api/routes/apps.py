import asyncio
import re
from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import app_out, run_out
from qagent.config import settings
from qagent.runs.manager import RunManager, get_run_manager
from qagent.storage.objects import object_store
from qagent.storage.purge import purge_app
from qagent.domain import models as m
from qagent.domain.schemas import (
    PrdExtractResponse, AppResponse, AppSummaryResponse, CreateAppRequest, RunResponse, UpdateAppRequest,
)

router = APIRouter(prefix="/apps", tags=["Apps"])


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "app"


async def _find(session: AsyncSession, key: str) -> m.App:
    app = (await session.execute(select(m.App).where((m.App.slug == key) | (m.App.id == key)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    return app


async def _summary(session: AsyncSession, app: m.App) -> AppSummaryResponse:
    runs = (await session.execute(
        select(m.Run).where(m.Run.app_id == app.id).order_by(m.Run.started_at.desc().nullslast()).limit(20)
    )).scalars().all()
    finished = [r for r in runs if r.status in ("passed", "failed")]
    open_issues = (await session.execute(
        select(m.Issue).where(m.Issue.app_id == app.id, m.Issue.status.in_(["open", "regressed"])))).scalars().all()
    return AppSummaryResponse(
        **app_out(app).model_dump(), last_run=run_out(runs[0]) if runs else None,
        recent_statuses=[r.status for r in runs],
        pass_rate=(sum(r.status == "passed" for r in finished) / len(finished)) if finished else None,
        open_issues=len(open_issues),
    )


@router.get("", response_model=List[AppSummaryResponse])
async def list_apps(session: AsyncSession = Depends(get_session)):
    """Apps with last-run summary, pass rate over the last 20 runs, and open issue count."""
    rows = (await session.execute(select(m.App).order_by(m.App.created_at))).scalars().all()
    return [await _summary(session, a) for a in rows]


@router.post("", response_model=AppResponse, status_code=201)
async def create_app(payload: CreateAppRequest, session: AsyncSession = Depends(get_session)):
    parsed = urlparse(payload.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="base_url must be an http(s) URL")
    host = parsed.hostname
    name = payload.name or host
    app = m.App(
        slug=payload.slug or _slug(payload.name or host), name=name, base_url=payload.base_url.rstrip("/"),
        allowed_hosts=payload.allowed_hosts or [host], description=payload.description,
        prd_markdown=payload.prd_markdown, default_mode=payload.default_mode.value, reset_path=payload.reset_path,
    )
    session.add(app)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"slug '{app.slug}' already exists")
    return app_out(app)


@router.get("/{app_id}", response_model=AppSummaryResponse)
async def get_app(app_id: str, session: AsyncSession = Depends(get_session)):
    return await _summary(session, await _find(session, app_id))


@router.patch("/{app_id}", response_model=AppResponse)
async def update_app(app_id: str, payload: UpdateAppRequest, session: AsyncSession = Depends(get_session)):
    app = await _find(session, app_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(app, field, value.value if field == "default_mode" and value is not None else value)
    await session.commit()
    return app_out(app)


@router.delete("/{app_id}")
async def delete_app(app_id: str, session: AsyncSession = Depends(get_session),
                     manager: RunManager = Depends(get_run_manager)):
    """Deletes the app with its test plans, runs, bugs, reports and stored screenshots/files. Cannot be undone."""
    app = await _find(session, app_id)
    if any(a.runner.spec.app_id == app.id for a in manager.active.values()):
        raise HTTPException(status_code=409, detail="A test run is still in progress. Stop it first, then delete the app.")
    counts = await purge_app(session, app.id)
    await session.commit()
    removed_files = await asyncio.to_thread(object_store.delete_prefix, f"apps/{app.id}/")
    return {"deleted": counts, "files_removed": removed_files}


@router.get("/{app_id}/runs", response_model=List[RunResponse])
async def list_app_runs(app_id: str, limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_session)):
    app = await _find(session, app_id)
    rows = (await session.execute(
        select(m.Run).where(m.Run.app_id == app.id).order_by(m.Run.started_at.desc().nullslast())
        .limit(min(limit, 200)).offset(offset))).scalars().all()
    return [run_out(r) for r in rows]


@router.post("/{app_id}/prd/extract", response_model=PrdExtractResponse)
async def extract_prd_requirements(app_id: str, session: AsyncSession = Depends(get_session)):
    """Claude proposes REQ- items from the app's PRD; each must be accepted by the user before it is saved."""
    from qagent.playbooks.prd_extract import extract_requirements, requirements_markdown
    app = await _find(session, app_id)
    if not app.prd_markdown:
        raise HTTPException(status_code=422, detail="App has no PRD to extract from")
    if not settings.bedrock_api_key:
        raise HTTPException(status_code=503, detail="BEDROCK_API_KEY is not configured")
    existing: List[str] = []
    version_ids = [p.current_version_id for p in (await session.execute(
        select(m.Playbook).where(m.Playbook.app_id == app.id))).scalars().all() if p.current_version_id]
    for vid in version_ids:
        v = await session.get(m.PlaybookVersion, vid)
        existing += [r["key"] for r in (v.parsed or {}).get("requirements", [])] if v else []
    try:
        proposals = await extract_requirements(app.prd_markdown, existing)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"extraction failed: {type(exc).__name__}")
    return PrdExtractResponse(proposals=proposals, markdown=requirements_markdown(proposals))
