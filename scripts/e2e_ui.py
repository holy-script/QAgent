"""Drives the running stack (make dev) through the UI: opens the app, starts a run, waits for it and saves
screenshots to /tmp/e2e. Usage: cd backend && uv run python ../scripts/e2e_ui.py [Stub|Hybrid|Baseline]"""
import asyncio, sys, time
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"
MODE = sys.argv[1] if len(sys.argv) > 1 else "Stub"

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(channel="chrome", headless=True)
        page = await b.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text[:200]}") if m.type in ("error",) else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))
        page.on("requestfailed", lambda r: errors.append(f"reqfailed: {r.url[:120]} {r.failure}"))
        page.on("response", lambda r: errors.append(f"http {r.status}: {r.url[:120]}") if r.status >= 400 and "localhost:8000" in r.url else None)

        async def shot(name):
            await page.screenshot(path=f"/tmp/e2e/{name}.png")

        await page.goto(BASE); await page.wait_for_timeout(1500); await shot("01-home")
        print("home:", (await page.inner_text("body"))[:200].replace("\n", " | "))
        await page.goto(f"{BASE}/apps/demo-shop"); await page.wait_for_timeout(2000); await shot("02-app")
        print("app:", (await page.inner_text("body"))[:300].replace("\n", " | "))
        await page.goto(f"{BASE}/apps/demo-shop/playbooks"); await page.wait_for_timeout(2500); await shot("03-playbooks")
        print("playbooks:", (await page.inner_text("body"))[:300].replace("\n", " | "))

        await page.goto(f"{BASE}/apps/demo-shop"); await page.wait_for_timeout(2500)
        await page.get_by_role("radio", name=MODE).click()
        await page.get_by_role("button", name="Run now").click()
        await page.wait_for_url("**/runs/**", timeout=20000)
        print("run url:", page.url)
        start = time.time(); n = 0
        while time.time() - start < 240:
            await page.wait_for_timeout(8000); n += 1
            body = await page.inner_text("body")
            await shot(f"run-{n:02d}")
            done = any(w in body for w in ("passed", "failed")) and "running" not in body.lower().split("status")[0][-200:]
            print(f"t={int(time.time()-start)}s", body[:160].replace("\n", " | "))
            if "Replay" in body and ("failed" in body or "passed" in body): break
        await shot("99-final")
        print("--- errors:"); [print(" ", e) for e in errors[:25]]
        await b.close()

asyncio.run(main())
