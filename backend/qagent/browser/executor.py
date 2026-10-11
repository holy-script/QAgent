import time
from typing import Dict, Any, Optional
from playwright.async_api import Page
from qagent.domain.schemas import CandidateAction


class BrowserExecutor:
    """Executes actions on page given candidate action and captures screenshot."""

    def __init__(self, page: Page):
        self.page = page

    async def execute(self, action: CandidateAction) -> Dict[str, Any]:
        start = time.perf_counter()
        status = "success"
        error_msg = None

        try:
            if action.action_type == "click":
                # First try exact selector
                try:
                    await self.page.click(action.selector, timeout=3000)
                except Exception:
                    # Fallback to text click
                    await self.page.get_by_text(action.label).first.click(timeout=3000)
            elif action.action_type == "fill":
                val = action.value or "test"
                await self.page.fill(action.selector, val, timeout=3000)
            elif action.action_type == "navigate":
                target = action.value or action.label
                await self.page.goto(target, timeout=5000)
        except Exception as e:
            status = "failed"
            error_msg = str(e)

        duration_ms = (time.perf_counter() - start) * 1000.0

        # Capture step screenshot
        screenshot_bytes = b""
        try:
            screenshot_bytes = await self.page.screenshot(type="jpeg", quality=75)
        except Exception:
            pass

        return {
            "status": status,
            "duration_ms": duration_ms,
            "error": error_msg,
            "screenshot_bytes": screenshot_bytes,
        }
