import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto("https://qagent-web-mu.vercel.app/login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"])
    pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    pg.goto("https://qagent-web-mu.vercel.app/apps/eco/runs"); pg.wait_for_timeout(3500)
    for r in pg.query_selector_all("tbody tr"):
        print(r.inner_text().replace("\n"," | ").replace("\t"," | ")[:170], r.query_selector("a") and r.query_selector("a").get_attribute("href"))
    b.close()
