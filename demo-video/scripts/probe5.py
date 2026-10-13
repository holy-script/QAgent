import time, base64, struct
from playwright.sync_api import sync_playwright
def size(b64):
    d=base64.b64decode(b64); i=2
    while i<len(d):
        if d[i]!=0xFF: i+=1; continue
        m=d[i+1]
        if m in (0xC0,0xC2): return struct.unpack(">HH", d[i+5:i+9])[::-1]
        i+=2+struct.unpack(">H", d[i+2:i+4])[0]
with sync_playwright() as p:
    b=p.chromium.launch()
    for dsf in (1,2):
        ctx=b.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=dsf); pg=ctx.new_page(); cdp=ctx.new_cdp_session(pg)
        pg.goto("https://ecosystem-forecast.vercel.app/login"); pg.wait_for_timeout(1500)
        t=time.time()
        for _ in range(6): r=cdp.send("Page.captureScreenshot",{"format":"jpeg","quality":86,"optimizeForSpeed":True,"clip":{"x":0,"y":0,"width":1920,"height":1080,"scale":2}})
        print("dsf",dsf,"clip.scale2 ->",size(r["data"]),"ms",round((time.time()-t)/6*1000))
        ctx.close()
    b.close()
