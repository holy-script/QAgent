import time, base64
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=2); pg=ctx.new_page()
    pg.goto("https://ecosystem-forecast.vercel.app/login"); pg.wait_for_timeout(2000)
    cdp=ctx.new_cdp_session(pg)
    for fmt,q in (("jpeg",85),("jpeg",70),("webp",80)):
        t=time.time(); n=8; sz=0
        for _ in range(n):
            r=cdp.send("Page.captureScreenshot",{"format":fmt,"quality":q,"optimizeForSpeed":True}); sz+=len(r["data"])*3//4
        print(fmt,q,"ms/frame",round((time.time()-t)/n*1000),"KB",round(sz/n/1024))
    b.close()
