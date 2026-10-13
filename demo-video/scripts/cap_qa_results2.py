import os, re
from rec import Session
from common import *
RUN = "02475b32-5567-4fc0-ae64-4d8b5894017c"
with Session("qa_results") as s:
    pg = s.page; login(s)
    pg.goto(B + "apps/eco/runs/" + RUN); s.wait(5000); s.start(); s.wait(800)
    s.track_text("k_steps", "^Steps taken", closest=CARD); s.track_text("k_problems", "^Problems found", closest=CARD)
    s.track_text("k_fast", "^Fast AI / Strong AI", closest=CARD); s.track_text("k_cost", "^AI cost", closest=CARD)
    s.track("repeat", "() => [...document.querySelectorAll('button,a')].find(b => /Repeat exactly/.test(b.innerText))")
    s.track_text("jsign", "^sign-in$", closest=CARD, nth=0)
    s.move(700, 190, 0.8); s.wait(2800)
    s.scroll(430, 1.6); s.wait(2800)
    s.click(pg.get_by_text("Problems", exact=False).nth(1)); s.wait(2200)
    s.track_text("p422", "Client error on POST", closest=CARD)
    s.track_text("pexport", "Export Forecast \\(\\.csv\\) starts a download of a CSV file", closest=CARD)
    s.track_text("pdeck", "Generate Deck \\(\\.pptx\\) starts a download", closest=CARD)
    s.track_css("proofimg", 'img[alt="Annotated screenshot"]'); s.track_css("sheet", '[data-slot="sheet-content"]')
    s.wait(2500)
    card = pg.locator(CARD).filter(has_text="Client error on POST").filter(has_text="See the proof").last
    s.click(card.get_by_text("See the proof")); s.wait(5000)
    pg.keyboard.press("Escape"); s.wait(1200)
    pg.locator(CARD).filter(has_text="Export Forecast (.csv) starts a download of a CSV file").last.scroll_into_view_if_needed(); s.wait(3800)
    pg.screenshot(path="footage/_r_after.png")
