from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import iso
from qagent.domain.models import App, Playbook, PlaybookVersion
from qagent.config import settings
from qagent.playbooks.normalize import normalize_playbook
from qagent.domain.schemas import NormalizeRequest, NormalizeResponse, CreatePlaybookRequest, PlaybookResponse, PlaybookVersionResponse
from qagent.playbooks.parser import parse_playbook_markdown

router = APIRouter(prefix="/playbooks", tags=["Playbooks"])


async def _current_version(session: AsyncSession, pb: Playbook) -> Optional[PlaybookVersion]:
    return await session.get(PlaybookVersion, pb.current_version_id) if pb.current_version_id else None


def _out(pb: Playbook, version: Optional[PlaybookVersion]) -> PlaybookResponse:
    return PlaybookResponse(
        id=pb.id, app_id=pb.app_id, name=pb.name, current_version_id=pb.current_version_id, status=pb.status,
        flows=(version.parsed.get("flows", []) if version else []),
    )


@router.get("", response_model=List[PlaybookResponse])
async def list_playbooks(app_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    stmt = select(Playbook)
    if app_id:
        stmt = stmt.where(Playbook.app_id == app_id)
    return [_out(p, await _current_version(session, p)) for p in (await session.execute(stmt)).scalars().all()]


@router.post("", response_model=PlaybookResponse, status_code=201)
async def upload_playbook(payload: CreatePlaybookRequest, session: AsyncSession = Depends(get_session)):
    """
    Parses and stores a Markdown playbook. Re-uploading under the same name adds a new
    version unless the content hash is unchanged.
    """
    if await session.get(App, payload.app_id) is None:
        raise HTTPException(status_code=404, detail="App not found")

    parsed = parse_playbook_markdown(payload.raw_markdown)
    if not parsed["flows"]:
        raise HTTPException(status_code=422, detail="playbook contains no '## Flow:' sections")

    name = payload.name or parsed["title"]
    pb = (await session.execute(
        select(Playbook).where(Playbook.app_id == payload.app_id, Playbook.name == name)
    )).scalar_one_or_none()
    if pb is None:
        pb = Playbook(app_id=payload.app_id, name=name)
        session.add(pb)
        await session.flush()

    versions = (await session.execute(
        select(PlaybookVersion).where(PlaybookVersion.playbook_id == pb.id).order_by(PlaybookVersion.version_no)
    )).scalars().all()
    latest = versions[-1] if versions else None
    if latest is None or latest.content_hash != parsed["content_hash"]:
        latest = PlaybookVersion(
            playbook_id=pb.id, version_no=(latest.version_no + 1) if latest else 1,
            raw_markdown=payload.raw_markdown, parsed=parsed, warnings=parsed["warnings"],
            content_hash=parsed["content_hash"],
        )
        session.add(latest)
        await session.flush()
    pb.current_version_id = latest.id
    await session.commit()
    return _out(pb, latest)


@router.post("/normalize", response_model=NormalizeResponse)
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


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(playbook_id: str, session: AsyncSession = Depends(get_session)):
    pb = await session.get(Playbook, playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return _out(pb, await _current_version(session, pb))


@router.get("/{playbook_id}/versions", response_model=List[PlaybookVersionResponse])
async def list_versions(playbook_id: str, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(PlaybookVersion).where(PlaybookVersion.playbook_id == playbook_id)
        .order_by(PlaybookVersion.version_no.desc())
    )).scalars().all()
    return [
        PlaybookVersionResponse(
            id=v.id, playbook_id=v.playbook_id, version_no=v.version_no, content_hash=v.content_hash,
            warnings=v.warnings or [], created_at=iso(v.created_at) or "",
        )
        for v in rows
    ]


@router.get("/versions/{version_id}/markdown")
async def get_version_markdown(version_id: str, session: AsyncSession = Depends(get_session)):
    v = await session.get(PlaybookVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"id": v.id, "raw_markdown": v.raw_markdown, "parsed": v.parsed, "warnings": v.warnings}
