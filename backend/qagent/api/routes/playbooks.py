from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import iso
from qagent.config import settings
from qagent.domain.models import App, Playbook, PlaybookItem, PlaybookVersion
from qagent.domain.schemas import (
    CreatePlaybookRequest, NormalizeRequest, NormalizeResponse, PlaybookItemResponse, PlaybookResponse,
    PlaybookUploadResponse, PlaybookValidationResponse, PlaybookVersionResponse,
)
from qagent.playbooks.normalize import normalize_playbook
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.playbooks.versioning import store_version

router = APIRouter(tags=["Playbooks"])

CATEGORY_KEYS = ["requirements", "flows", "formulas", "ux_rules", "gotchas", "edge_cases", "reasoning_examples"]


async def _current_version(session: AsyncSession, pb: Playbook) -> Optional[PlaybookVersion]:
    return await session.get(PlaybookVersion, pb.current_version_id) if pb.current_version_id else None


def _out(pb: Playbook, version: Optional[PlaybookVersion]) -> PlaybookResponse:
    return PlaybookResponse(
        id=pb.id, app_id=pb.app_id, name=pb.name, current_version_id=pb.current_version_id, status=pb.status,
        flows=(version.parsed.get("flows", []) if version else []),
    )


def _version_out(v: PlaybookVersion) -> PlaybookVersionResponse:
    return PlaybookVersionResponse(
        id=v.id, playbook_id=v.playbook_id, version_no=v.version_no, content_hash=v.content_hash,
        warnings=v.warnings or [], created_at=iso(v.created_at) or "",
    )


@router.get("/playbooks", response_model=List[PlaybookResponse])
async def list_playbooks(app_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    stmt = select(Playbook)
    if app_id:
        stmt = stmt.where(Playbook.app_id == app_id)
    return [_out(p, await _current_version(session, p)) for p in (await session.execute(stmt)).scalars().all()]


@router.get("/apps/{app_id}/playbooks", response_model=List[PlaybookResponse])
async def list_app_playbooks(app_id: str, session: AsyncSession = Depends(get_session)):
    return await list_playbooks(app_id, session)


@router.post("/playbooks/validate", response_model=PlaybookValidationResponse)
async def validate_playbook_markdown(payload: NormalizeRequest):
    """Parses and validates Markdown without saving it (drives the editor's inline errors and coverage panel)."""
    parsed = parse_playbook_markdown(payload.raw_text)
    return PlaybookValidationResponse(
        title=parsed["title"], base_url=parsed["base_url"],
        counts={k: len(parsed[k]) for k in CATEGORY_KEYS}, errors=parsed["errors"], warnings=parsed["warnings"],
        coverage=parsed["coverage"], flows=parsed["flows"],
    )


async def _upload(app_id: str, payload: CreatePlaybookRequest, session: AsyncSession) -> PlaybookUploadResponse:
    if await session.get(App, app_id) is None:
        raise HTTPException(status_code=404, detail="App not found")

    name = payload.name
    pb = None
    if name:
        pb = (await session.execute(select(Playbook).where(Playbook.app_id == app_id, Playbook.name == name))
              ).scalar_one_or_none()
    first = parse_playbook_markdown(payload.raw_markdown)
    name = name or first["title"]
    if pb is None:
        pb = (await session.execute(select(Playbook).where(Playbook.app_id == app_id, Playbook.name == name))
              ).scalar_one_or_none()

    previous = None
    if pb is not None and pb.current_version_id:
        current = await session.get(PlaybookVersion, pb.current_version_id)
        previous = current.parsed if current else None
    parsed = parse_playbook_markdown(payload.raw_markdown, previous)

    if parsed["errors"]:  # errors block confirmation
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"], "warnings": parsed["warnings"]})
    if not parsed["flows"]:
        raise HTTPException(status_code=422, detail={"errors": ["playbook contains no flows"], "warnings": []})

    if pb is None:
        pb = Playbook(app_id=app_id, name=name)
        session.add(pb)
        await session.flush()
    version, created = await store_version(session, pb, payload.raw_markdown, parsed)
    await session.commit()
    return PlaybookUploadResponse(
        playbook=_out(pb, version), version=_version_out(version), created=created, errors=[],
        warnings=parsed["warnings"], coverage=parsed["coverage"],
    )


@router.post("/apps/{app_id}/playbooks", response_model=PlaybookUploadResponse, status_code=201)
async def upload_app_playbook(app_id: str, payload: CreatePlaybookRequest, session: AsyncSession = Depends(get_session)):
    """Parses, validates and stores a Markdown playbook; unchanged content does not create a new version."""
    return await _upload(app_id, payload, session)


@router.post("/playbooks", response_model=PlaybookUploadResponse, status_code=201)
async def upload_playbook(payload: CreatePlaybookRequest, session: AsyncSession = Depends(get_session)):
    return await _upload(payload.app_id, payload, session)


@router.post("/playbooks/normalize", response_model=NormalizeResponse)
async def normalize(payload: NormalizeRequest):
    """Claude rewrites a freeform test description into canonical playbook Markdown (nothing is saved)."""
    if not settings.bedrock_api_key:
        raise HTTPException(status_code=503, detail="BEDROCK_API_KEY is not configured")
    try:
        result = await normalize_playbook(payload.raw_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"normalization failed: {type(exc).__name__}")
    return NormalizeResponse(markdown=result["markdown"], flows=result["parsed"]["flows"],
                             warnings=result["warnings"], notes=result.get("notes"))


@router.get("/playbooks/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(playbook_id: str, session: AsyncSession = Depends(get_session)):
    pb = await session.get(Playbook, playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return _out(pb, await _current_version(session, pb))


@router.get("/playbooks/{playbook_id}/versions", response_model=List[PlaybookVersionResponse])
async def list_versions(playbook_id: str, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(PlaybookVersion).where(PlaybookVersion.playbook_id == playbook_id)
        .order_by(PlaybookVersion.version_no.desc())
    )).scalars().all()
    return [_version_out(v) for v in rows]


@router.get("/playbook-versions/{version_id}/items", response_model=List[PlaybookItemResponse])
async def list_items(version_id: str, category: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    stmt = select(PlaybookItem).where(PlaybookItem.version_id == version_id)
    if category:
        stmt = stmt.where(PlaybookItem.category == category)
    rows = (await session.execute(stmt.order_by(PlaybookItem.item_key))).scalars().all()
    return [PlaybookItemResponse.model_validate(r, from_attributes=True) for r in rows]


@router.get("/playbook-versions/{version_id}/markdown")
async def get_version_markdown(version_id: str, session: AsyncSession = Depends(get_session)):
    v = await session.get(PlaybookVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"id": v.id, "raw_markdown": v.raw_markdown, "parsed": v.parsed, "warnings": v.warnings,
            "errors": v.parsed.get("errors", []), "coverage": v.parsed.get("coverage", {})}
