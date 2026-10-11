from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from qagent.storage import db


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    # Looked up at call time so tests can swap db.async_session_factory.
    async with db.async_session_factory() as session:
        yield session
