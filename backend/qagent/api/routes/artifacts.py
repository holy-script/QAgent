import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.domain.models import Artifact, FlowRun, Run
from qagent.storage.objects import object_store

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


async def _serve(key: str) -> Response:
    if object_store.is_configured():
        return RedirectResponse(object_store.get_presigned_url(key), status_code=307)
    data = object_store.get_bytes(key)
    if data is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(content=data, media_type=mimetypes.guess_type(key)[0] or "application/octet-stream")


@router.get("/{run_id}/flows/{flow_key}/{path:path}")
async def get_flow_artifact(run_id: str, flow_key: str, path: str, session: AsyncSession = Depends(get_session)):
    """Serves e.g. steps/3/screenshot.jpg, steps/3/dom.html, network/{call}/response.json, trace.zip."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return await _serve(f"apps/{run.app_id}/runs/{run_id}/flows/{flow_key}/{path}")


@router.get("/{run_id}/steps/{step_seq}/screenshot.jpg")
async def get_screenshot(run_id: str, step_seq: int, session: AsyncSession = Depends(get_session)):
    """Shorthand for the first flow's screenshot; use the flow-qualified route when flows run in parallel."""
    row = (await session.execute(
        select(Artifact).where(Artifact.run_id == run_id, Artifact.step_seq == step_seq, Artifact.kind == "screenshot")
    )).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return await _serve(row.object_key)
