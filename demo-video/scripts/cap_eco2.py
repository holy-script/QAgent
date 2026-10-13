import os, re
from rec import Session
F = os.path.abspath("../demo-ecoforecast/test-files/ocrevus_trx_data.csv")
with Session("eco_app") as s:
    pg = s.page
    pg.goto("https://ecosystem-forecast.vercel.app/login"); s.wait(2500); s.start(); s.wait(1000)
    s.track_text("kpirow", "NATIONAL BASELINE TRX", min_w=1300)
    s.track_text("bestfit", "Best Fit", min_w=1300)
    s.track_text("matrix", "Model Evaluation Matrix", min_w=1300)
    s.track_text("validation", "6 integrity checks", min_w=420)
    s.track_text("mapping", "Column mapping", min_w=600)
    s.type(pg.locator("input").first, "admin"); s.type(pg.locator("input[type=password]"), os.environ["ECO_PASSWORD"])
    s.click(pg.get_by_role("button", name="Sign in")); s.wait(3500)
    s.click(pg.get_by_text("12 months").first); s.wait(700)
    s.click(pg.get_by_text("Upload Historical Data").first); s.wait(1200)
    pg.set_input_files("input[type=file]", F); s.wait(3000)
    s.scroll(420, 1.2); s.wait(1200)
    s.click(pg.get_by_role("button", name="Confirm Mapping")); s.wait(4500)
    s.click(pg.get_by_role("button", name="Proceed to Analysis")); s.wait(4000)
    s.click(pg.get_by_role("button", name="Proceed to Method")); s.wait(9000)
    pg.get_by_text("trend · seasonal (auto-selected)").first.scroll_into_view_if_needed(); s.wait(3500)   # matrix + "Best Fit" row, hold
    s.click(pg.get_by_text("trend · seasonal (auto-selected)").first); s.wait(900)
    s.click(pg.get_by_role("button", name="Use selected method")); s.wait(6000)                          # forecast, hold on the numbers
    s.move(1200, 520, 0.9); s.wait(1500)
