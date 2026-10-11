import asyncio
import time
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, Request, Response

from qagent.config import settings


class NetworkRecorder:
    """Records traffic per request (not per URL, so repeated POSTs are kept distinct)."""

    def __init__(self, page: Page, flow_run_id: str, sandbox: Optional[Any] = None):
        self.page = page
        self.flow_run_id = flow_run_id
        self.calls: List[Dict[str, Any]] = []
        self._started: Dict[Request, float] = {}
        self._cursor = 0
        self._step_cursor = 0
        self.sandbox = sandbox
        self.inflight = 0

        self.page.on("request", self._on_request)
        self.page.on("requestfinished", self._on_done)
        self.page.on("requestfailed", self._on_done)
        self.page.on("response", self._on_response)

    def _on_request(self, request: Request) -> None:
        self._started[request] = time.perf_counter()
        self.inflight += 1

    def _on_done(self, request: Request) -> None:
        self.inflight = max(0, self.inflight - 1)

    async def _on_response(self, response: Response) -> None:
        request = response.request
        duration_ms = (time.perf_counter() - self._started.pop(request, time.perf_counter())) * 1000.0
        content_type = response.headers.get("content-type", "")
        is_api = "/api/" in response.url or "json" in content_type

        cap = settings.network_body_cap_kb * 1024
        resp_body: Optional[bytes] = None
        if is_api:
            try:
                resp_body = (await response.body())[:cap]
            except Exception:
                resp_body = None
        req_body = (request.post_data_buffer or b"")[:cap] if is_api else None

        self.calls.append({
            "flow_run_id": self.flow_run_id,
            "method": request.method,
            "url": response.url,
            "status": response.status,
            "duration_ms": duration_ms,
            "is_api": is_api,
            "content_type": content_type,
            "req_body": req_body or None,
            "resp_body": resp_body,
            "req_size": len(req_body or b""),
            "resp_size": len(resp_body or b""),
            "traceparent": self._injected_traceparent(response.url),
        })

    def _injected_traceparent(self, url: str) -> Optional[str]:
        queue = getattr(self.sandbox, "injected", {}).get(url) if self.sandbox else None
        return queue.pop(0) if queue else None

    def mark_step_start(self) -> None:
        self._step_cursor = len(self.calls)

    async def wait_for_response(self, path: str, timeout_ms: int = 3000) -> bool:
        """Gotcha hint: if this step has requested `path`, wait until its response has been recorded."""
        deadline = time.perf_counter() + timeout_ms / 1000
        while time.perf_counter() < deadline:
            if any(path in c["url"] for c in self.calls[self._step_cursor:]):
                return True
            if self.inflight == 0:
                return False  # nothing pending: the step never triggered it
            await asyncio.sleep(0.05)
        return False

    def drain(self) -> List[Dict[str, Any]]:
        """Calls recorded since the previous drain (i.e. during the current step)."""
        new = self.calls[self._cursor:]
        self._cursor = len(self.calls)
        return new
