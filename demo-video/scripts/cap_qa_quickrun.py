import os, re, time
from rec import Session
from common import *
PLAN = "Data Upload and Validation"
with Session("qa_quickrun") as s:
    pg = s.page; login(s)
    for _ in range(80):                                      # wait (not recording) until nothing else is running: runs go one at a time
        pg.goto(B + "apps/eco"); pg.wait_for_timeout(3500)
        if not re.search(r"\bRunning\b", pg.inner_text("body")): break
        pg.wait_for_timeout(8000)
    s.start(); s.wait(1000)
    s.track_text("runpanel", "Run a test", closest=CARD)
    s.click(pg.get_by_role("combobox").first); s.wait(700)
    s.click(pg.get_by_role("option").filter(has_text=PLAN).first); s.wait(1000)
    s.click(pg.get_by_role("button", name="Run now")); s.wait(3500)
    s.track_text("k_steps", "^Steps taken", closest=CARD)
    s.track_text("k_problems", "^Problems found", closest=CARD)
    s.track_text("jfirst", "^sign-in$", closest=CARD)
    s.track_text("jval", "^upload-and-validate", closest=CARD)
    for i in range(160):
        txt = pg.inner_text("body")
        if i > 5 and re.search(r"\bRunning\b", txt) is None: break
        s.wait(1500)
    s.wait(4000)
    pg.screenshot(path="footage/_qr_done.png")
