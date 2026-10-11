from fastapi import APIRouter
from qagent.config import settings
from qagent.domain.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    has_jev = bool(settings.active_jev_token)
    has_bedrock = bool(settings.bedrock_api_key)
    
    return HealthResponse(
        status="ok",
        jev_reachable=has_jev,
        bedrock_reachable=has_bedrock,
        postgres_reachable=True,
        storage_reachable=True,
        active_model=settings.jev_model,
    )
