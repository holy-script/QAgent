import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"])
    pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    pg.goto(B+"apps/eco/runs/02475b32-5567-4fc0-ae64-4d8b5894017c"); pg.wait_for_timeout(5000)
    pg.screenshot(path="footage/_run.png"); print(pg.inner_text("body")[:1500].replace("\n"," | "))
    pg.goto(B+"apps/eco/playbooks"); pg.wait_for_timeout(3000)
    for a in pg.query_selector_all("a"): 
        h=a.get_attribute("href") or ""
        if "playbooks/" in h: print(h, a.inner_text()[:50].replace("\n"," "))
    b.close()
