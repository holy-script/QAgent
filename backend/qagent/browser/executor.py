import time
from typing import Any, Dict, Optional

from playwright.async_api import Page

from qagent.domain.schemas import CandidateAction


class BrowserExecutor:
    """Executes one candidate action on the page."""

    def __init__(self, page: Page):
        self.page = page

    async def execute(self, action: CandidateAction, value: Optional[str] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        status = "success"
        error_msg = None

        try:
            if action.action_type == "click":
                try:
                    await self.page.click(action.selector, timeout=3000)
                except Exception:
                    await self.page.get_by_text(action.label).first.click(timeout=3000)
            elif action.action_type == "fill":
                await self.page.fill(
                    action.selector, value if value is not None else (action.value or "test"), timeout=3000)
            elif action.action_type == "navigate":
                await self.page.goto(action.value or action.label, timeout=5000)
        except Exception as e:
            status = "failed"
            error_msg = str(e).splitlines()[0]

        return {
            "status": status,
            "duration_ms": (time.perf_counter() - start) * 1000.0,
            "error": error_msg,
        }
