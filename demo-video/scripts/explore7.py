import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    pg.goto(B+"apps/eco/runs/a6a2b404-eeb8-4fbc-ad85-edfb0899812f"); pg.wait_for_timeout(4000)
    print([x.inner_text()[:30] for x in pg.query_selector_all("button,a") if "atch" in x.inner_text()])
    pg.get_by_text("Watch it live").first.click(); pg.wait_for_timeout(5000)
    pg.screenshot(path="footage/_live2.png"); print(pg.url)
    b.close()
