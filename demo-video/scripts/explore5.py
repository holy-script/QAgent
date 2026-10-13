import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"])
    pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    pg.goto(B+"apps/eco/playbooks/b9434de2-54f0-40f0-a0a9-7ea1de9a6242"); pg.wait_for_timeout(4000)
    pg.screenshot(path="footage/_plan.png"); print(pg.inner_text("body")[:900].replace("\n"," | "))
    print([ (x.inner_text()[:40]) for x in pg.query_selector_all("button")][:30])
    pg.goto(B+"apps/eco/playbooks/new"); pg.wait_for_timeout(3000)
    pg.screenshot(path="footage/_new.png"); print(pg.inner_text("body")[:900].replace("\n"," | "))
    b.close()
