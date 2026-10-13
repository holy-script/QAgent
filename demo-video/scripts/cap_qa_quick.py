import os, re
from rec import Session
from common import *
NOTES = "App: https://ecosystem-forecast.vercel.app. Enter the username and password and click Sign in. Choose a 12 month horizon. Upload ocrevus_trx_data.csv and confirm the column mapping. The validation should show 6 of 6 checks passed."
with Session("qa_quick") as s:
    pg = s.page; login(s)
    pg.goto(B + "apps/eco/playbooks/new"); s.wait(3000); s.start(); s.wait(800)
    s.click(pg.get_by_role("button", name="Text", exact=True)); s.wait(900)
    ed = pg.locator(".cm-content, textarea").first
    s.click(ed, pause_after=300)
    for ch in NOTES:
        pg.keyboard.type(ch); s.wait(28 if ch != " " else 45)
    s.wait(1500)
    s.track("editor", "() => document.querySelector('.cm-editor, textarea')")
    s.click(pg.get_by_role("button", name=re.compile("Rewrite my notes")))
    pg.get_by_text("Review the rewritten test plan").wait_for(timeout=120000); s.wait(1500)
    s.track_text("diff", "Review the rewritten test plan", closest='[role="dialog"]')
    s.wait(2500); s.scroll(260, 1.2); s.wait(2500)
    s.click(pg.get_by_role("button", name="Use the rewritten version")); s.wait(1800)
    s.click(pg.get_by_role("button", name="Save and review")); s.wait(4000)
    pg.screenshot(path="footage/_q_plan.png")
    title = pg.locator("h1, h2").first.inner_text(); print("PLAN:", title)
    s.goto(B + "apps/eco")
    s.click(pg.get_by_role("combobox").first); s.wait(700)
    s.click(pg.get_by_role("option").filter(has_text=title).first); s.wait(900)
    s.track_text("runpanel", "Run a test", closest=CARD)
    s.track_text("smart", "^Smart", min_w=250)
    s.click(pg.get_by_role("button", name="Run now")); s.wait(4000)
    s.track_text("running", "A test run is in progress", min_w=900)
    s.track_text("k_steps", "^Steps taken", closest=CARD)
    s.track_text("jfirst", "^sign-in$", closest=CARD)
    for i in range(200):                                    # until the run is finished (about 4 min at most)
        txt = pg.inner_text("body")
        if re.search(r"\bRunning\b", txt) is None and i > 4: break
        s.wait(1200)
    s.wait(3500); pg.screenshot(path="footage/_q_done.png")
