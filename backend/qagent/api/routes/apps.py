from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import app_out
from qagent.domain.models import App
from qagent.domain.schemas import AppResponse, CreateAppRequest

router = APIRouter(prefix="/apps", tags=["Apps"])


@router.get("", response_model=List[AppResponse])
async def list_apps(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(App).order_by(App.created_at))).scalars().all()
    return [app_out(a) for a in rows]


@router.post("", response_model=AppResponse, status_code=201)
async def create_app(payload: CreateAppRequest, session: AsyncSession = Depends(get_session)):
    app = App(
        slug=payload.slug, name=payload.name, base_url=payload.base_url, allowed_hosts=payload.allowed_hosts,
        description=payload.description, prd_markdown=payload.prd_markdown,
        default_mode=payload.default_mode.value,
    )
    session.add(app)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"slug '{payload.slug}' already exists")
    return app_out(app)


@router.get("/{slug}", response_model=AppResponse)
async def get_app(slug: str, session: AsyncSession = Depends(get_session)):
    app = (await session.execute(select(App).where((App.slug == slug) | (App.id == slug)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    return app_out(app)
