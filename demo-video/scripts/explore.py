import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1920,"height":1080})
    pg.goto("https://qagent-web-mu.vercel.app/login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email], input[name=email]", os.environ["QAGENT_EMAIL"])
    pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"])
    pg.keyboard.press("Enter"); pg.wait_for_timeout(5000)
    print(pg.url); pg.screenshot(path="footage/_home.png")
    print(pg.inner_text("body")[:700])
    pg.goto("https://ecosystem-forecast.vercel.app"); pg.wait_for_timeout(4000)
    pg.screenshot(path="footage/_eco.png"); print(pg.url); print(pg.inner_text("body")[:400])
    b.close()
