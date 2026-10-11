"""
One place that decides which Chromium QAgent drives, so every machine and test run behaves the same.

Order of preference:
  1. QAGENT_BROWSER_PATH       an explicit executable (for custom builds or locked-down hosts)
  2. Playwright's own Chromium the version pinned by uv.lock; `make browsers` installs it (honours PLAYWRIGHT_BROWSERS_PATH)
  3. QAGENT_BROWSER_CHANNEL    a branded browser such as "chrome" or "msedge", only if you ask for it
  4. an installed Chrome/Edge  last resort, logged as a warning because the version is not pinned
"""
from typing import Any, List, Optional, Tuple

from playwright.async_api import Browser, Playwright

from qagent.config import settings
from qagent.engine.tracing import logger

DEFAULT_ARGS = ["--no-sandbox", "--disable-setuid-sandbox"]
FALLBACK_CHANNELS = ("chrome", "msedge")


class BrowserUnavailable(RuntimeError):
    pass


async def launch_chromium(pw: Playwright, headless: bool = True, args: Optional[List[str]] = None) -> Tuple[Browser, str]:
    """Returns (browser, source) where source says which option above was used."""
    args = args if args is not None else DEFAULT_ARGS
    errors: List[str] = []

    async def attempt(label: str, **kw: Any) -> Optional[Browser]:
        try:
            return await pw.chromium.launch(headless=headless, args=args, **kw)
        except Exception as exc:
            errors.append(f"{label}: {str(exc).splitlines()[0][:140]}")
            return None

    if settings.browser_path:
        browser = await attempt("QAGENT_BROWSER_PATH", executable_path=settings.browser_path)
        if browser:
            return browser, f"executable {settings.browser_path}"
        raise BrowserUnavailable(f"QAGENT_BROWSER_PATH is set but not usable ({errors[-1]})")

    if not settings.browser_channel:
        browser = await attempt("Playwright Chromium")
        if browser:
            return browser, "playwright-chromium"
    else:
        browser = await attempt(f"channel {settings.browser_channel}", channel=settings.browser_channel)
        if browser:
            return browser, f"channel {settings.browser_channel}"

    for channel in FALLBACK_CHANNELS:
        browser = await attempt(f"channel {channel}", channel=channel)
        if browser:
            logger.warning("browser.fallback", channel=channel, hint="run `make browsers` to install the pinned Chromium")
            return browser, f"fallback channel {channel}"

    raise BrowserUnavailable(
        "No browser could be started. Run `make browsers` (installs the pinned Chromium) "
        "or set QAGENT_BROWSER_PATH. Tried: " + "; ".join(errors)
    )
