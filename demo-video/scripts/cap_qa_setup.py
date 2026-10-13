import os
from rec import Session
from common import *
with Session("qa_setup") as s:
    pg = s.page; login(s)
    pg.goto(B); s.wait(3000); s.start(); s.wait(800)
    s.click(pg.get_by_role("link", name="Add an app").or_(pg.get_by_role("button", name="Add an app")).first); s.wait(1800)
    s.track_text("addform", "Tell QAgent where your app lives", min_w=500)
    s.type(pg.locator("input").nth(0), "EcoForecast"); s.click(pg.locator("input").nth(1), pause_after=150); pg.keyboard.press("Meta+A"); pg.keyboard.press("Backspace"); s.type(pg.locator("input").nth(1), "https://ecosystem-forecast.vercel.app", delay=(25, 55)); s.wait(1500)
    s.click(pg.get_by_role("button", name="Cancel")); s.wait(1500)
    s.click(pg.get_by_text("EcoForecast").first); s.wait(2500)
    s.click(pg.get_by_role("link", name="Settings")); s.wait(3000)
    s.track_text("signin", "Sign-in details", closest=CARD)
    s.track_text("testfiles", "^Test files$", closest=CARD)
    s.track_text("hosts", "Other sites tests may visit", min_w=400)
    s.track_text("mode", "Default mode", min_w=400)
    s.move(1300, 300, 0.9); s.wait(2500)
    s.scroll(420, 1.4); s.wait(3500)
    s.move(500, 520, 0.9); s.wait(2500)
