"""
Sign in once, reuse the session in every run (Microsoft SSO, MFA, ...).

    QAGENT_USER_DATA_DIR=~/.qagent/chrome-profile python -m qagent.browser.profile https://your-app.example.com

Opens Chrome on that profile folder. Sign in by hand, then close the window. Later runs with the same
QAGENT_USER_DATA_DIR start already signed in. (Chrome 136+ refuses remote debugging on your everyday profile,
so QAgent keeps its own profile folder instead of borrowing the default one.)
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

from qagent.config import settings


async def main(url: str) -> None:
    folder = os.path.expanduser(settings.user_data_dir or "~/.qagent/chrome-profile")
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            folder, channel=settings.browser_channel or "chrome", headless=False,
            ignore_default_args=["--enable-automation"], viewport=None,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url)
        print(f"Chrome is open on profile {folder}. Sign in, then close the window.")
        closed = asyncio.Event()
        context.on("close", lambda _: closed.set())
        await closed.wait()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    asyncio.run(main(sys.argv[1]))
