import asyncio
import time
from dataclasses import dataclass, field
from typing import List

from playwright.async_api import Page

# A page counts as busy while a visible loading indicator exists.
BUSY_JS = """
() => {
    const sel = '.spinner, .loading, [aria-busy="true"], [role="progressbar"], [data-testid*="spinner"], [data-testid*="loading"]';
    return Array.from(document.querySelectorAll(sel)).some(el => {
        const r = el.getBoundingClientRect();
        const s = window.getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
    });
}
"""


@dataclass
class SettleResult:
    settled: bool
    waited_ms: float
    frames: List[bytes] = field(default_factory=list)


class WaitFramesWatcher:
    """Waits for the page to settle; captures a frame each poll while it is still busy."""

    def __init__(self, page: Page, recorder=None):
        self.page = page
        self.recorder = recorder

    async def _busy(self) -> bool:
        try:
            if await self.page.evaluate(BUSY_JS):
                return True
        except Exception:
            return False  # mid-navigation; treat as not busy and re-check next poll
        return bool(self.recorder and self.recorder.inflight > 0)

    async def wait_until_settled(self, timeout_ms: int = 3000, poll_interval_ms: int = 500) -> SettleResult:
        start = time.perf_counter()
        frames: List[bytes] = []
        quiet_polls = 0
        while (time.perf_counter() - start) * 1000 < timeout_ms:
            if await self._busy():
                quiet_polls = 0
                try:
                    frames.append(await self.page.screenshot(type="jpeg", quality=60))
                except Exception:
                    pass
                await asyncio.sleep(poll_interval_ms / 1000.0)
            else:
                quiet_polls += 1
                if quiet_polls >= 2:  # two consecutive quiet checks: stable
                    return SettleResult(True, (time.perf_counter() - start) * 1000, frames)
                await asyncio.sleep(0.05)
        return SettleResult(False, (time.perf_counter() - start) * 1000, frames)


# Resolves once the page's DOM has not changed for `quiet` ms (or after `max` ms). Spinner checks miss pages that are simply
# still rendering (hydration, client-side routing, lazy images), and a screenshot or element list taken mid-render shows a
# page that is already gone.
DOM_QUIET_JS = """
([quiet, max]) => new Promise(resolve => {
    let timer;
    const done = () => { obs.disconnect(); resolve(true); };
    const obs = new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(done, quiet); });
    obs.observe(document.documentElement, {subtree: true, childList: true, attributes: true, characterData: true});
    timer = setTimeout(done, quiet);
    setTimeout(() => { clearTimeout(timer); obs.disconnect(); resolve(false); }, max);
})
"""

PAGE_SIGNATURE_JS = "() => (document.body ? document.body.innerText.length : 0) + '|' + document.querySelectorAll('*').length + '|' + location.href"


async def wait_dom_stable(page: Page, quiet_ms: int = 350, max_ms: int = 3000) -> bool:
    """True if the DOM went quiet; False if it kept changing until `max_ms` (or the page was navigating)."""
    try:
        return bool(await page.evaluate(DOM_QUIET_JS, [quiet_ms, max_ms]))
    except Exception:
        return False


async def page_signature(page: Page) -> str:
    try:
        return str(await page.evaluate(PAGE_SIGNATURE_JS))
    except Exception:
        return ""
