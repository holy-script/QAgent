import asyncio
import mimetypes
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.domain.models import Artifact, FlowRun, Run
from qagent.storage.objects import object_store

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


_TEXTUAL = ("json", "html", "text", "xml", "javascript", "markdown", "x-ndjson")


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
    path = re.sub(r"^(steps/\d+)/screenshot\.jpg$", r"\1/after.jpg", path)  # stable alias used in events/DTOs
    key = f"apps/{run.app_id}/runs/{run_id}/flows/{flow_key}/{path}"
    # Uploads are asynchronous: a client following a live run may ask for a file a moment before it lands.
    # Wait (briefly) for its row instead of redirecting to a storage URL that would answer 404.
    for attempt in range(200):  # up to ~30s while the run is live
        if (await session.execute(select(Artifact.id).where(Artifact.object_key == key))).first():
            break
        if run.status not in ("pending", "running") and attempt >= 2:
            break
        await asyncio.sleep(0.15)
    else:
        raise HTTPException(status_code=404, detail="Artifact not uploaded yet")
    return await _serve(key)


@router.get("/{run_id}/steps/{step_seq}/screenshot.jpg")
async def get_screenshot(run_id: str, step_seq: int, session: AsyncSession = Depends(get_session)):
    """Shorthand for the first flow's screenshot; use the flow-qualified route when flows run in parallel."""
    row = (await session.execute(
        select(Artifact).where(Artifact.run_id == run_id, Artifact.step_seq == step_seq, Artifact.kind == "screenshot_after")
    )).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return await _serve(row.object_key)


@router.get("/{artifact_id}/url")
async def artifact_url(artifact_id: str, session: AsyncSession = Depends(get_session)):
    """A short-lived presigned URL (images, trace.zip, PDF); with local storage, the proxied content URL."""
    art = await session.get(Artifact, artifact_id)
    if art is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if object_store.is_configured():
        return {"url": object_store.get_presigned_url(art.object_key, 900), "expires_in": 900,
                "content_type": art.content_type}
    return {"url": f"/api/artifacts/{art.id}/content", "expires_in": None, "content_type": art.content_type}


@router.get("/{artifact_id}/content")
async def artifact_content(artifact_id: str, session: AsyncSession = Depends(get_session)):
    """Proxied bytes (JSON, HTML, text): browsers cannot fetch() presigned URLs without bucket CORS rules."""
    art = await session.get(Artifact, artifact_id)
    if art is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    data = object_store.get_bytes(art.object_key)
    if data is None:
        raise HTTPException(status_code=404, detail="Artifact file not found")
    return Response(content=data, media_type=art.content_type)
