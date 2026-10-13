import os
import re
from rec import Session
B = "https://qagent-web-mu.vercel.app/"
RUN = "02475b32-5567-4fc0-ae64-4d8b5894017c"
with Session("qa_results") as s:
    pg = s.page
    pg.goto(B + "login"); s.wait(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); s.wait(4000)
    pg.goto(B + "apps/eco/runs/" + RUN); s.wait(4500); s.start(); s.wait(800)
    s.move(700, 190, 0.8); s.wait(1800)                      # KPI strip
    s.scroll(480, 1.6); s.wait(1600)
    s.click(pg.get_by_role("tab", name=re.compile("Problems")) if False else pg.get_by_text("Problems", exact=False).nth(1)); s.wait(2500)
    s.move(1440, 400, 0.9); s.wait(1600)
    s.click(pg.get_by_text("See the proof").nth(1)); s.wait(3500)
    pg.screenshot(path="footage/_r2.png")
    s.wait(2500)
    pg.keyboard.press("Escape"); s.wait(800)
    s.scroll(620, 2.0); s.wait(2200)
    s.scroll(620, 2.0); s.wait(1800)
    pg.screenshot(path="footage/_r3.png")
