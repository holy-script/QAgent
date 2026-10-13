"""Studio-quality screen recorder on Playwright.
 - true 4K frames (device scale factor 2) captured with Page.captureScreenshot in lock-step with every action
 - a visible cursor and click ripple
 - element tracking: boxes of chosen elements are sampled every frame so overlays in the edit stay glued to the UI
 - QAgent's page tours are switched off
"""
import base64, json, os, random, shutil, subprocess, time
from playwright.sync_api import sync_playwright

PAGE_JS = """
(() => {
  if (window.__recInit) return; window.__recInit = true;
  try { localStorage.setItem('qagent_tours', JSON.stringify(['home','app','run','plan','bug'])); } catch (e) {}
  // ---- cursor
  const c = document.createElement('div'); window.__cur = c;
  c.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;left:0;top:0;width:28px;height:28px;transform:translate(-100px,-100px);filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))';
  c.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M5 2l14 9-6.2 1.4L16 20l-3 1.2-3.2-7.4L5 17z" fill="#fff" stroke="#111" stroke-width="1.3" stroke-linejoin="round"/></svg>';
  const r = document.createElement('div');
  r.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;width:46px;height:46px;border-radius:50%;border:3px solid rgba(201,146,42,.95);background:rgba(201,146,42,.22);transform:translate(-100px,-100px) scale(.3);opacity:0';
  const add = () => { document.documentElement.appendChild(c); document.documentElement.appendChild(r); };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', add) : add();
  window.addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX-4}px,${e.clientY-2}px)`; try { sessionStorage.__mx = e.clientX + ',' + e.clientY; } catch (_) {} }, true);
  try { const m = (sessionStorage.__mx || '').split(','); if (m.length == 2) c.style.transform = `translate(${m[0]-4}px,${m[1]-2}px)`; } catch (_) {}
  window.addEventListener('mousedown', e => { r.style.transition='none'; r.style.opacity='1'; r.style.transform=`translate(${e.clientX-23}px,${e.clientY-23}px) scale(.3)`;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{ r.style.transition='transform .45s ease-out, opacity .45s ease-out'; r.style.transform=`translate(${e.clientX-23}px,${e.clientY-23}px) scale(1.15)`; r.style.opacity='0'; })); }, true);
  // ---- element tracks (definitions survive navigation in sessionStorage)
  window.__trk = {};
  const load = () => { let d = {}; try { d = JSON.parse(sessionStorage.__trkdefs || '{}'); } catch (_) {} for (const n in d) if (!window.__trk[n]) window.__trk[n] = { fn: eval(d[n]), rows: [], last: undefined, src: d[n] }; };
  load();
  const loop = () => {
    const now = performance.timeOrigin + performance.now();
    for (const n in window.__trk) {
      const t = window.__trk[n]; let el = null; try { el = t.fn(); } catch (_) {}
      if (!el) { if (t.last !== null) { t.rows.push([now, 0, 0, 0, 0]); t.last = null; } continue; }
      const b = el.getBoundingClientRect(); const v = [b.x, b.y, b.width, b.height].map(x => Math.round(x * 10) / 10); const k = v.join(',');
      if (k !== t.last) { t.rows.push([now].concat(v)); t.last = k; }
    }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
})();
"""

