import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
NOTES="Sign in. Choose a 12 month horizon. Upload ocrevus_trx_data.csv and confirm the column mapping. The validation should show 6 of 6 checks passed."
with sync_playwright() as p:
    b = p.chromium.launch(); ctx=b.new_context(viewport={"width":1920,"height":1080})
    ctx.add_init_script('try{localStorage.setItem("qagent_tours",JSON.stringify(["home","app","run","plan","bug"]))}catch(e){}')
    pg = ctx.new_page()
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    pg.goto(B+"apps/eco/playbooks/new"); pg.wait_for_timeout(3000)
    pg.get_by_role("button", name="Create from product document").click(); pg.wait_for_timeout(2500)
    pg.screenshot(path="footage/_y1.png"); print(pg.inner_text("body")[:900].replace("\n"," | "))
    pg.goto(B+"apps/eco/playbooks/new"); pg.wait_for_timeout(3000)
    pg.get_by_role("button", name="Text", exact=True).click(); pg.wait_for_timeout(1000)
    ta = pg.locator("textarea, .cm-content").first
    ta.click(); pg.keyboard.type(NOTES); pg.wait_for_timeout(500)
    pg.screenshot(path="footage/_y2.png")
    pg.get_by_role("button", name="Rewrite my notes").click(); pg.wait_for_timeout(45000)
    pg.screenshot(path="footage/_y3.png"); print(pg.inner_text("body")[:600].replace("\n"," | "))
    b.close()
