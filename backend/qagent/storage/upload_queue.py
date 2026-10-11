import asyncio
import hashlib
from typing import Dict, Any, Optional
from qagent.storage.objects import object_store
from qagent.storage.db import async_session_factory
from qagent.domain.models import Artifact


class UploadItem:
    def __init__(
        self,
        key: str,
        data: bytes,
        content_type: str,
        run_id: str,
        flow_run_id: Optional[str] = None,
        step_seq: Optional[int] = None,
        kind: str = "screenshot",
    ):
        self.key = key
        self.data = data
        self.content_type = content_type
        self.run_id = run_id
        self.flow_run_id = flow_run_id
        self.step_seq = step_seq
        self.kind = kind


class UploadQueue:
    def __init__(self):
        self._queue: asyncio.Queue[UploadItem] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        self._running = False
        await self._queue.join()
        if self._worker_task:
            self._worker_task.cancel()

    async def enqueue(
        self,
        key: str,
        data: bytes,
        content_type: str,
        run_id: str,
        flow_run_id: Optional[str] = None,
        step_seq: Optional[int] = None,
        kind: str = "screenshot",
    ):
        item = UploadItem(
            key=key,
            data=data,
            content_type=content_type,
            run_id=run_id,
            flow_run_id=flow_run_id,
            step_seq=step_seq,
            kind=kind,
        )
        await self._queue.put(item)

    async def _worker(self):
        while self._running:
            try:
                item = await self._queue.get()
                try:
                    # Upload object to storage
                    object_store.put_object(item.key, item.data, item.content_type)
                    sha = hashlib.sha256(item.data).hexdigest()

                    # Save record in DB
                    async with async_session_factory() as session:
                        artifact = Artifact(
                            run_id=item.run_id,
                            flow_run_id=item.flow_run_id,
                            step_seq=item.step_seq,
                            kind=item.kind,
                            object_key=item.key,
                            content_type=item.content_type,
                            size_bytes=len(item.data),
                            sha256=sha,
                        )
                        session.add(artifact)
                        await session.commit()
                except Exception as e:
                    # Log error in production
                    pass
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break


upload_queue = UploadQueue()
