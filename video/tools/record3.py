"""v3 recordings of the live Lifeline site at 1920x1080 CSS viewport, 1.5x device pixels (2880x1620 frames)
so the edit can push in without going soft. Map shots are cropped to the map element at native resolution.
The MapLibre map is reached through an init-script hook on window.maplibregl (recording browser only; the app
is unchanged). PayPal sandbox buyer credentials stay inside record.paypal_approve and the popup is never captured.
Usage: python record3.py marshall verified donate raleigh asheville
"""
import base64, json, pathlib, subprocess, sys, time
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import record as R

SITE = R.SITE
ROOT = R.ROOT
OUT = ROOT / "assets" / "rec3"
OUT.mkdir(parents=True, exist_ok=True)
import os
DSF = float(os.environ.get("DSF", "1.5"))
FW, FH = int(1920 * DSF), int(1080 * DSF)

HOOK_JS = r"""
(() => { if (window.top !== window) return; let v;
  Object.defineProperty(window, 'maplibregl', { configurable: true, get() { return v; }, set(x) {
    if (x && x.Map && !x.__hooked) { const O = x.Map; x.Map = class extends O { constructor(o) { super(o); (window.__maps = window.__maps || []).push(this); } }; x.__hooked = 1; }
    v = x; } });
})();
"""

IDLE_JS = """() => new Promise(ok => { const m = (window.__maps||[]).filter(x => x.getContainer().id === 'map').pop();
  if (!m) return ok('nomap'); const done = () => ok('idle');
  m.once('idle', done); m.triggerRepaint(); setTimeout(() => ok('timeout'), 8000); })"""


class Rec3(R.Rec):
    def __init__(self, page, name, crop=None):
        super().__init__(page, name, FW, FH)
        self.crop = crop  # css px (x, y, w, h)

    def start(self):
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": int(os.environ.get("Q", "80")), "maxWidth": FW, "maxHeight": FH, "everyNthFrame": 1})
        self.t0 = time.time()
        return self

    def stop(self):
        self.page.wait_for_timeout(300)
        self.cdp.send("Page.stopScreencast")
        end_ts = self.frames[-1][1] + 0.5
        lst = self.dir / "list.txt"
        with lst.open("w") as f:
            for k, (n, ts) in enumerate(self.frames):
                nxt = self.frames[k + 1][1] if k + 1 < len(self.frames) else end_ts
                f.write(f"file '{n}'\nduration {max(0.001, nxt - ts):.4f}\n")
            f.write(f"file '{self.frames[-1][0]}'\n")
        if self.crop:
            x, y, w, h = [round(v * DSF) for v in self.crop]
            vf = f"scale={FW}:{FH},crop={w}:{h}:{x}:{y},scale=1920:1080:flags=lanczos,fps=30,format=yuv420p"
        else:
            vf = f"scale={FW}:{FH}:flags=lanczos,fps=30,format=yuv420p"
        out = OUT / f"{self.name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", vf,
                        "-c:v", "libx264", "-preset", "slow", "-crf", "15", str(out)], check=True, cwd=self.dir)
        dur = self.frames[-1][1] - self.frames[0][1]
        print(f"  {self.name}: {len(self.frames)} frames / {dur:.1f}s ({len(self.frames)/max(dur,.1):.0f} fps)", flush=True)
        return out


def rect(pg, sel):
    return pg.eval_on_selector(sel, "e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }")


def map_crop(pg):
    x, y, w, h = rect(pg, "#map")
    ch = min(h, w * 9 / 16)
    cw = ch * 16 / 9
    return (x + (w - cw) / 2, y + (h - ch) / 2, cw, ch)


def ease(pg, opts):
    pg.evaluate("o => { const m = window.__maps.filter(x => x.getContainer().id==='map').pop(); m.easeTo(o); }", opts)


def jump_and_settle(pg, opts):
    pg.evaluate("o => { const m = window.__maps.filter(x => x.getContainer().id==='map').pop(); m.stop(); m.jumpTo(o); }", opts)
    pg.wait_for_timeout(500)
    print("   map:", pg.evaluate(IDLE_JS), flush=True)
    pg.wait_for_timeout(2500)   # idle + 2 s (plus margin) before recording
    print("   map:", pg.evaluate(IDLE_JS), flush=True)


