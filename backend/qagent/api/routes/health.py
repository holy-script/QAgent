from fastapi import APIRouter
from sqlalchemy import text

from qagent.config import settings
from qagent.domain.schemas import HealthResponse
from qagent.storage import db
from qagent.storage.objects import object_store

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    """Postgres is pinged for real; Jev, Bedrock and object storage report whether they are configured."""
    try:
        async with db.async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        postgres_ok = False

    return HealthResponse(
        status="ok" if postgres_ok else "degraded",
        jev_reachable=bool(settings.active_jev_token),
        bedrock_reachable=bool(settings.bedrock_api_key),
        postgres_reachable=postgres_ok,
        storage_reachable=object_store.is_configured(),
        active_model=settings.jev_model,
    )
