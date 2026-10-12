from fastapi import APIRouter, HTTPException

from qagent.config import settings
from qagent.domain.schemas import RefineRequest, RefineResponse
from qagent.playbooks.refine import KINDS, refine_text

router = APIRouter(prefix="/text", tags=["Text"])


@router.post("/refine", response_model=RefineResponse)
async def refine(payload: RefineRequest):
    """Claude tidies dictated or rough text for a purpose (tidy, description, prd, notes). Nothing is saved."""
    if payload.kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(KINDS)}")
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="There is no text to tidy up")
    if not settings.bedrock_api_key:
        raise HTTPException(status_code=503, detail="BEDROCK_API_KEY is not configured")
    try:
        result = await refine_text(payload.text, payload.kind)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"tidy-up failed: {type(exc).__name__}")
    return RefineResponse(text=result["text"], notes=result["notes"])
