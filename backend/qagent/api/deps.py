from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from qagent.storage import db


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    # Looked up at call time so tests can swap db.async_session_factory.
    async with db.async_session_factory() as session:
        yield session


async def resolve_app_id(session: AsyncSession, key: str) -> str:
    """Accepts an app id or slug and returns the id (404 if unknown)."""
    from fastapi import HTTPException
    from sqlmodel import select
    from qagent.domain.models import App
    app = (await session.execute(select(App).where((App.id == key) | (App.slug == key)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    return app.id
