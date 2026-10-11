import asyncio
from typing import List
from playwright.async_api import Page


class WaitFramesWatcher:
    """Watches DOM settling and captures wait frame screenshots for slow or infinite spinners."""

    def __init__(self, page: Page):
        self.page = page

    async def wait_until_settled(self, timeout_ms: int = 3000, poll_interval_ms: int = 500) -> List[bytes]:
        wait_frames: List[bytes] = []
        elapsed = 0
        
        while elapsed < timeout_ms:
            await asyncio.sleep(poll_interval_ms / 1000.0)
            elapsed += poll_interval_ms
            try:
                frame = await self.page.screenshot(type="jpeg", quality=60)
                wait_frames.append(frame)
            except Exception:
                pass

        return wait_frames
