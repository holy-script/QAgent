from playwright.async_api import async_playwright

from qagent.browser.launcher import launch_chromium


async def html_to_pdf(html: str) -> bytes:
    """Prints HTML to PDF with the same Chromium the runs use (no extra dependency)."""
    async with async_playwright() as pw:
        browser, _ = await launch_chromium(pw)
        try:
            page = await browser.new_page()
            await page.set_content(html)
            return await page.pdf(format="A4", print_background=True,
                                  margin={"top": "16mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        finally:
            await browser.close()
