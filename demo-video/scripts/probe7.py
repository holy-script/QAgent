import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1920,"height":1080})
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); pg.wait_for_url(lambda u:"/login" not in u); pg.wait_for_timeout(2500)
    pg.goto(B+"apps/eco/playbooks"); pg.wait_for_timeout(3500)
    print([a.inner_text().replace("\n"," | ")[:110] for a in pg.query_selector_all("a") if "playbooks/" in (a.get_attribute("href") or "") and "new" not in a.get_attribute("href")])
    pg.goto(B+"apps/eco"); pg.wait_for_timeout(3000)
    print(pg.inner_text("body")[pg.inner_text("body").find("Recent test runs"):][:500].replace("\n"," | "))
    b.close()
