import os, re
from rec import Session
from common import *
with Session("qa_bugs") as s:
    pg = s.page; login(s)
    pg.goto(B + "apps/eco/issues"); s.wait(3500)
    # footage-only: the committed fix (wrapping long bug titles) is not deployed yet, so apply the same CSS here
    pg.add_style_tag(content='td[data-slot="table-cell"]:first-child{white-space:normal!important;width:28rem;min-width:18rem;max-width:28rem}td[data-slot="table-cell"]:first-child a{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}')
    s.start(); s.wait(800)
    s.track("filters", "() => [...document.querySelectorAll('button')].find(b => /^Came back$/.test(b.innerText.trim()))?.parentElement")
    s.track_text("bugtable", "^Bug$", min_w=1000)
    s.move(900, 330, 0.9); s.wait(2200)
    s.click(pg.get_by_role("button", name="Came back", exact=True)); s.wait(2600)
    s.click(pg.get_by_role("button", name="Fixed", exact=True)); s.wait(2600)
    s.click(pg.get_by_role("button", name="All", exact=True)); s.wait(1200)
    pg.goto(B + "apps/eco/traceability"); s.wait(3500)
    s.track_text("reqkpi", "^Not tested$", min_w=1300)
    s.track_text("req1", "^REQ-1$", min_w=900)
    s.move(900, 250, 0.8); s.wait(2800)
    s.scroll(380, 1.6); s.wait(2500)
    pg.goto(B + "apps/eco/runs/02475b32-5567-4fc0-ae64-4d8b5894017c"); s.wait(4500)
    s.track("repeat", "() => [...document.querySelectorAll('button,a')].find(b => /Repeat exactly/.test(b.innerText))")
    s.move(1455, 95, 1.0); s.wait(3500)
