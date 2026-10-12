import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.browser import uploads
from qagent.api.mappers import app_out, iso, run_out
from qagent.config import settings
from qagent.runs.manager import RunManager, get_run_manager
from qagent.storage.objects import object_store
from qagent.storage import vault
from qagent.storage.purge import purge_app
from qagent.storage.retention import apply_retention, expired_runs
from qagent.domain import models as m
from qagent.domain.schemas import (
    AppFileResponse, CredentialResponse, NormalizeResponse, PrdExtractResponse, PrdPlanRequest, AppResponse, AppSummaryResponse, CreateAppRequest, RetentionResult, RetentionStatus, RunResponse,
    SetCredentialRequest, UpdateAppRequest,
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


def _file_out(f: m.AppFile) -> AppFileResponse:
    return AppFileResponse(id=f.id, name=f.name, content_type=f.content_type, size_bytes=f.size_bytes,
                           created_at=iso(f.created_at) or "")


@router.post("/{app_id}/prd/plan", response_model=NormalizeResponse)
async def plan_from_product_document(app_id: str, payload: Optional[PrdPlanRequest] = None,
                                     session: AsyncSession = Depends(get_session)):
    """Claude turns the app's product document (or `prd` from the request) into a high-level test plan of goal-driven
    journeys. Nothing is saved; the author reviews and saves it like any other plan."""
    from qagent.playbooks.from_prd import plan_from_prd
    app = await _find(session, app_id)
    prd = ((payload.prd if payload else None) or app.prd_markdown or "").strip()
    if not prd:
        raise HTTPException(status_code=422, detail="Add a product document in Settings first")
    if not settings.bedrock_api_key:
        raise HTTPException(status_code=503, detail="BEDROCK_API_KEY is not configured")
    try:
        result = await plan_from_prd(prd, app.base_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"could not write the test plan: {type(exc).__name__}")
    return NormalizeResponse(markdown=result["markdown"], flows=result["parsed"]["flows"],
                             warnings=result["warnings"], notes=result.get("notes"))


PLAIN_NAMES = {"username", "user", "email", "login", "account"}


def _credential_out(c: m.AppCredential) -> CredentialResponse:
    value = None if c.secret else vault.decrypt(c.ciphertext)
    return CredentialResponse(name=c.name, secret=c.secret, value=value, updated_at=iso(c.updated_at) or "")


@router.get("/{app_id}/credentials", response_model=List[CredentialResponse])
async def list_credentials(app_id: str, session: AsyncSession = Depends(get_session)):
    """Saved sign-in details by name. Secret values are never returned."""
    app = await _find(session, app_id)
    rows = (await session.execute(select(m.AppCredential).where(m.AppCredential.app_id == app.id).order_by(m.AppCredential.name))).scalars().all()
    return [_credential_out(c) for c in rows]


@router.put("/{app_id}/credentials/{name}", response_model=CredentialResponse)
async def set_credential(app_id: str, name: str, payload: SetCredentialRequest, session: AsyncSession = Depends(get_session)):
    """Saves (or replaces) one sign-in detail, encrypted. Tests type it in by field name ("Enter the password")."""
    app = await _find(session, app_id)
    clean = name.strip()
    if not re.fullmatch(r"[A-Za-z][\w .\-]{0,39}", clean):
        raise HTTPException(status_code=422, detail="Use a short name such as username, email or password")
    rows = (await session.execute(select(m.AppCredential).where(m.AppCredential.app_id == app.id))).scalars().all()
    existing = next((c for c in rows if c.name.lower() == clean.lower()), None)
    if existing is None and len(rows) >= 20:
        raise HTTPException(status_code=409, detail="An app can keep 20 saved sign-in details; remove some first")
    secret = payload.secret if payload.secret is not None else clean.lower() not in PLAIN_NAMES
    record = existing or m.AppCredential(app_id=app.id, name=clean, ciphertext="")
    record.ciphertext, record.secret = vault.encrypt(payload.value), secret
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    await session.commit()
    return _credential_out(record)


@router.delete("/{app_id}/credentials/{name}")
async def delete_credential(app_id: str, name: str, session: AsyncSession = Depends(get_session)):
    app = await _find(session, app_id)
    rows = (await session.execute(select(m.AppCredential).where(m.AppCredential.app_id == app.id))).scalars().all()
    record = next((c for c in rows if c.name.lower() == name.strip().lower()), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
    return {"deleted": record.name}


@router.get("/{app_id}/files", response_model=List[AppFileResponse])
async def list_app_files(app_id: str, session: AsyncSession = Depends(get_session)):
    """Test files the app's upload steps can use, plus the built-in samples every app has."""
    app = await _find(session, app_id)
    own = (await session.execute(select(m.AppFile).where(m.AppFile.app_id == app.id).order_by(m.AppFile.name))).scalars().all()
    shadowed = {f.name.lower() for f in own}
    builtin = [AppFileResponse(id=f"builtin:{n}", name=n, content_type=c, size_bytes=len(b), created_at="", builtin=True)
               for n, (b, c) in uploads.BUILTIN.items() if n.lower() not in shadowed]
    return [_file_out(f) for f in own] + builtin


@router.post("/{app_id}/files", response_model=AppFileResponse, status_code=201)
async def add_app_file(app_id: str, request: Request, name: str, session: AsyncSession = Depends(get_session)):
    """Stores a test file. Send the raw file as the request body and its name as `?name=`. Same name replaces."""
    app = await _find(session, app_id)
    clean = re.sub(r"[^\w.\- ]", "_", name.strip().split("/")[-1].split("\\")[-1])[:120]
    if not clean or clean.startswith("."):
        raise HTTPException(status_code=422, detail="Give the file a name, for example report.pdf")
    data = await request.body()
    # An empty file is allowed on purpose: "upload an empty file" is a classic edge case.
    if len(data) > uploads.MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"Files can be at most {uploads.MAX_FILE_BYTES // (1024 * 1024)} MB")
    existing = (await session.execute(select(m.AppFile).where(m.AppFile.app_id == app.id))).scalars().all()
    same = next((f for f in existing if f.name.lower() == clean.lower()), None)
    if same is None and len(existing) >= uploads.MAX_FILES_PER_APP:
        raise HTTPException(status_code=409, detail=f"An app can keep {uploads.MAX_FILES_PER_APP} test files; delete some first")
    ctype = request.headers.get("x-file-type") or uploads.guess_type(clean)
    record = same or m.AppFile(app_id=app.id, name=clean, object_key="")
    record.content_type, record.size_bytes = ctype, len(data)
    record.sha256 = hashlib.sha256(data).hexdigest()
    record.object_key = f"apps/{app.id}/files/{record.id}/{clean}"
    await asyncio.to_thread(object_store.put_object, record.object_key, data, ctype)
    session.add(record)
    await session.commit()
    return _file_out(record)


@router.delete("/{app_id}/files/{file_id}")
async def delete_app_file(app_id: str, file_id: str, session: AsyncSession = Depends(get_session)):
    app = await _find(session, app_id)
    record = await session.get(m.AppFile, file_id)
    if record is None or record.app_id != app.id:
        raise HTTPException(status_code=404, detail="File not found")
    await session.delete(record)
    await session.commit()
    await asyncio.to_thread(object_store.delete_prefix, f"apps/{app.id}/files/{record.id}/")
    return {"deleted": record.name}


@router.get("/{app_id}/retention", response_model=RetentionStatus)
async def retention_status(app_id: str, session: AsyncSession = Depends(get_session),
                           manager: RunManager = Depends(get_run_manager)):
    """The app's clean-up policy and how many runs it would remove right now."""
    app = await _find(session, app_id)
    runs = (await session.execute(select(m.Run).where(m.Run.app_id == app.id))).scalars().all()
    starts = [r.started_at for r in runs if r.started_at]
    return RetentionStatus(
        retention_days=app.retention_days, retention_keep_last=app.retention_keep_last, total_runs=len(runs),
        would_delete=len(await expired_runs(session, app, manager.active)),
        oldest_started_at=iso(min(starts)) if starts else None)


@router.post("/{app_id}/retention/clean", response_model=RetentionResult)
async def retention_clean(app_id: str, session: AsyncSession = Depends(get_session),
                          manager: RunManager = Depends(get_run_manager)):
    """Applies the app's policy now. Does nothing when the app keeps runs for ever."""
    return RetentionResult(**await apply_retention(session, await _find(session, app_id), manager.active))


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
