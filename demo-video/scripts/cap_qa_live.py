import os
from rec import Session
B = "https://qagent-web-mu.vercel.app/"
with Session("qa_live") as s:
    pg = s.page
    pg.goto(B + "login"); s.wait(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); s.wait(4000)
    pg.goto(B + "apps/eco"); s.wait(3500); s.start(); s.wait(900)
    s.click(pg.get_by_role("combobox").first); s.wait(700)
    pg.screenshot(path="footage/_l0.png")
    s.click(pg.get_by_role("option", name="EcoForecast PRD plan (demo)").first); s.wait(900)
    s.click(pg.get_by_role("button", name="Run now")); s.wait(4000)
    print(pg.url)
    for i in range(14):
        s.wait(10000); pg.screenshot(path=f"footage/_l{i+1}.png")
    print(pg.url)
