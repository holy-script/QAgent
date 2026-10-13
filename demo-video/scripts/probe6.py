import base64, struct, time
from playwright.sync_api import sync_playwright
def size(b64):
    d=base64.b64decode(b64); i=2
    while i<len(d):
        if d[i]!=0xFF: i+=1; continue
        m=d[i+1]
        if m in (0xC0,0xC2): return struct.unpack(">HH", d[i+5:i+9])[::-1]
        i+=2+struct.unpack(">H", d[i+2:i+4])[0]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=2); pg=ctx.new_page(); cdp=ctx.new_cdp_session(pg)
    pg.goto("https://qagent-web-mu.vercel.app/login"); pg.wait_for_timeout(1500)
    r=cdp.send("Page.captureScreenshot",{"format":"jpeg","quality":86,"optimizeForSpeed":True}); print("noclip dsf2",size(r["data"]))
    r=cdp.send("Page.captureScreenshot",{"format":"jpeg","quality":86,"optimizeForSpeed":True,"fromSurface":True,"captureBeyondViewport":False}); print("fromSurface",size(r["data"]))
    pg.evaluate("document.body.style.minHeight='4000px'; window.scrollTo(0,500)"); pg.wait_for_timeout(300)
    print("scrollY", pg.evaluate("scrollY"))
    r=cdp.send("Page.captureScreenshot",{"format":"jpeg","quality":86,"optimizeForSpeed":True,"clip":{"x":0,"y":0,"width":1920,"height":1080,"scale":2}}); open("footage/_clip0.jpg","wb").write(base64.b64decode(r["data"]))
    lm=cdp.send("Page.getLayoutMetrics"); print({k:lm["cssVisualViewport"][k] for k in ("pageX","pageY","clientWidth")})
    v=lm["cssVisualViewport"]
    r=cdp.send("Page.captureScreenshot",{"format":"jpeg","quality":86,"optimizeForSpeed":True,"clip":{"x":v["pageX"],"y":v["pageY"],"width":1920,"height":1080,"scale":2}}); print("clip at viewport",size(r["data"]))
    b.close()
