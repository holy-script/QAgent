from playwright.async_api import async_playwright

from qagent.config import settings


async def html_to_pdf(html: str) -> bytes:
    """Prints HTML to PDF with Chromium (no extra dependency)."""
    async with async_playwright() as pw:
        args = ["--no-sandbox"]
        try:
            browser = await pw.chromium.launch(args=args, channel=settings.browser_channel)
        except Exception:
            browser = await pw.chromium.launch(args=args, channel="chrome")
        try:
            page = await browser.new_page()
            await page.set_content(html)
            return await page.pdf(format="A4", print_background=True, margin={"top": "16mm", "bottom": "16mm",
                                                                             "left": "12mm", "right": "12mm"})
        finally:
            await browser.close()
