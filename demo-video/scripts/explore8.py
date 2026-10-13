import os, json
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx=b.new_context(viewport={"width":1920,"height":1080})
    ctx.add_init_script('try{localStorage.setItem("qagent_tours",JSON.stringify(["home","app","run","plan","bug"]))}catch(e){}')
    pg = ctx.new_page()
    pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    for path in ["apps/new","apps/eco/flows","apps/eco/issues","apps/eco/traceability","apps/eco/compare","apps/eco/settings"]:
        pg.goto(B+path); pg.wait_for_timeout(3500)
        pg.screenshot(path="footage/_x_"+path.replace("/","_")+".png"); print("==",path); print(pg.inner_text("body")[:600].replace("\n"," | "))
    b.close()