class Session:
    def __init__(self, name, size=(1920, 1080), fps=30, dsf=2):
        self.name, self.size, self.fps, self.dsf = name, size, fps, dsf
        self.dir = f"footage/_frames_{name}"; shutil.rmtree(self.dir, ignore_errors=True); os.makedirs(self.dir)
        self.frames, self.tracks, self.defs = [], {}, {}
        self.mx, self.my, self.recording = 960, 540, False

    def __enter__(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.ctx = self.browser.new_context(viewport={"width": self.size[0], "height": self.size[1]}, device_scale_factor=self.dsf)
        self.ctx.add_init_script(PAGE_JS)
        self.page = self.ctx.new_page()
        self.cdp = self.ctx.new_cdp_session(self.page)
        return self

    # ---- frames
    def _snap(self):
        t = time.time()
        v = self.cdp.send("Page.getLayoutMetrics")["cssVisualViewport"]          # clip coordinates are document-relative: follow the scroll position
        r = self.cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 86, "optimizeForSpeed": True, "clip": {"x": v["pageX"], "y": v["pageY"], "width": self.size[0], "height": self.size[1], "scale": 2}})
        mid = (t + time.time()) / 2
        path = f"{self.dir}/{len(self.frames):06d}.jpg"
        with open(path, "wb") as f: f.write(base64.b64decode(r["data"]))
        self.frames.append((mid, path))

    def start(self): self.recording = True

    def wait(self, ms):
        end = time.time() + ms / 1000
        while True:
            t0 = time.time()
            if self.recording: self._snap(); self.harvest()
            if time.time() >= end: break
            rest = 1 / self.fps - (time.time() - t0)
            if rest > 0.002: self.page.wait_for_timeout(int(min(rest, end - time.time()) * 1000) or 1)

    def goto(self, url, settle=2500):
        self.page.goto(url); self.wait(settle)

    # ---- tracks
    def track(self, name, fn_src):
        self.defs[name] = fn_src
        self.page.evaluate("([n, src]) => { const d = JSON.parse(sessionStorage.__trkdefs || '{}'); d[n] = src; sessionStorage.__trkdefs = JSON.stringify(d); window.__trk[n] = { fn: eval(src), rows: [], last: undefined, src }; }", [name, fn_src])

    def track_text(self, name, text, tag="*", nth=0, closest=None, min_w=0):
        """Track the innermost element whose text matches `text`; optionally climb to a CSS ancestor, or to one at least min_w px wide."""
        js = ("() => { const re = new RegExp(%s); const l = [...document.querySelectorAll(%s)].filter(e => re.test(e.innerText || '') && ![...e.children].some(c => re.test(c.innerText || ''))); let e = l[%d] || null;"
              " if (e && %s) e = e.closest(%s) || e; if (e && %d) { while (e && e.getBoundingClientRect().width < %d) e = e.parentElement; } return e; }"
              % (json.dumps(text), json.dumps(tag), nth, "true" if closest else "false", json.dumps(closest or ""), min_w, min_w))
        self.track(name, js)

    def track_css(self, name, selector, nth=0):
        self.track(name, "() => document.querySelectorAll(%s)[%d] || null" % (json.dumps(selector), nth))

    def harvest(self):
        try: got = self.page.evaluate("() => { const o = {}; for (const n in window.__trk) { o[n] = window.__trk[n].rows; window.__trk[n].rows = []; } return o; }")
        except Exception: return
        for n, rows in got.items():
            if rows: self.tracks.setdefault(n, []).extend(rows)

    # ---- human-like input
    def move(self, x, y, dur=0.7):
        sx, sy = self.mx, self.my; n = max(8, int(dur * 30))
        cx, cy = (sx + x) / 2 + random.uniform(-40, 40), (sy + y) / 2 + random.uniform(-40, 40)
        for i in range(1, n + 1):
            t = i / n; e = t * t * (3 - 2 * t)
            self.page.mouse.move((1-e)**2*sx + 2*(1-e)*e*cx + e*e*x, (1-e)**2*sy + 2*(1-e)*e*cy + e*e*y); self.wait(1000 * dur / n)
        self.mx, self.my = x, y

    def click(self, locator, pause_before=350, pause_after=500, dur=0.7):
        locator.scroll_into_view_if_needed(); locator.wait_for(state="visible"); self.wait(150)
        b = locator.bounding_box(); x, y = b["x"] + b["width"] * random.uniform(.4, .6), b["y"] + b["height"] * random.uniform(.4, .6)
        self.move(x, y, dur); self.wait(pause_before); self.page.mouse.down(); self.wait(70); self.page.mouse.up(); self.wait(pause_after)

    def type(self, locator, text, delay=(45, 100)):
        self.click(locator, pause_after=200)
        for ch in text:
            self.page.keyboard.type(ch); self.wait(random.randint(*delay))
        self.wait(300)

    def scroll(self, dy, dur=1.2):
        n = max(6, int(dur * 25))
        for i in range(n):
            t = (i + 1) / n; e = t * t * (3 - 2 * t); p = (i / n) ** 2 * (3 - 2 * i / n)
            self.page.mouse.wheel(0, dy * (e - p)); self.wait(1000 * dur / n)

    # ---- output
    def __exit__(self, *a):
        self.harvest(); self.browser.close(); self.pw.stop(); self.save()

    def save(self):
        if len(self.frames) < 2: print("no frames"); return
        t0 = self.frames[0][0]; lst = f"{self.dir}/list.txt"
        with open(lst, "w") as f:
            for i, (t, p) in enumerate(self.frames):
                d = (self.frames[i + 1][0] - t) if i + 1 < len(self.frames) else 0.4
                f.write(f"file '{os.path.abspath(p)}'\nduration {max(d, 0.001):.4f}\n")
            f.write(f"file '{os.path.abspath(self.frames[-1][1])}'\n")
        out = f"footage/{self.name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf", f"fps={self.fps},format=yuv420p", "-c:v", "libx264", "-crf", "17", "-preset", "fast", out], check=True)
        os.makedirs("public/tracks", exist_ok=True)
        json.dump({n: [[round(r[0] / 1000 - t0, 3)] + r[1:] for r in rows if r[0] / 1000 >= t0 - 1] for n, rows in self.tracks.items()}, open(f"public/tracks/{self.name}.json", "w"))
        shutil.rmtree(self.dir, ignore_errors=True)
        print("saved", out, round(self.frames[-1][0] - t0, 1), "s,", len(self.frames), "frames")
