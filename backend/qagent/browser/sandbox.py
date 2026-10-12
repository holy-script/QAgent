import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from qagent.browser.launcher import launch_chromium
from qagent.config import settings


ANIMATIONS_OFF = """(() => {
  const css = '*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important;caret-color:transparent!important}';
  const add = () => { const s = document.createElement('style'); s.textContent = css; (document.head || document.documentElement).appendChild(s); };
  if (document.documentElement) add(); else document.addEventListener('DOMContentLoaded', add);
})();"""


# Sign-in providers a signed-in session may bounce through; allowed in session mode so SSO redirects are not blocked.
SSO_HOST_SUFFIXES = ("microsoftonline.com", "microsoft.com", "live.com", "msauth.net", "msftauth.net", "msauth.com")


FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


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
        self.session_mode = settings.session_mode
        self.browser_version: str = ""

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
        host = parsed.hostname or ""
        if host in FONT_HOSTS:
            return True   # web fonts only change how the page looks
        if self.session_mode and any(host == s or host.endswith("." + s) for s in SSO_HOST_SUFFIXES):
            return True
        return any(host == a or (a.startswith("*.") and host.endswith(a[1:])) for a in self.allowed_hosts)

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

    async def _open_existing_session(self) -> BrowserContext:
        """Attaches to a running Chrome (CDP) or launches Chrome on a persistent profile; the signed-in session is already there."""
        assert self.playwright
        if settings.cdp_url:
            self.browser = await self.playwright.chromium.connect_over_cdp(settings.cdp_url)
            self.browser_source = f"existing Chrome at {settings.cdp_url}"
            self.browser_version = self.browser.version
            return self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        context = await self.playwright.chromium.launch_persistent_context(
            os.path.expanduser(settings.user_data_dir),
            channel=settings.browser_channel or "chrome",
            executable_path=settings.browser_path or None,
            headless=self.headless,
            args=["--no-sandbox"],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 800},
        )
        self.browser = context.browser
        self.browser_version = self.browser.version if self.browser else ""
        self.browser_source = f"Chrome profile {settings.user_data_dir}"
        return context

    async def start(self, storage_state: Optional[Dict[str, Any]] = None) -> Page:
        """`storage_state`: cookies and local storage of an earlier signed-in session to start from (ignored in session mode,
        where the browser profile already holds the signed-in session)."""
        self.playwright = await async_playwright().start()
        if self.session_mode:
            # The profile is the user's own: no fixed clock, init scripts or HAR (they would touch their other tabs),
            # and the allow-list is applied to our page only.
            self.context = await self._open_existing_session()
            await self.context.tracing.start(screenshots=True, snapshots=True, sources=False)
            self.page = await self.context.new_page()
            await self.page.route("**/*", self._guard)
        else:
            self.browser = await self._launch()
            self.browser_version = self.browser.version

            context_args: Dict[str, Any] = {"viewport": {"width": 1280, "height": 800}}
            if settings.deterministic_browser:
                context_args.update(reduced_motion="reduce", locale="en-US", timezone_id="UTC")
            if storage_state:
                context_args["storage_state"] = storage_state
            if self.artifact_dir:
                self.artifact_dir.mkdir(parents=True, exist_ok=True)
                context_args["record_har_path"] = str(self.har_path)
            self.context = await self.browser.new_context(**context_args)
            await self.context.route("**/*", self._guard)
            if settings.deterministic_browser:
                # Date.now()/new Date() read the same instant on every run; timers still fire so the app keeps working.
                await self.context.clock.set_fixed_time(datetime.fromisoformat(settings.fixed_clock_iso))
                await self.context.add_init_script(ANIMATIONS_OFF)
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

    async def export_state(self) -> Optional[Dict[str, Any]]:
        """The signed-in session (cookies and local storage), for other journeys to start from."""
        try:
            return await self.context.storage_state() if self.context else None
        except Exception:
            return None

    async def stop(self) -> None:
        """Closes the browser; trace.zip and har.json are flushed to artifact_dir."""
        if self.context:
            if self.trace_path:
                try:
                    await self.context.tracing.stop(path=str(self.trace_path))
                except Exception:
                    pass
            if self.session_mode:
                # Leave the user's Chrome and its other tabs alone: close only the tab we opened.
                if self.page:
                    try:
                        await self.page.close()
                    except Exception:
                        pass
                if not settings.cdp_url:
                    await self.context.close()  # our own persistent-profile Chrome
            else:
                await self.context.close()  # flushes the HAR
        if self.browser and not self.session_mode:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
