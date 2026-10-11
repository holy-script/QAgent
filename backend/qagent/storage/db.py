from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel
from qagent.config import settings

# Format URL for async SQLAlchemy:
# postgresql+psycopg:// -> postgresql+psycopg_async:// or postgresql+psycopg:// (psycopg 3 async engine)
db_url = settings.database_url
connect_args = {}

if "postgres" in db_url:
    # PgBouncer transaction pooling setting
    connect_args["prepare_threshold"] = None

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

direct_engine = None
if settings.database_url_direct:
    direct_engine = create_async_engine(
        settings.database_url_direct,
        echo=False,
        future=True,
    )


async def init_db() -> None:
    """Initialize DB tables if using SQLite or direct table creation."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
