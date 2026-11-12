"""Take the README / Devpost screenshots (1800x1200 PNG) of a running Lifeline.

  python scripts/screenshots.py https://lifeline-3fug.onrender.com docs/screenshots

Against a sample-mode server it presses the SAMPLE MODE donate button. Against the live site it uses the real
PayPal sandbox button through video/tools/record.py:paypal_approve, with the sandbox buyer login read from .env
(never printed, never captured: the PayPal popup is not screenshotted).
"""
import sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video" / "tools"))
W, H = 1800, 1200
SHOTS = ["01-appeals", "02-proof", "03-marshall-check", "04-marshall-verified", "05-raleigh-not-verified",
         "06-asheville-injection-check", "07-asheville-not-verified", "08-donate-followup", "09-donate-receipt",
         "10-reviewer-queue", "11-check-with-lifeline"]


def main(base, out_dir, only=None):
    base = base.rstrip("/")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    want = set(only.split(",")) if only else set(SHOTS)

    def snap(pg, name):
        if name in want:
            pg.mouse.move(W - 5, H - 5)
            pg.wait_for_timeout(400)
            pg.screenshot(path=str(out / f"{name}.png"))
            print("shot", name, (out / f"{name}.png").stat().st_size // 1024, "KB", flush=True)

    def scroll_to(pg, sel, off=90):
        pg.evaluate("([s,o])=>{const e=document.querySelector(s); scrollTo(0, Math.max(0, e.getBoundingClientRect().top+scrollY-o));}",
                    [sel, off])
        pg.wait_for_timeout(700)

    def open_check(pg, q, settle_ms=4500):
        pg.goto(f"{base}/{q}", wait_until="domcontentloaded")
        pg.wait_for_selector("#verdict .verdict", timeout=180000)
        pg.wait_for_timeout(settle_ms)

    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=False,
                              args=["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--window-position=0,0"])
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, color_scheme="light",
                            reduced_motion="no-preference")
        pg = ctx.new_page()
        # wake the free server first
        for _ in range(40):
            try:
                if pg.goto(f"{base}/api/health", timeout=60000).ok:
                    break
            except Exception:
                time.sleep(3)

        pg.goto(f"{base}/", wait_until="domcontentloaded")
        pg.wait_for_selector("#feed .post", timeout=180000)
        pg.wait_for_timeout(9000)                       # hero 3D map starts after ~5 s idle
        snap(pg, "01-appeals")

        pg.goto(f"{base}/#proof", wait_until="domcontentloaded")
        pg.wait_for_selector("#proofBody table", timeout=120000)
        pg.wait_for_timeout(3500)
        snap(pg, "02-proof")

        open_check(pg, "?appeal=in-02#check", 6500)      # trail expanded (judge link)
        pg.evaluate("scrollTo(0,0)")
        snap(pg, "03-marshall-check")

        open_check(pg, "?appeal=in-02", 2500)            # donor-first, trail collapsed
        scroll_to(pg, "#appealCard", 80)
        snap(pg, "04-marshall-verified")

        open_check(pg, "?appeal=out-01", 2500)
        scroll_to(pg, "#appealCard", 80)
        snap(pg, "05-raleigh-not-verified")

        open_check(pg, "?appeal=rt-01#check", 6500)
        pg.evaluate("scrollTo(0,0)")
        snap(pg, "06-asheville-injection-check")

        open_check(pg, "?appeal=rt-01", 2500)
        scroll_to(pg, "#appealCard", 80)
        snap(pg, "07-asheville-not-verified")

        if want & {"08-donate-followup", "09-donate-receipt"}:
            open_check(pg, "?appeal=in-02", 2000)
            pg.locator("#verdict a.btn").first.click()
            pg.wait_for_timeout(2500)
            pg.locator("#earmark summary").click()
            pg.locator("#emFamily").fill("Miller")
            pg.locator("#emNote").fill("For the Miller family in Marshall. They lost their home in the flood.")
            pg.locator("#emNote").dispatch_event("input")
            pg.locator("#emLink").fill("https://x.com/madisoncounty_jess/status/1234567890123456789")
            pg.locator("#emLink").dispatch_event("blur")
            pg.evaluate("scrollTo(0,0)")
            pg.wait_for_timeout(2500)
            snap(pg, "08-donate-followup")
            if pg.locator("#sampleDonate").is_visible():
                pg.locator("#sampleDonate").click()
            else:
                import record as R
                creds = R.env(ROOT / ".env")
                assert creds.get("PAYPAL_SANDBOX_BUYER_EMAIL") and creds.get("PAYPAL_SANDBOX_BUYER_PASSWORD"), \
                    "PayPal sandbox buyer login missing from .env"
                R.paypal_approve(pg, creds)
            pg.wait_for_selector("#receipt .verdict", timeout=180000)
            pg.wait_for_timeout(9000)                   # coin animation + live payout status polling
            scroll_to(pg, "#receipt .proofline", 700)
            snap(pg, "09-donate-receipt")

        pg.goto(f"{base}/review", wait_until="domcontentloaded")
        pg.wait_for_selector("#queue article", timeout=180000)
        pg.wait_for_timeout(1500)
        snap(pg, "10-reviewer-queue")

        pg.goto(f"{base}/", wait_until="domcontentloaded")
        pg.wait_for_selector("#feed .post", timeout=180000)
        pg.wait_for_timeout(2500)
        scroll_to(pg, "#pasteGo", 260)
        snap(pg, "11-check-with-lifeline")
        b.close()


if __name__ == "__main__":
    main(*sys.argv[1:])
