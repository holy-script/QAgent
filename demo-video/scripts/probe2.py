import os
from playwright.sync_api import sync_playwright
B="https://qagent-web-mu.vercel.app/"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx=b.new_context(viewport={"width":1920,"height":1080})
    ctx.add_init_script('try{localStorage.setItem("qagent_tours",JSON.stringify(["home","app","run","plan","bug"]))}catch(e){}')
    pg = ctx.new_page(); pg.goto(B+"login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    pg.goto(B+"apps/eco/runs/02475b32-5567-4fc0-ae64-4d8b5894017c"); pg.wait_for_timeout(5000)
    pg.get_by_text("Problems", exact=False).nth(1).click(); pg.wait_for_timeout(2000)
    print(pg.evaluate("""() => { const t=[...document.querySelectorAll('*')].find(e=>e.children.length==0 && /Client error on POST/.test(e.innerText||'')); const out=[]; let e=t; for(let i=0;i<6&&e;i++){const r=e.getBoundingClientRect(); out.push(e.tagName+'.'+(e.className||'').toString().slice(0,60)+' '+Math.round(r.width)+'x'+Math.round(r.height)); e=e.parentElement;} return out; }"""))
    pg.get_by_text("See the proof").nth(1).click(); pg.wait_for_timeout(3500)
    print(pg.evaluate("""() => [...document.querySelectorAll('img')].map(i=>{const r=i.getBoundingClientRect();return (i.alt||'')+' '+Math.round(r.x)+','+Math.round(r.y)+' '+Math.round(r.width)+'x'+Math.round(r.height)+' '+(i.closest('[role=dialog],[data-slot]')||{}).tagName})"""))
    print(pg.evaluate("""() => [...document.querySelectorAll('[role=dialog],[data-slot*=sheet]')].map(e=>e.tagName+' '+e.getAttribute('data-slot')+' '+Math.round(e.getBoundingClientRect().x))"""))
    b.close()
