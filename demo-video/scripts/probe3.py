import base64, struct
from playwright.sync_api import sync_playwright
def jpg_size(b):
    i=2
    while i<len(b):
        if b[i]!=0xFF: i+=1; continue
        m=b[i+1]
        if m in (0xC0,0xC2): return struct.unpack(">HH", b[i+5:i+9])[::-1]
        i+=2+struct.unpack(">H", b[i+2:i+4])[0]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=2); pg=ctx.new_page(); cdp=ctx.new_cdp_session(pg)
    got=[]
    cdp.on("Page.screencastFrame", lambda f: (got.append((jpg_size(base64.b64decode(f["data"])), f["metadata"])), cdp.send("Page.screencastFrameAck",{"sessionId":f["sessionId"]})))
    pg.goto("https://ecosystem-forecast.vercel.app/login"); pg.wait_for_timeout(1500)
    cdp.send("Page.startScreencast", {"format":"jpeg","quality":90,"maxWidth":3840,"maxHeight":2160,"everyNthFrame":1}); pg.wait_for_timeout(1500)
    print(got[:1]); 
    print("dpr", pg.evaluate("devicePixelRatio"))
    shot=pg.screenshot(); print("shot", jpg_size(shot) if shot[:2]==b"\xff\xd8" else struct.unpack(">II", shot[16:24]))
    b.close()