def open_check(pg, aid):
    pg.goto(SITE + f"?appeal={aid}#check", wait_until="domcontentloaded", timeout=120000)
    pg.wait_for_selector("#verdict .verdict", timeout=120000)
    pg.wait_for_timeout(5500)  # pipeline + flyTo/fitBounds finish
    pg.evaluate(IDLE_JS)
    pg.evaluate("scrollTo(0,0)")
    pg.mouse.move(300, 1000)


PIN_JS = "() => { const r = document.querySelector('#map .pin').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; }"


def track(pg, r, crop, ms):
    """Wait ms while sampling the pin position in cropped-frame (1920x1080) coordinates."""
    out, end = [], time.time() + ms / 1000
    while time.time() < end:
        x, y = pg.evaluate(PIN_JS)
        out.append([round(time.time() - r.t0, 3), round((x - crop[0]) * 1920 / crop[2], 1), round((y - crop[1]) * 1080 / crop[3], 1)])
        pg.wait_for_timeout(100)
    return out


def main(which):
    creds = R.env(ROOT.parent / "lifeline" / ".env")
    assert creds.get("PAYPAL_SANDBOX_BUYER_EMAIL") and creds.get("PAYPAL_SANDBOX_BUYER_PASSWORD")
    args = ["--disable-renderer-backgrounding", "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
            "--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--window-position=0,0"]
    marks = json.loads((OUT / "marks.json").read_text()) if (OUT / "marks.json").exists() else {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=False, args=args)
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=DSF)
        ctx.add_init_script(HOOK_JS)
        ctx.add_init_script(R.CURSOR_JS)
        pg = ctx.new_page()
        print("warming up", flush=True)
        pg.goto(SITE + "?appeal=in-02#check", wait_until="domcontentloaded", timeout=180000)
        pg.wait_for_selector("#verdict .verdict", timeout=180000)
        print("  gl:", pg.evaluate("(()=>{const g=document.createElement('canvas').getContext('webgl2');const d=g&&g.getExtension('WEBGL_debug_renderer_info');return d?g.getParameter(d.UNMASKED_RENDERER_WEBGL):'?'})()"), flush=True)

        if "marshall" in which:
            open_check(pg, "in-02")
            loc = pg.evaluate("() => { const m = window.__maps.filter(x => x.getContainer().id==='map').pop(); const mk = document.querySelector('#map .pin'); return mk ? null : null; }")
            # Marshall from the Census geocoder, as the Locator step shows: (35.7986, -82.6800)
            c = [-82.6800, 35.7986]
            jump_and_settle(pg, {"center": c, "zoom": 12.2, "pitch": 55, "bearing": -20})
            crop = map_crop(pg)
            r = Rec3(pg, "marshall", crop).start()
            pg.wait_for_timeout(600)
            ease(pg, {"center": c, "zoom": 13.0, "pitch": 60, "bearing": -26, "duration": 13000})
            marks["marshall_track"] = track(pg, r, crop, 13600)
            r.stop()
            marks["marshall_crop"] = crop
            # where the pin sits in the cropped frame (1920x1080 units) at the start
            px = pg.evaluate("() => { const r = document.querySelector('#map .pin').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; }")
            marks["marshall_pin_end"] = [(px[0] - crop[0]) * 1920 / crop[2], (px[1] - crop[1]) * 1080 / crop[3]]

        if "verified" in which:
            open_check(pg, "in-02")
            pg.wait_for_timeout(1500)
            r = Rec3(pg, "verified").start()
            pg.wait_for_timeout(1200)
            R.scroll(pg, R.top_of(pg, "#verdict", 110), 4200)
            pg.wait_for_timeout(9000)
            r.stop()
            marks["verified_verdict"] = rect(pg, "#verdict .verdict")
            marks["verified_trust"] = rect(pg, "#trustCheck")

        if "donate" in which:
            dm = {}
            open_check(pg, "in-02")
            R.scroll(pg, R.top_of(pg, "#verdict", 110), 10)
            pg.wait_for_timeout(800)
            pg.locator("#verdict a.btn").click()
            pg.wait_for_timeout(2500)
            pg.evaluate("scrollTo(0,0)")
            pg.mouse.move(1500, 900)
            pg.wait_for_timeout(1000)
            r = Rec3(pg, "donate").start()
            pg.wait_for_timeout(1500)
            amt = pg.locator('#amounts button[data-a="25"]').bounding_box()
            R.glide(pg, amt["x"] + amt["width"] / 2, amt["y"] + amt["height"] / 2, 1200)
            pg.wait_for_timeout(300)
            pg.locator('#amounts button[data-a="25"]').click()
            dm["amount_click"] = time.time() - r.t0
            dm["pp1"], dm["pp2"], dm["pp3"], dm["slots"] = rect(pg, "#pp1"), rect(pg, "#pp2"), rect(pg, "#pp3"), rect(pg, "#slots")
            dm["amounts"], dm["ppflow"] = rect(pg, "#amounts"), rect(pg, "#ppflow")
            pg.wait_for_timeout(9000)
            sm = pg.locator("#earmark summary").bounding_box()
            R.glide(pg, sm["x"] + 120, sm["y"] + sm["height"] / 2, 1000)
            pg.wait_for_timeout(200)
            dm["earmark_open"] = time.time() - r.t0
            pg.locator("#earmark summary").click()
            pg.wait_for_timeout(900)
            for sel, txt in (("#emFamily", "Miller"),
                             ("#emNote", "For the Miller family on Main Street, Marshall. They lost their home."),
                             ("#emLink", "https://x.com/madisoncounty_jess/status/1234567890123456789")):
                fb = pg.locator(sel).bounding_box()
                R.glide(pg, fb["x"] + 60, fb["y"] + fb["height"] / 2, 600)
                pg.locator(sel).click()
                if sel == "#emLink":
                    pg.locator(sel).fill(txt)
                    pg.locator(sel).dispatch_event("paste")
                else:
                    pg.locator(sel).press_sequentially(txt, delay=35)
                pg.wait_for_timeout(400)
            dm["type_end"] = time.time() - r.t0
            dm["earmark"] = rect(pg, "#earmark")
            pg.wait_for_timeout(1500)
            dm["popup_start"] = time.time() - r.t0
            R.paypal_approve(pg, creds)
            dm["popup_end"] = time.time() - r.t0
            pg.mouse.move(1700, 300, steps=10)
            pg.wait_for_selector("#receipt .verdict", timeout=120000)
            dm["receipt"] = time.time() - r.t0
            pg.wait_for_timeout(4500)   # coin split into the three charity cards
            dm["split_done"] = time.time() - r.t0
            R.scroll(pg, R.top_of(pg, "#receipt", 30), 2600)
            dm["receipt_scrolled"] = time.time() - r.t0
            final = {"SUCCESS", "FAILED", "RETURNED", "REVERSED", "BLOCKED", "REFUNDED", "DENIED", "UNCLAIMED"}
            st = []
            for _ in range(120):
                st = pg.eval_on_selector_all("#receipt td.pst", "ts => ts.map(t => t.firstChild.textContent.trim())")
                if st and all(x in final for x in st):
                    break
                pg.wait_for_timeout(1000)
            dm["statuses"] = st
            dm["final"] = time.time() - r.t0
            pg.wait_for_timeout(6000)
            r.stop()
            dm["receipt_rect"] = rect(pg, "#receipt")
            dm["stage"] = pg.inner_text("#stageState")
            dm["receipt_text"] = pg.inner_text("#receipt")[:1500]
            marks["donate"] = dm
            print("  donate:", dm["stage"], st, flush=True)

        if "raleigh" in which:
            open_check(pg, "out-01")
            print("  verdict:", pg.inner_text("#verdict .verdict")[:200].replace("\n", " | "), flush=True)
            # pin at Raleigh, framed so the western NC flood area is in the same view
            ll = pg.evaluate("() => { const m = window.__maps.filter(x => x.getContainer().id==='map').pop(); const c = m.getCenter(); return [c.lng, c.lat]; }")
            marks["raleigh_center"] = ll
            jump_and_settle(pg, {"center": [-80.35, 35.6], "zoom": 6.75, "pitch": 30, "bearing": 0})
            crop = map_crop(pg)
            r = Rec3(pg, "raleigh_map", crop).start()
            pg.wait_for_timeout(500)
            ease(pg, {"center": [-80.35, 35.6], "zoom": 6.95, "pitch": 34, "bearing": 0, "duration": 7000})
            marks["raleigh_track"] = track(pg, r, crop, 7400)
            r.stop()
            marks["raleigh_crop"] = crop
            marks["raleigh_pin"] = pg.evaluate("() => { const r = document.querySelector('#map .pin').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; }")
            marks["raleigh_proj"] = pg.evaluate("""() => { const m = window.__maps.filter(x => x.getContainer().id==='map').pop(); const b = m.getContainer().getBoundingClientRect();
                return [[-82.55,35.60]].map(p => { const q = m.project(p); return [q.x + b.x, q.y + b.y]; }); }""")
            pg.wait_for_timeout(500)
            r = Rec3(pg, "raleigh_card").start()
            pg.wait_for_timeout(800)
            R.scroll(pg, R.top_of(pg, "#verdict", 110), 3200)
            pg.wait_for_timeout(7000)
            r.stop()
            marks["raleigh_verdict"] = rect(pg, "#verdict .verdict")

        if "asheville" in which:
            open_check(pg, "rt-01")
            print("  verdict:", pg.inner_text("#verdict .verdict")[:200].replace("\n", " | "), flush=True)
            pg.wait_for_timeout(1000)
            marks["ash_text"] = pg.evaluate("""() => { const el = [...document.querySelectorAll('#s-check *')].find(e => e.children.length===0 && /SYSTEM|ignore|Assistant|verdict/i.test(e.textContent));
                if (!el) return null; const t = el.textContent; return {text: t, rect: (r => [r.x, r.y, r.width, r.height])(el.getBoundingClientRect())}; }""")
            marks["ash_lines"] = pg.evaluate("""() => { const el = [...document.querySelectorAll('#s-check *')].find(e => e.children.length===0 && /SYSTEM|ignore|Assistant|verdict/i.test(e.textContent));
                if (!el) return []; const t = el.firstChild, s = t.textContent; const m = s.search(/(SYSTEM|ignore|Assistant)/i); if (m < 0) return [];
                const rg = document.createRange(); rg.setStart(t, m); rg.setEnd(t, s.length); return [...rg.getClientRects()].map(r => [r.x, r.y, r.width, r.height]); }""")
            r = Rec3(pg, "asheville").start()
            pg.wait_for_timeout(5000)
            R.scroll(pg, R.top_of(pg, "#verdict", 110), 3200)
            pg.wait_for_timeout(1500)
            bb = pg.locator("#verdict a.btn").bounding_box()
            R.glide(pg, bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, 1400)
            pg.wait_for_timeout(5000)
            r.stop()
            marks["ash_verdict"] = rect(pg, "#verdict .verdict")
            marks["ash_btn"] = rect(pg, "#verdict a.btn")
            marks["ash_btn_text"] = pg.inner_text("#verdict a.btn")

        if "shots" in which:   # full-page stills at 1.5x for smooth edit-side pans (static pages only)
            for aid, name in (("in-02", "verified"), ("out-01", "raleigh"), ("rt-01", "asheville")):
                open_check(pg, aid)
                pg.mouse.move(5, 1075)
                pg.evaluate("document.getElementById('__cur') && (document.getElementById('__cur').style.display='none')")
                pg.wait_for_timeout(1500)
                pg.screenshot(path=str(OUT / f"page_{name}.png"), full_page=True)
                sels = {"verdict": "#verdict .verdict", "trust": "#trustCheck", "btn": "#verdict a.btn", "map": "#map",
                        "appeal": "#s-check .card, #s-check article"}
                marks[f"page_{name}"] = {k: pg.evaluate("s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x, r.y + scrollY, r.width, r.height]; }", v) for k, v in sels.items()}
                marks[f"page_{name}"]["height"] = pg.evaluate("document.documentElement.scrollHeight")
                pg.evaluate("document.getElementById('__cur') && (document.getElementById('__cur').style.display='')")
        (OUT / "marks.json").write_text(json.dumps(marks, indent=1))
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:] or ["marshall", "verified", "raleigh", "asheville", "donate"])
