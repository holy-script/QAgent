from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from qagent.browser.launcher import launch_chromium
from qagent.config import settings


class BrowserSandbox:
    """
    Playwright sandbox for one flow: isolated context, trace, HAR, console log,
    and a network allow-list so the agent cannot wander off the target app.
    """

    def __init__(
        self,
        headless: Optional[bool] = None,
        allowed_hosts: Optional[List[str]] = None,
        artifact_dir: Optional[Path] = None,
    ):
        self.headless = settings.browser_headless if headless is None else headless
        self.allowed_hosts = allowed_hosts
        self.artifact_dir = artifact_dir
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.console_logs: List[Dict[str, Any]] = []
        self.blocked_requests: List[str] = []
        self.browser_source: str = ""
        # W3C traceparent injection: set a provider to add the header to every allowed request.
        self.traceparent_provider: Optional[Callable[[], str]] = None
        self.injected: Dict[str, List[str]] = {}

    @property
    def trace_path(self) -> Optional[Path]:
        return self.artifact_dir / "trace.zip" if self.artifact_dir else None

    @property
    def har_path(self) -> Optional[Path]:
        return self.artifact_dir / "har.json" if self.artifact_dir else None

    async def _launch(self) -> Browser:
        assert self.playwright
        browser, self.browser_source = await launch_chromium(self.playwright, self.headless)
        return browser

    def _host_allowed(self, url: str) -> bool:
        if not self.allowed_hosts:
            return True
        parsed = urlparse(url)
        if parsed.scheme in ("data", "about", "blob"):
            return True
        return (parsed.hostname or "") in self.allowed_hosts

    async def _guard(self, route) -> None:
        if self._host_allowed(route.request.url):
            if self.traceparent_provider:
                tp = self.traceparent_provider()
                self.injected.setdefault(route.request.url, []).append(tp)
                await route.continue_(headers={**route.request.headers, "traceparent": tp})
            else:
                await route.continue_()
        else:
            self.blocked_requests.append(route.request.url)
            await route.abort("blockedbyclient")

    async def start(self) -> Page:
        self.playwright = await async_playwright().start()
        self.browser = await self._launch()

        context_args: Dict[str, Any] = {"viewport": {"width": 1280, "height": 800}}
        if self.artifact_dir:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
            context_args["record_har_path"] = str(self.har_path)
        self.context = await self.browser.new_context(**context_args)
        await self.context.route("**/*", self._guard)
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=False)

        self.page = await self.context.new_page()
        self.page.on(
            "console",
            lambda msg: self.console_logs.append(
                {"type": msg.type, "text": msg.text, "location": msg.location}
            ),
        )
        self.page.on(
            "pageerror",
            lambda err: self.console_logs.append({"type": "pageerror", "text": str(err), "location": {}}),
        )
        return self.page

    async def stop(self) -> None:
        """Closes the browser; trace.zip and har.json are flushed to artifact_dir."""
        if self.context:
            if self.trace_path:
                try:
                    await self.context.tracing.stop(path=str(self.trace_path))
                except Exception:
                    pass
            await self.context.close()  # flushes the HAR
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
