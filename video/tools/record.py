"""Record the live Lifeline site for the demo video.

Captures Chrome's own compositor frames over CDP (Page.startScreencast) at the page's 1920x1080 viewport,
so the 1280x800 desktop does not limit the capture. Each scene becomes assets/rec/<name>.mp4 (30 fps CFR).
PayPal sandbox buyer credentials come from lifeline/.env and are never printed or recorded: the PayPal
login runs in a separate popup window, and only the main page is captured.
"""
import base64, os, subprocess, sys, time, json, pathlib
from playwright.sync_api import sync_playwright

SITE = "https://lifeline-3fug.onrender.com/"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "rec"
TMP = ROOT / "tools" / "frames"
OUT.mkdir(parents=True, exist_ok=True)


def env(path):
    vals = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


CURSOR_JS = r"""
(() => {
  if (window.top !== window) return;  // no second cursor inside the PayPal iframe
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id='__cur';
    c.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2l14 9-6.2 1.3L15 20l-3 1.4-3.3-7.6L4 18z" fill="#fff" stroke="#22313a" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    Object.assign(c.style,{position:'fixed',left:'0',top:'0',zIndex:2147483647,pointerEvents:'none',
      transform:'translate(-200px,-200px)',filter:'drop-shadow(0 3px 6px rgba(0,0,0,.35))',transition:'none'});
    const ring = document.createElement('div'); ring.id='__ring';
    Object.assign(ring.style,{position:'fixed',left:'0',top:'0',width:'44px',height:'44px',marginLeft:'-22px',marginTop:'-22px',
      borderRadius:'50%',border:'3px solid rgba(79,179,232,.9)',zIndex:2147483646,pointerEvents:'none',opacity:'0',transform:'scale(.4)'});
    document.documentElement.appendChild(ring); document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX-6}px,${e.clientY-3}px)`; }, true);
    addEventListener('mousedown', e => { ring.style.left=e.clientX+'px'; ring.style.top=e.clientY+'px';
      ring.animate([{opacity:1,transform:'scale(.4)'},{opacity:0,transform:'scale(1.4)'}],{duration:520,easing:'ease-out'}); }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk); else mk();
})();
"""

SCROLL_JS = """([y, ms]) => new Promise(ok => { const s = scrollY, d = y - s, t0 = performance.now();
  const ease = t => t<.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2;
  const f = t => { const k = Math.min(1,(t-t0)/ms); scrollTo(0, s + d*ease(k)); k<1 ? requestAnimationFrame(f) : ok(); };
  requestAnimationFrame(f); })"""


class Rec:
    """CDP screencast -> JPEG frames with timestamps -> CFR mp4."""
    def __init__(self, page, name, w, h):
        self.page, self.name, self.w, self.h = page, name, w, h
        self.cdp = page.context.new_cdp_session(page)
        self.dir = TMP / name
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in self.dir.glob("*.jpg"):
            f.unlink()
        self.frames = []
        self.cdp.on("Page.screencastFrame", self._frame)

    def _frame(self, ev):
        i = len(self.frames)
        p = self.dir / f"{i:06d}.jpg"
        p.write_bytes(base64.b64decode(ev["data"]))
        self.frames.append((p.name, ev["metadata"]["timestamp"]))
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception:
            pass

    def start(self):
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 95, "maxWidth": self.w,
                                               "maxHeight": self.h, "everyNthFrame": 1})
        self.t0 = time.time()
        return self

    def stop(self):
        self.page.wait_for_timeout(300)
        self.cdp.send("Page.stopScreencast")
        end_ts = self.frames[-1][1] + 0.5 if self.frames else 0
        lst = self.dir / "list.txt"
        with lst.open("w") as f:
            for k, (n, ts) in enumerate(self.frames):
                nxt = self.frames[k + 1][1] if k + 1 < len(self.frames) else end_ts
                f.write(f"file '{n}'\nduration {max(0.001, nxt - ts):.4f}\n")
            if self.frames:
                f.write(f"file '{self.frames[-1][0]}'\n")
        out = OUT / f"{self.name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-vf", f"scale={self.w}:{self.h}:flags=lanczos,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "16", str(out)], check=True, cwd=self.dir)
        dur = self.frames[-1][1] - self.frames[0][1] if self.frames else 0
        print(f"  {self.name}: {len(self.frames)} frames over {dur:.1f}s -> {out.name}", flush=True)
        return out


