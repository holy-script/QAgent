from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from qagent.config import settings


class BrowserSandbox:
    """
    Playwright Browser Sandbox managing browser lifecycle,
    viewports, traces, HAR recording, and console logs.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.console_logs: List[Dict[str, Any]] = []

    async def start(self, record_har_path: Optional[str] = None):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        
        context_args: Dict[str, Any] = {
            "viewport": {"width": 1280, "height": 800},
            "record_video_dir": None,
        }
        if record_har_path:
            context_args["record_har_path"] = record_har_path

        self.context = await self.browser.new_context(**context_args)
        
        # Start tracing
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

        self.page = await self.context.new_page()

        # Intercept console logs
        self.page.on("console", lambda msg: self.console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "location": msg.location,
        }))

    async def stop(self, trace_path: Optional[str] = None):
        if self.context:
            if trace_path:
                try:
                    await self.context.tracing.stop(path=trace_path)
                except Exception:
                    pass
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
