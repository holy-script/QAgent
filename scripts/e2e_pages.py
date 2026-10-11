"""Checks the pages that read finished-run data (issues, evidence, reports, traceability, editor, palette).
Needs `make dev` running and at least one finished run. Usage: cd backend && uv run python ../scripts/e2e_pages.py"""
import asyncio, json, urllib.request
from playwright.async_api import async_playwright

FE, API = "http://localhost:3000", "http://localhost:8000"
get = lambda p: json.load(urllib.request.urlopen(API + p))

async def main():
    runs = [r for r in get("/apps/demo-shop/runs") if r["status"] in ("passed", "failed") and r["totals"]["findings_count"] > 0]
    def has_report(r):
        try: get(f"/runs/{r['id']}/report"); return True
        except Exception: return False
    run_id = next(r["id"] for r in runs if has_report(r) and r["mode"] != "stub")
    ok, bad = [], []
    def check(name, cond, detail=""):
        (ok if cond else bad).append(name); print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))

    async with async_playwright() as pw:
        b = await pw.chromium.launch(channel="chrome", headless=True)
        ctx = await b.new_context(viewport={"width": 1440, "height": 1000}, permissions=["clipboard-read", "clipboard-write"])
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        page.on("response", lambda r: errors.append(f"http {r.status} {r.url[:110]}") if r.status >= 400 and "localhost:8000" in r.url else None)
        shot = lambda n: page.screenshot(path=f"/tmp/e2e/p-{n}.png")

        # issues list + issue page (bug report)
        await page.goto(f"{FE}/apps/demo-shop/issues"); await page.wait_for_selector("table", timeout=15000); await shot("issues")
        check("issues list shows rows", await page.locator("tbody tr").count() >= 5)
        await page.locator("tbody a").first.click(); await page.wait_for_selector("text=Steps to reproduce", timeout=20000); await page.wait_for_timeout(1500); await shot("issue")
        body = (await page.inner_text("body")).lower()
        check("bug page has report sections", all(t in body for t in ("requirements affected", "what should happen vs what happened", "proof", "why it matters")))
        await page.get_by_role("button", name="Copy for my issue tracker").click(); await page.wait_for_timeout(800)
        clip = await page.evaluate("navigator.clipboard.readText()")
        check("copy as issue puts Markdown on the clipboard", "Steps to reproduce" in clip, clip[:80])

        # run page: findings -> evidence panel
        await page.goto(f"{FE}/apps/demo-shop/runs/{run_id}?tab=findings"); await page.wait_for_selector("text=See the proof", timeout=20000)
        await page.get_by_text("See the proof").first.click(); await page.wait_for_selector("[aria-label='Finding evidence'] >> text=What should happen", timeout=15000); await page.wait_for_timeout(2000); await shot("evidence")
        dlg = (await page.locator("[aria-label='Finding evidence']").inner_text()).lower()
        check("evidence panel shows check inputs / calls", "values compared" in dlg or "server calls" in dlg, dlg[:100])
        check("evidence panel shows screenshots", await page.locator("[aria-label='Finding evidence'] img").count() >= 1)
        await page.keyboard.press("Escape")

        # network bodies
        await page.get_by_role("tab", name="Server calls").click(); await page.wait_for_timeout(500)
        row = page.locator("tbody tr", has_text="500").first
        await row.click(); await page.wait_for_timeout(2500); await shot("network")
        check("network row shows the 500 response body", "Payment gateway error" in await page.inner_text("body"))

        # step drawer: before/after + wait frames + candidates
        await page.get_by_role("tab", name="Journeys").click(); await page.wait_for_timeout(500)
        await page.locator("main img").nth(1).click(); await page.wait_for_selector("[aria-label$='details']", timeout=8000); await page.wait_for_timeout(2500); await shot("drawer")
        check("drawer has before/after toggle", await page.get_by_role("button", name="before").count() == 1)
        check("drawer overlays candidates", await page.locator("[aria-label$='details'] [title^='#']").count() >= 1)
        await page.keyboard.press("Escape")

        # report
        await page.goto(f"{FE}/apps/demo-shop/runs/{run_id}/report"); await page.wait_for_selector("text=Requirements", timeout=20000); await shot("report")
        body = (await page.inner_text("body")).lower()
        check("report sections", all(t in body for t in ("journeys", "problems by type", "suggested next steps", "how reliable was this run")))
        # traceability
        await page.goto(f"{FE}/apps/demo-shop/traceability"); await page.wait_for_selector("text=REQ-1", timeout=15000); await shot("trace")
        check("traceability lists requirements", "REQ-3" in await page.inner_text("body"))
        # overview
        await page.goto(f"{FE}/apps/demo-shop"); await page.wait_for_selector("text=Open bugs", timeout=15000); await page.wait_for_timeout(2500); await shot("overview")
        check("overview shows open issues + coverage", "requirements" in (await page.inner_text("body")).lower())

        # playbook editor
        await page.goto(f"{FE}/apps/demo-shop/playbooks"); await page.wait_for_timeout(1500)
        await page.locator("a[href*='/playbooks/']:not([href$='/new'])").first.click(); await page.wait_for_selector("text=Edit test plan", timeout=10000)
        await page.get_by_role("button", name="Edit test plan", exact=True).click(); await page.wait_for_selector("text=Add requirement", timeout=15000); await page.wait_for_timeout(1500); await shot("editor")
        check("editor shows category tabs with counts", await page.get_by_role("tab", name="Journeys").count() == 1)
        await page.get_by_label("Statement *").fill("Orders can be cancelled")
        await page.get_by_label("Acceptance criteria *").fill("A placed order can be cancelled before it ships")
        await page.get_by_role("button", name="Add to test plan").click(); await page.wait_for_timeout(1800)
        body = await page.inner_text("body")
        check("added requirement appears and flags uncovered", "REQ-4" in body and "no journey tests yet" in body.lower())
        await page.get_by_role("button", name="Text", exact=True).click(); await page.wait_for_timeout(300)
        check("raw view contains the new item", "### REQ-4: Orders can be cancelled" in await page.locator("textarea").first.input_value())
        await page.get_by_role("button", name="Guided").click()
        await page.locator("textarea[aria-label]").count()
        # invalid edit -> error blocks save
        await page.get_by_role("button", name="Text", exact=True).click()
        ta = page.locator("textarea").first; txt = await ta.input_value(); await ta.fill(txt.replace("- verifies: REQ-1", "- verifies: REQ-99")); await page.wait_for_timeout(1500)
        check("validation error blocks saving", await page.get_by_role("button", name="Save as version 2").is_disabled() and "REQ-99" in await page.inner_text("body"))
        await shot("editor-error")

        # command palette
        await page.goto(f"{FE}/apps/demo-shop"); await page.wait_for_timeout(1000)
        await page.keyboard.press("Control+k"); await page.get_by_placeholder("Search pages, runs and bugs…").fill("bugs"); await page.wait_for_timeout(1500); await shot("palette")
        check("command palette lists issues", await page.locator("[role=option]").count() >= 1)
        await page.keyboard.press("Enter"); await page.wait_for_timeout(1500)
        check("palette navigates", "/issues" in page.url, page.url)

        # replay panel
        await page.goto(f"{FE}/apps/demo-shop/runs/{run_id}"); await page.wait_for_selector("text=Repeat exactly", timeout=20000)
        await page.get_by_role("button", name="Repeat exactly").click(); await page.wait_for_selector("text=Act without double-checking above"); await shot("replay-panel")
        check("replay panel opens", True)
        await page.get_by_role("button", name="Start repeat run").click(); await page.wait_for_url(lambda u: run_id not in u and "/runs/" in u, timeout=20000)
        check("re-run from tape starts a new run", True)

        # PRD extraction (real Claude call)
        prd = "# Demo shop PRD\n## 4.2 Orders\nCustomers can cancel an order until it ships. A cancelled order refunds the full amount.\n## 3.1 Search\nThe search box returns matching products within two seconds."
        req = urllib.request.Request(API + "/apps/demo-shop", data=json.dumps({"prd_markdown": prd}).encode(), method="PATCH", headers={"Content-Type": "application/json"}); urllib.request.urlopen(req)
        await page.goto(f"{FE}/apps/demo-shop/playbooks"); await page.wait_for_timeout(1500)
        await page.locator("a[href*='/playbooks/']:not([href$='/new'])").first.click(); await page.get_by_role("button", name="Edit test plan", exact=True).click()
        await page.get_by_role("button", name="Suggest requirements").click(); await page.get_by_role("button", name="Accept", exact=True).first.wait_for(timeout=60000); await shot("prd")
        n = await page.get_by_role("button", name="Accept", exact=True).count()
        check("PRD extraction proposes requirements with quotes", n >= 1 and "“" in await page.inner_text("body"))
        await page.get_by_role("button", name="Accept", exact=True).first.click(); await page.wait_for_timeout(1500)
        check("accepted proposal is added", "Added" in await page.inner_text("body"))

        # normalize freeform text (real Claude call) with diff review
        await page.goto(f"{FE}/apps/demo-shop/playbooks/new"); await page.wait_for_timeout(1000)
        await page.get_by_role("button", name="Text", exact=True).click()
        await page.locator("textarea").first.fill("Test the shop: open the products page, add two items to the cart, go to the cart. The cart should show 2 items and a visible total.")
        await page.get_by_role("button", name="Rewrite my notes as a test plan").click(); await page.wait_for_selector("text=Review the rewritten test plan", timeout=60000); await shot("normalize")
        check("normalize shows a diff", await page.locator("text=Use the rewritten version").count() == 1)
        await page.get_by_role("button", name="Use the rewritten version").click(); await page.wait_for_timeout(2000)
        check("normalized playbook validates", await page.get_by_role("button", name="Save and review").is_enabled(), (await page.inner_text("body"))[:0])
        print("\npage errors / failed API calls:"); [print(" ", e) for e in errors[:15]]
        await b.close()
    print(f"\n{len(ok)} passed, {len(bad)} failed: {bad}")

asyncio.run(main())
