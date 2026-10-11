import asyncio
import hashlib
from typing import Any, Awaitable, Callable, Dict, List, Optional
from qagent.storage.objects import object_store
from qagent.storage.db import async_session_factory
from qagent.domain.models import Artifact
from qagent.engine.tracing import logger


UPLOAD_CONCURRENCY = 4
UPLOAD_ATTEMPTS = 4
BACKOFF_S = (0.4, 1.0, 2.5)  # waits between attempts


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
        on_done: Optional[Callable[[Artifact], Awaitable[None]]] = None,
    ):
        self.on_done = on_done
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
        self._workers: list = []
        self.failed: List[str] = []  # keys that could not be stored after every retry
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._workers = [asyncio.create_task(self._worker()) for _ in range(UPLOAD_CONCURRENCY)]

    async def drain(self):
        """Waits until every queued upload has been stored and recorded."""
        await self._queue.join()

    async def stop(self):
        """Flushes every queued upload, then stops the worker (never abandons items mid-queue)."""
        await self._queue.join()
        self._running = False
        for task in self._workers:
            task.cancel()
        self._workers = []

    async def enqueue(
        self,
        key: str,
        data: bytes,
        content_type: str,
        run_id: str,
        flow_run_id: Optional[str] = None,
        step_seq: Optional[int] = None,
        kind: str = "screenshot",
        on_done: Optional[Callable[[Artifact], Awaitable[None]]] = None,
    ):
        item = UploadItem(
            key=key,
            data=data,
            content_type=content_type,
            run_id=run_id,
            flow_run_id=flow_run_id,
            step_seq=step_seq,
            kind=kind,
            on_done=on_done,
        )
        await self._queue.put(item)

    async def _store(self, item: UploadItem) -> None:
        """Uploads with retries and exponential backoff: storage hiccups should not lose evidence."""
        last: Optional[Exception] = None
        for attempt in range(UPLOAD_ATTEMPTS):
            try:
                await asyncio.to_thread(object_store.put_object, item.key, item.data, item.content_type)  # boto3 blocks
                return
            except Exception as exc:
                last = exc
                if attempt < UPLOAD_ATTEMPTS - 1:
                    await asyncio.sleep(BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)])
        raise last  # type: ignore[misc]

    async def _worker(self):
        while self._running:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                break
            try:
                await self._store(item)
                async with async_session_factory() as session:
                    artifact = Artifact(
                        run_id=item.run_id, flow_run_id=item.flow_run_id, step_seq=item.step_seq, kind=item.kind,
                        object_key=item.key, content_type=item.content_type, size_bytes=len(item.data),
                        sha256=hashlib.sha256(item.data).hexdigest(),
                    )
                    session.add(artifact)
                    await session.commit()
                if item.on_done:
                    await item.on_done(artifact)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.failed.append(item.key)
                logger.warning("upload.failed", key=item.key, error=type(exc).__name__)  # never fails the run
            finally:
                self._queue.task_done()


upload_queue = UploadQueue()
