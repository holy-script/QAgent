import time
from typing import Any, Dict, List, Optional

from playwright.async_api import Locator, Page

from qagent.domain.schemas import CandidateAction


class BrowserExecutor:
    """Executes one candidate action on the page. It acts on exactly the element that was chosen, or fails and says why."""

    def __init__(self, page: Page):
        self.page = page

    async def _locate(self, action: CandidateAction) -> Optional[Locator]:
        """The one element this candidate stands for: its stamp, or else its own selector if that matches a single element."""
        for sel in (action.selector, action.alt_selector):
            if not sel:
                continue
            loc = self.page.locator(sel)
            if await loc.count() == 1:
                return loc
        return None

    async def _fill(self, action: CandidateAction, value: str) -> None:
        loc = await self._locate(action)
        if loc is None:
            raise RuntimeError(f"could not find exactly one field for '{action.label}' (it may have changed or there are several alike)")
        await loc.fill(value, timeout=3000)
        if await loc.input_value() != value:
            # Some inputs (masks, controlled components) reject a bulk fill: type it the way a person would.
            await loc.fill("", timeout=3000)
            await loc.press_sequentially(value, delay=20, timeout=8000)
            if await loc.input_value() != value:
                raise RuntimeError(f"the field '{action.label}' did not keep the text that was typed")

    async def _click(self, action: CandidateAction) -> None:
        """Clicks the chosen element, escalating when a rough page gets in the way: a normal click, a forced click (covered by an
        overlay or animating), a click dispatched from script, then the visible text."""
        loc = await self._locate(action)
        attempts = []
        if loc is not None:
            attempts += [lambda: loc.click(timeout=3000), lambda: loc.click(timeout=2000, force=True),
                         lambda: loc.evaluate("el => el.click()", timeout=2000)]
        if action.label and not action.label.startswith("Clickable "):
            attempts.append(lambda: self.page.get_by_text(action.label).first.click(timeout=3000))
        last: Optional[Exception] = None
        for attempt in attempts:
            try:
                await attempt()
                return
            except Exception as exc:
                last = exc
        raise last or RuntimeError("no single match")

    async def execute(self, action: CandidateAction, value: Optional[str] = None,
                      files: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        status = "success"
        error_msg = None

        try:
            if action.action_type == "click":
                await self._click(action)
            elif action.action_type == "fill":
                await self._fill(action, value if value is not None else (action.value or "test"))
            elif action.action_type == "upload":
                loc = await self._locate(action)
                if loc is None:
                    raise RuntimeError(f"could not find exactly one file field for '{action.label}'")
                # set_input_files works on hidden inputs too, which is how styled "drop zone" buttons are built.
                await loc.set_input_files(files or [], timeout=3000)
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
