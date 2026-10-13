import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"])
    pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    for path in ["apps/eco","apps/eco/flows","apps/eco/runs"]:
        pg.goto(B+path); pg.wait_for_timeout(3000)
        print(path, [x.inner_text()[:30].replace("\n"," ") for x in pg.query_selector_all("button") if x.inner_text().strip()])
    pg.goto(B+"apps/eco"); pg.wait_for_timeout(2500)
    pg.screenshot(path="footage/_eco_over.png")
    b.close()
