import os
from playwright.sync_api import sync_playwright
F=os.path.abspath("../demo-ecoforecast/test-files/ocrevus_trx_data.csv")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto("https://ecosystem-forecast.vercel.app/login"); pg.wait_for_timeout(3000)
    pg.fill("input >> nth=0","admin"); pg.fill("input[type=password]", os.environ["ECO_PASSWORD"]); pg.get_by_role("button",name="Sign in").click(); pg.wait_for_timeout(5000)
    pg.screenshot(path="footage/_e1.png"); print([x.inner_text()[:25].replace("\n"," ") for x in pg.query_selector_all("button")])
    pg.get_by_text("12 months").first.click(); pg.wait_for_timeout(800)
    pg.get_by_text("Upload Historical Data").first.click(); pg.wait_for_timeout(1500)
    pg.set_input_files("input[type=file]", F); pg.wait_for_timeout(3000)
    pg.screenshot(path="footage/_e2.png"); print([x.inner_text()[:25].replace("\n"," ") for x in pg.query_selector_all("button")])
    b.close()
