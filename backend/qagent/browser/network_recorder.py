from typing import List, Dict, Any
from playwright.async_api import Page, Request, Response
from qagent.domain.schemas import NetworkCall


class NetworkRecorder:
    """Records network traffic, filtering and tracking API calls and timings."""

    def __init__(self, page: Page, flow_run_id: str):
        self.page = page
        self.flow_run_id = flow_run_id
        self.calls: List[Dict[str, Any]] = []
        self._request_start_times: Dict[str, float] = {}

        self.page.on("request", self._handle_request)
        self.page.on("response", self._handle_response)

    def _handle_request(self, request: Request):
        import time
        self._request_start_times[request.url] = time.perf_counter()

    async def _handle_response(self, response: Response):
        import time
        url = response.url
        start_time = self._request_start_times.get(url, time.perf_counter())
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        is_api = "/api/" in url or "json" in response.headers.get("content-type", "")

        self.calls.append({
            "flow_run_id": self.flow_run_id,
            "method": response.request.method,
            "url": url,
            "status": response.status,
            "duration_ms": duration_ms,
            "is_api": is_api,
            "content_type": response.headers.get("content-type", ""),
        })
