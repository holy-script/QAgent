import pytest
import asyncio
from qagent.storage.upload_queue import upload_queue
from qagent.storage.objects import object_store
from qagent.storage.db import async_session_factory
from qagent.domain.models import Artifact
from sqlmodel import select


@pytest.mark.asyncio
async def test_object_store_put():
    key = "apps/app-1/runs/run-1/steps/1/screenshot.jpg"
    data = b"\xff\xd8\xff\xe0mock_jpeg_bytes"
    res = object_store.put_object(key, data, "image/jpeg")
    assert res is not None

    url = object_store.get_presigned_url(key)
    assert url is not None


@pytest.mark.asyncio
async def test_upload_queue_processes_items():
    upload_queue.start()
    try:
        key = "apps/app-1/runs/run-1/steps/1/test_dom.html"
        data = b"<html><body>test</body></html>"
        
        await upload_queue.enqueue(
            key=key,
            data=data,
            content_type="text/html",
            run_id="run-test-001",
            step_seq=1,
            kind="dom",
        )
        
        # Allow queue worker to process
        await asyncio.sleep(0.1)
        
        async with async_session_factory() as session:
            stmt = select(Artifact).where(Artifact.run_id == "run-test-001")
            result = await session.execute(stmt)
            artifacts = list(result.scalars().all())
            assert len(artifacts) >= 1
            assert artifacts[0].object_key == key
            assert artifacts[0].size_bytes == len(data)
    finally:
        await upload_queue.stop()
