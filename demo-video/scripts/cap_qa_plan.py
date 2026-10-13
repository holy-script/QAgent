import os, re
from rec import Session
from common import *
with Session("qa_plan") as s:
    pg = s.page; login(s)
    pg.goto(B + "apps/eco/playbooks"); s.wait(3000); s.start(); s.wait(800)
    s.click(pg.get_by_role("link", name="Add a test plan")); s.wait(2000)
    gen = pg.get_by_role("button", name="Create from product document")
    s.click(gen); s.wait(1500)
    for _ in range(160):                                   # about 30 s of "Writing the plan…"
        if pg.get_by_text("Writing the plan").count() == 0: break
        s.wait(500)
    s.wait(1500)
    pg.screenshot(path="footage/_p_after_gen.png")
    s.track_text("counts", "^Requirements\\s*12", min_w=0)
    s.click(pg.get_by_text(re.compile(r"^Journeys\s*\d*$")).first); s.wait(3000)
    s.scroll(260, 1.2); s.wait(2200)
    pg.on("dialog", lambda d: d.accept())
    pg.goto(B + "apps/eco/playbooks"); s.wait(2500)
    s.click(pg.get_by_text("EcoForecast PRD plan (demo)").first); s.wait(3500)
    s.track_text("jcol", "WHAT QAGENT UNDERSTOOD", min_w=500)
    s.track_text("jcard_sign", "^sign-in$", closest=CARD)
    s.track_text("jcard_clean", "^clean-forecast-end-to-end$", closest=CARD)
    s.track_text("nums", "national baseline of 6,786", tag="li")
    s.track_text("expect", "Should be true afterwards", nth=1, min_w=300)
    s.move(1230, 330, 0.9); s.wait(2500)
    s.scroll(300, 1.6); s.wait(4500)
