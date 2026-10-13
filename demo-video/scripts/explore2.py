import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto("https://qagent-web-mu.vercel.app/login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"])
    pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    for path in ["apps/eco","apps/eco/playbooks","apps/eco/runs","apps/eco/issues"]:
        pg.goto("https://qagent-web-mu.vercel.app/"+path); pg.wait_for_timeout(3500)
        pg.screenshot(path="footage/_"+path.replace("/","_")+".png")
        print("==",path, pg.url); print(pg.inner_text("body")[:500].replace("\n"," | "))
    b.close()