def glide(page, x, y, ms=900):
    page.mouse.move(x, y, steps=max(8, ms // 16))


def scroll(page, y, ms=1600):
    page.evaluate(SCROLL_JS, [y, ms])


def top_of(page, sel, off=90):
    return page.eval_on_selector(sel, f"e => e.getBoundingClientRect().top + scrollY - {off}")


def paypal_approve(page, creds):
    """Click the real PayPal button and approve in the sandbox popup. Credentials never leave this function."""
    btn = page.frame_locator("#paypal-buttons iframe").first.locator('[data-funding-source="paypal"]')
    btn.wait_for(timeout=60000)
    box = page.locator("#paypal-buttons iframe").first.bounding_box()
    glide(page, box["x"] + box["width"] / 2, box["y"] + 24, 900)
    page.wait_for_timeout(300)
    with page.context.expect_page(timeout=60000) as pop_info:
        btn.click()
    pop = pop_info.value
    pop.wait_for_load_state("domcontentloaded")
    email, pw = creds["PAYPAL_SANDBOX_BUYER_EMAIL"], creds["PAYPAL_SANDBOX_BUYER_PASSWORD"]
    deadline = time.time() + 240
    stage = "email"
    while not pop.is_closed() and time.time() < deadline:
        try:
            for sel in ("#acceptAllButton", "button#acceptAllButton"):
                if pop.locator(sel).is_visible():
                    pop.locator(sel).click()
            if stage == "email" and pop.locator("#email").is_visible():
                pop.locator("#email").fill(email)
                if pop.locator("#btnNext").is_visible():
                    pop.locator("#btnNext").click()
                stage = "password"
                pop.wait_for_timeout(1500)
                continue
            if pop.locator("#password").is_visible():
                pop.locator("#password").fill(pw)
                pop.locator("#btnLogin").click()
                stage = "review"
                pop.wait_for_timeout(3000)
                continue
            for sel in ("#payment-submit-btn", "[data-testid='submit-button-initial']", "button:has-text('Complete Purchase')",
                        "button:has-text('Continue to Review Order')", "button:has-text('Pay Now')", "button:has-text('Continue')",
                        "button:has-text('Agree & Continue')", "button:has-text('Donate')"):
                loc = pop.locator(sel).first
                if loc.is_visible() and loc.is_enabled():
                    loc.click()
                    pop.wait_for_timeout(2500)
                    break
        except Exception:
            pass
        if not pop.is_closed():
            pop.wait_for_timeout(700)
    if not pop.is_closed():
        raise SystemExit("PayPal popup did not complete in time")
    page.bring_to_front()


def main(which):
    creds = env(ROOT.parent / "lifeline" / ".env")
    assert creds.get("PAYPAL_SANDBOX_BUYER_EMAIL") and creds.get("PAYPAL_SANDBOX_BUYER_PASSWORD"), "buyer creds missing"
    args = ["--disable-renderer-backgrounding", "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows", "--ignore-gpu-blocklist", "--enable-gpu-rasterization",
            "--window-position=0,0", "--force-device-scale-factor=1"]
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=False, args=args)
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        ctx.add_init_script(CURSOR_JS)
        pg = ctx.new_page()

        print("warming up", flush=True)
        pg.goto(SITE + "?appeal=in-02#check", wait_until="domcontentloaded", timeout=120000)
        pg.wait_for_selector("#verdict .verdict", timeout=120000)
        print("  gl:", pg.evaluate("(()=>{const g=document.createElement('canvas').getContext('webgl2');const d=g&&g.getExtension('WEBGL_debug_renderer_info');return d?g.getParameter(d.UNMASKED_RENDERER_WEBGL):'?'})()"), flush=True)

        if "hero" in which:
            pg.goto(SITE, wait_until="domcontentloaded")
            pg.wait_for_selector("#feed article")
            pg.mouse.move(1500, 900)
            pg.wait_for_selector("#heroMap.live", timeout=90000)
            pg.wait_for_timeout(4000)
            r = Rec(pg, "hero", 1920, 1080).start()
            pg.wait_for_timeout(9000)
            glide(pg, 980, 640, 1800)
            pg.wait_for_timeout(1500)
            scroll(pg, 560, 2600)
            pg.wait_for_timeout(1200)
            scroll(pg, 1350, 3200)
            pg.wait_for_timeout(2500)
            r.stop()

        if "marshall" in which or "donate" in which:
            marks = {}
            pg.goto("about:blank")
            r = Rec(pg, "marshall", 1920, 1080).start()
            pg.goto(SITE + "?appeal=in-02#check", wait_until="domcontentloaded")
            marks["loaded"] = time.time() - r.t0
            pg.wait_for_selector("#verdict .verdict", timeout=120000)
            marks["verdict"] = time.time() - r.t0
            glide(pg, 1100, 520, 1500)
            pg.wait_for_timeout(7000)
            scroll(pg, top_of(pg, "#verdict"), 3000)
            pg.wait_for_timeout(5500)
            marks["trust_scroll"] = time.time() - r.t0
            scroll(pg, top_of(pg, "#trustCheck", 140), 2000)
            pg.wait_for_timeout(5500)
            scroll(pg, top_of(pg, "#verdict"), 1500)
            pg.wait_for_timeout(2000)
            r.stop()
            json.dump(marks, open(OUT / "marshall.json", "w"), indent=1)

            # Donate: real sandbox payment with a charity follow-up request
            dm = {}
            r = Rec(pg, "donate", 1920, 1080).start()
            a = pg.locator("#verdict a.btn")
            bb = a.bounding_box()
            glide(pg, bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, 900)
            pg.wait_for_timeout(250)
            a.click()
            pg.wait_for_timeout(1800)
            amt = pg.locator('#amounts button[data-a="25"]').bounding_box()
            glide(pg, amt["x"] + amt["width"] / 2, amt["y"] + amt["height"] / 2, 900)
            pg.locator('#amounts button[data-a="25"]').click()
            pg.wait_for_timeout(700)
            sm = pg.locator("#earmark summary").bounding_box()
            glide(pg, sm["x"] + 120, sm["y"] + sm["height"] / 2, 800)
            pg.locator("#earmark summary").click()
            pg.wait_for_timeout(700)
            dm["type_start"] = time.time() - r.t0
            for sel, txt in (("#emFamily", "Miller"),
                             ("#emNote", "For the Miller family on Main Street, Marshall. They lost their home."),
                             ("#emLink", "https://x.com/madisoncounty_jess/status/1234567890123456789")):
                fb = pg.locator(sel).bounding_box()
                glide(pg, fb["x"] + 60, fb["y"] + fb["height"] / 2, 500)
                pg.locator(sel).click()
                if sel == "#emLink":  # pasted in one go, like a real user
                    pg.locator(sel).fill(txt)
                    pg.locator(sel).dispatch_event("paste")
                else:
                    pg.locator(sel).press_sequentially(txt, delay=28)
                pg.wait_for_timeout(300)
            dm["type_end"] = time.time() - r.t0
            pg.wait_for_timeout(600)
            scroll(pg, top_of(pg, "#paypal-buttons", 420), 900)
            pg.wait_for_timeout(1000)
            dm["popup_start"] = time.time() - r.t0
            paypal_approve(pg, creds)
            dm["popup_end"] = time.time() - r.t0
            pg.wait_for_selector("#receipt .verdict", timeout=120000)
            dm["receipt"] = time.time() - r.t0
            pg.mouse.move(1500, 300, steps=20)
            scroll(pg, top_of(pg, "#ppflow", 300), 1200)
            pg.wait_for_timeout(4000)
            scroll(pg, top_of(pg, "#receipt table", 300), 1200)
            final = {"SUCCESS", "FAILED", "RETURNED", "REVERSED", "BLOCKED", "REFUNDED", "DENIED", "UNCLAIMED"}
            for _ in range(70):
                st = pg.eval_on_selector_all("#receipt td.pst", "ts => ts.map(t => t.firstChild.textContent.trim())")
                if st and all(x in final for x in st):
                    break
                pg.wait_for_timeout(1000)
            dm["statuses"] = st
            dm["final"] = time.time() - r.t0
            pg.wait_for_timeout(3000)
            scroll(pg, top_of(pg, "#ppflow", 300), 1000)
            pg.wait_for_timeout(3000)
            dm["final_flow"] = time.time() - r.t0
            dm["receipt_scroll"] = time.time() - r.t0
            scroll(pg, top_of(pg, "#receipt", 40), 2400)
            pg.wait_for_timeout(5000)
            dm["proof_scroll"] = time.time() - r.t0
            scroll(pg, top_of(pg, "#receipt .proofline", 640), 2200)
            pg.wait_for_timeout(5000)
            r.stop()
            dm.update(stage=pg.inner_text("#stageState"), hits=pg.evaluate("document.querySelectorAll('.slot.hit').length"),
                      receipt=pg.inner_text("#receipt")[:1200])
            json.dump(dm, open(OUT / "donate.json", "w"), indent=1)
            print("  donate:", dm["stage"], "| slots hit:", dm["hits"], flush=True)

        if "asheville" in which:
            pg.goto("about:blank")
            r = Rec(pg, "asheville", 1920, 1080).start()
            pg.goto(SITE + "?appeal=rt-01#check", wait_until="domcontentloaded")
            pg.wait_for_selector("#verdict .verdict", timeout=120000)
            glide(pg, 1050, 470, 1500)
            pg.wait_for_timeout(7000)
            scroll(pg, top_of(pg, "#verdict"), 3000)
            pg.wait_for_timeout(1000)
            bb = pg.locator("#verdict a.btn").bounding_box()
            glide(pg, bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, 1400)
            pg.wait_for_timeout(5500)
            r.stop()

        if "proof" in which:
            pg.goto("about:blank")
            r = Rec(pg, "proof", 1920, 1080).start()
            pg.goto(SITE + "#proof", wait_until="domcontentloaded")
            pg.wait_for_selector("#proofBody .bars", timeout=60000)
            glide(pg, 700, 440, 1500)
            pg.wait_for_timeout(3500)
            scroll(pg, 380, 2600)
            pg.wait_for_timeout(5000)
            r.stop()

        if "phone" in which:
            m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            mp = m.new_page()
            mp.goto(SITE, wait_until="domcontentloaded")
            mp.wait_for_selector("#feed article")
            mp.evaluate("scrollTo(0,1)")
            mp.wait_for_selector("#heroMap.live", timeout=90000)
            mp.evaluate("scrollTo(0,0)")
            mp.wait_for_timeout(3000)
            r = Rec(mp, "phone", 780, 1688).start()
            mp.wait_for_timeout(2500)
            scroll(mp, 760, 3000)
            mp.wait_for_timeout(1200)
            scroll(mp, 2300, 5000)
            mp.wait_for_timeout(1500)
            r.stop()
            m.close()
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:] or ["hero", "marshall", "asheville", "proof", "phone"])
