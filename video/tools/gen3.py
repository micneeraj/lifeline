"""v3 Lifeline demo: builds index.html, every scene and the captions from one timing table (assets/v3 voice)."""
import json, pathlib, wave, contextlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMP = ROOT / "compositions"
V3 = ROOT / "assets" / "v3"
MK = json.loads((ROOT / "assets" / "rec3" / "marks.json").read_text())
W, H = 1920, 1080
C = dict(bg="#f7f3ec", bg2="#efe8dc", card="#fffdf9", ink="#22313a", muted="#5f6b70", line="#e6ddd0",
         river="#2f6f8f", river_soft="#dcebf2", glow="#4fb3e8", green="#2e7d4f", green_soft="#e2f2e8",
         red="#b4442f", red_soft="#f8e3dd", gold="#e0a84a", deep="#0f2430", deep2="#1d4357")
FONT = "@font-face{font-family:'Fraunces';src:url('assets/fonts/Fraunces.woff2') format('woff2');font-weight:100 900;font-style:normal;}"
LINES = json.loads((V3 / "lines.json").read_text(encoding="utf-8"))


def vdur(k):
    with contextlib.closing(wave.open(str(V3 / f"{k}.wav"))) as wf:
        return wf.getnframes() / wf.getframerate()


# scene id, voice line, lead (s before voice), tail (s after voice)
PLAN = [("flow", "s01", 0.6, 0.5), ("phone", "s02", 0.2, 0.5), ("scams", "s03", 0.3, 0.6), ("pplogo", "s04", 0.5, 0.5),
        ("title", "s05", 0.6, 0.6), ("pipeline", "s06", 0.3, 0.6), ("jess", "s07", 0.3, 0.6), ("marshall", "s08", 0.8, 0.5),
        ("verified", "s09", 0.3, 0.45), ("don1", "s10", 0.3, 0.5), ("don2", "s11", 0.2, 0.5), ("don3", "s12", 0.2, 0.45),
        ("don4", "s13", 2.3, None), ("ppslide", "s14", 0.5, 0.6), ("raleigh", "s15", 0.4, 0.45), ("asheville", "s16", 0.3, 0.45),
        ("gemini", "s17", 0.4, 0.5), ("closing", "s18", 0.3, 0.4)]
FIXED = {"don4": 11.2}
SC, VO, t = [], {}, 0.0
for sid, k, lead, tail in PLAN:
    d = vdur(k)
    L = FIXED.get(sid) or round(lead + d + tail, 2)
    SC.append((sid, round(t, 2), L))
    VO[k] = round(t + lead, 2)
    t += L
SC.append(("endcard", round(t, 2), 2.5))
TOTAL = round(t + 2.5, 2)
LEN = {s: L for s, _, L in SC}


def words(k):
    d = json.loads((V3 / "words" / f"{k}.json").read_text(encoding="utf-8"))
    return d if isinstance(d, list) else d["words"]


def wtime(k, word, nth=0):
    """Local time (from voice start) of the nth occurrence of a word in line k."""
    hits = [w["start"] for w in words(k) if re.sub(r"\W", "", w["text"]).lower() == word.lower()]
    return hits[nth]


def scene(sid, style, body, script, root_bg="transparent", clip=False, outer="", clip_bg=None):
    body = body + outer  # point 1 skipped: recordings keep the full frame
    _n = iter(range(100))
    body = re.sub(r"<video (?![^>]*id=)", lambda m: f'<video id="{sid}-v{next(_n)}" ', body)
    (COMP / f"{sid}.html").write_text(f"""<template>
<style>
{FONT}
#root{{position:absolute;inset:0;overflow:hidden;background:{root_bg};font-family:Inter,sans-serif;color:{C['ink']};}}
#root .wrap{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;transform-origin:0 0;}}
#root .wrap video{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover;}}
#root .page{{position:absolute;left:0;top:0;width:{W}px;transform-origin:0 0;}}
#root .page img{{display:block;width:{W}px;}}
.rclip{{position:absolute;left:0;top:0;width:{W}px;height:907px;overflow:hidden;}}
.rshift{{position:absolute;left:0;top:-86px;width:{W}px;height:{H}px;}}
.mlab.stem:before{{content:"";position:absolute;left:50%;top:100%;width:4px;margin-left:-2px;height:70px;background:#fffdf9;box-shadow:0 2px 6px rgba(0,0,0,.35);}}
.ring{{position:absolute;border-radius:14px;border:4px solid {C['glow']};box-shadow:0 0 0 6px rgba(79,179,232,.22),0 0 28px rgba(79,179,232,.55);opacity:0;}}
.mlab{{position:absolute;left:0;top:0;margin-top:-26px;padding:10px 20px;border-radius:999px;background:#fffdf9;color:{C['ink']};font:700 34px Inter;white-space:nowrap;
  box-shadow:0 10px 30px -8px rgba(0,0,0,.45);transform:translate(-50%,-100%);}}
.mlab:after{{content:"";position:absolute;left:50%;bottom:-10px;margin-left:-10px;border:10px solid transparent;border-bottom:0;border-top-color:#fffdf9;}}
{style}
</style>
<div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
{body}
</div>
<script>
const tl = gsap.timeline({{paused:true}});
{script}
tl.set({{}},{{}},{LEN[sid] - 0.01});
window.__timelines["{sid}"] = tl;
</script>
</template>
""", encoding="utf-8")


def cam(sel, t, cx, cy, s, dur=0.01, ease="sine.inOut", clamp=True):
    """Put content point (cx, cy) at frame centre at scale s (wrapper origin 0 0). Clamp keeps 1920x1080 media edge-free."""
    x, y = W / 2 - cx * s, H / 2 - cy * s
    if clamp:
        x = min(0, max(W - W * s, x))
        y = min(0, max(H - H * s, y))
    return f'tl.to("{sel}",{{x:{x:.1f},y:{y:.1f},scale:{s},duration:{dur},ease:"{ease}"}},{t:.2f});'


def pagecam(sel, t, cx, cy, s, page_h, dur=0.01, ease="sine.inOut"):
    x, y = W / 2 - cx * s, H / 2 - cy * s
    x = min(0, max(W - W * s, x))
    y = min(0, max(H - page_h * s, y))
    return f'tl.to("{sel}",{{x:{x:.1f},y:{y:.1f},scale:{s},duration:{dur},ease:"{ease}"}},{t:.2f});'


def ring(rid, r, pad=8):
    x, y, w, h = r
    return f'<div class="ring" id="{rid}" style="left:{x-pad:.0f}px;top:{y-pad:.0f}px;width:{w+2*pad:.0f}px;height:{h+2*pad:.0f}px"></div>'


def ring_in(rid, t):
    return f'tl.fromTo("#{rid}",{{opacity:0,scale:1.04}},{{opacity:1,scale:1,duration:0.4,ease:"power2.out"}},{t:.2f});'


def fade(sel, t=0, d=0.4):
    return f'tl.fromTo("{sel}",{{opacity:0}},{{opacity:1,duration:{d},ease:"power1.out"}},{t:.2f});'


def voice_at(sid, k):
    """Voice start relative to the scene start."""
    s = dict((a, b) for a, b, _ in SC)[sid]
    return round(VO[k] - s, 2)


# ---------------- 1. Flow opening (flood + rooftop: media 0..6)
L = LEN["flow"]
scene("flow", """.dram{position:absolute;left:64px;top:56px;padding:8px 16px;border-radius:999px;background:rgba(10,20,26,.55);
  color:rgba(255,255,255,.88);font:600 28px Inter;letter-spacing:.14em;text-transform:uppercase;}""",
      f"""<div class="wrap" id="fl-w" style="transform-origin:50% 50%"><video class="clip" src="assets/footage/flow.mp4" data-start="0" data-duration="{L}" data-media-start="0" data-playback-rate="{6.0/L:.3f}" muted playsinline></video></div>
<div class="dram" id="fl-d">Dramatization</div>""",
      'tl.fromTo("#fl-w",{scale:1.0},{scale:1.06,duration:%s,ease:"none"},0);' % L + fade("#fl-d", 0.5, 0.6), root_bg="#0a161e")

# ---------------- 2. Flow phone shot (HELP US / PLEASE DONATE: media 6..10)
L = LEN["phone"]
scene("phone", "", f"""<div class="wrap" id="ph-w" style="transform-origin:58% 45%"><video class="clip" src="assets/footage/flow.mp4" data-start="0" data-duration="{L}" data-media-start="6.0" data-playback-rate="{3.95/L:.3f}" muted playsinline></video></div>""",
      'tl.fromTo("#ph-w",{scale:1.0},{scale:1.08,duration:%s,ease:"none"},0);' % L, root_bg="#0a161e")

# ---------------- 3. Public warnings (as before)
L = LEN["scams"]
WARN = [("North Carolina&rsquo;s Attorney General warns of charity scams after Helene", "NC Department of Justice &middot; Oct 2024"),
        ("U.S. Attorney urges western North Carolina to beware of disaster scams", "U.S. Attorney&rsquo;s Office, W.D.N.C. &middot; Oct 2024"),
        ("FEMA warns survivors and donors about Helene scams", "FEMA &middot; 2024")]
wc = "".join(f"""<div class="sc-card" id="sc-c{i}" style="left:{300+i*70}px;top:{110+i*250}px"><div class="sc-k">Public warning</div>
<div class="sc-h">{h}</div><div class="sc-src">Source: {src}</div></div>""" for i, (h, src) in enumerate(WARN))
ss = fade("#sc-bg", 0, 0.3) + 'tl.fromTo("#sc-lab",{opacity:0,y:-10},{opacity:1,y:0,duration:0.5},0.3);'
for i in range(3):
    t0 = 0.4 + i * 1.4
    ss += f'tl.fromTo("#sc-c{i}",{{x:900,opacity:0,rotation:{3-i*2}}},{{x:0,opacity:1,rotation:{[-1.2,0.8,-0.4][i]},duration:0.75,ease:"power3.out"}},{t0});'
    if i < 2:
        ss += f'tl.to("#sc-c{i}",{{opacity:0.72,duration:0.5}},{t0+1.4});'
ss += f'tl.to("#sc-stack",{{scale:1.03,duration:{L-0.5},ease:"none"}},0.5);'
scene("scams", f"""#sc-bg{{position:absolute;inset:0;background:radial-gradient(1200px 700px at 50% 40%,{C['deep2']},{C['deep']} 72%);}}
#sc-stack{{position:absolute;inset:0;transform-origin:50% 45%;}}
.sc-card{{position:absolute;width:1180px;padding:28px 40px 24px;background:#fbf8f1;border-radius:6px;border-top:6px solid {C['ink']};box-shadow:0 30px 70px -26px rgba(0,0,0,.65);}}
.sc-k{{font:700 28px Inter;letter-spacing:.18em;text-transform:uppercase;color:{C['red']};}}
.sc-h{{font:600 48px/1.12 Fraunces,serif;color:{C['ink']};margin:10px 0 12px;letter-spacing:-.01em;}}
.sc-src{{font:500 28px Inter;color:{C['muted']};border-top:1px solid {C['line']};padding-top:10px;}}
#sc-lab{{position:absolute;right:120px;top:44px;font:600 28px Inter;color:#9fd3ee;letter-spacing:.06em;}}""",
      f'<div id="sc-bg"></div><div id="sc-lab">Real public warnings, paraphrased.</div><div id="sc-stack">{wc}</div>', ss, root_bg=C["deep"])

# ---------------- 4. PayPal logo (official full-colour logo on a light background, clear space kept)
L = LEN["pplogo"]
scene("pplogo", f"""#pp-bg{{position:absolute;inset:0;background:radial-gradient(1100px 650px at 50% 48%,#ffffff,{C['bg']} 75%);}}
#pp-logo{{position:absolute;left:{(W-720)//2}px;top:{(H-203)//2 - 40}px;width:720px;height:203px;}}""",
      '<div id="pp-bg"></div><img id="pp-logo" src="assets/brand/paypal-color.svg" alt="PayPal">',
      fade("#pp-bg", 0, 0.3) + 'tl.fromTo("#pp-logo",{opacity:0,scale:0.9},{opacity:1,scale:1,duration:1.0,ease:"power2.out"},0.15);'
      f'tl.to("#pp-logo",{{scale:1.04,duration:{L-1.15},ease:"none"}},1.15);', root_bg=C["bg"])

# ---------------- 5. Lifeline title (PayPal logo glides up and fades as Lifeline appears)
L = LEN["title"]
scene("title", f"""#ti-bg{{position:absolute;inset:0;background:radial-gradient(1100px 650px at 50% 48%,#ffffff,{C['bg']} 75%);}}
#ti-pp{{position:absolute;left:{(W-720)//2}px;top:{(H-203)//2 - 40}px;width:720px;height:203px;transform-origin:50% 50%;}}
#ti-word{{position:absolute;left:0;width:{W}px;top:300px;text-align:center;font:600 210px/1 Fraunces,serif;color:{C['river']};letter-spacing:-.03em;}}
#ti-wave{{position:absolute;left:560px;top:540px;width:800px;height:70px;overflow:visible;}}
#ti-tag{{position:absolute;left:0;width:{W}px;top:640px;text-align:center;font:500 50px Inter;color:{C['muted']};}}""",
      f"""<div id="ti-bg"></div><img id="ti-pp" src="assets/brand/paypal-color.svg" alt="PayPal">
<div id="ti-word">Lifeline</div>
<svg id="ti-wave" viewBox="0 0 800 70" data-layout-allow-overflow><path id="ti-path" d="M0 35 C 100 0, 200 70, 300 35 S 500 0, 600 35 S 700 70, 800 35" fill="none" stroke="{C['glow']}" stroke-width="5" stroke-linecap="round" stroke-dasharray="900" stroke-dashoffset="900"/></svg>
<div id="ti-tag">Every dollar finds the flood.</div>""",
      'tl.set("#ti-pp",{scale:1.04},0);'
      'tl.to("#ti-pp",{y:-330,scale:0.42,opacity:0,duration:0.9,ease:"power2.inOut"},0.1);'
      'tl.fromTo("#ti-word",{opacity:0,y:30},{opacity:1,y:0,duration:0.9,ease:"power3.out"},0.45);'
      'tl.fromTo("#ti-path",{strokeDashoffset:900},{strokeDashoffset:0,duration:1.6,ease:"power2.inOut"},0.9);'
      'tl.fromTo("#ti-tag",{opacity:0,y:14},{opacity:1,y:0,duration:0.6,ease:"power2.out"},1.3);'
      f'tl.fromTo(["#ti-word","#ti-tag","#ti-wave"],{{scale:1}},{{scale:1.03,duration:{L-1.3},ease:"none",transformOrigin:"50% 50%"}},1.3);',
      root_bg=C["bg"])

# ---------------- 6. 3D six-agent pipeline (timings scaled to the line)
L = LEN["pipeline"]
k = L / 6.8
AG = [("Reader", "Reads the appeal", "ai"), ("Locator", "Census place", "code"), ("Flood Check", "Satellite + FEMA", "code"),
      ("Register Check", "IRS register", "code"), ("Skeptic", "Tries to break it", "code"), ("Judge", "Rules &rarr; verdict", "code")]
cards = "".join(f"""<div class="pc {kd}" id="pc{i}" style="left:{i*256}px"><div class="num">0{i+1}</div><div class="nm">{n}</div><div class="ds">{d}</div><div class="tg">{"AI reads" if kd=="ai" else "Code"}</div></div>""" for i, (n, d, kd) in enumerate(AG))
ps = (fade("#pl-bg", 0, 0.3) + f'tl.fromTo("#pl-row",{{rotationY:-22,rotationX:14,scale:0.96}},{{rotationY:-8,rotationX:8,scale:1.02,duration:{L},ease:"sine.inOut"}},0);'
      f'tl.fromTo("#pl-appeal",{{x:-140,opacity:0}},{{x:0,opacity:1,duration:0.6,ease:"power3.out"}},{0.2});')
for i in range(6):
    ps += f'tl.fromTo("#pc{i}",{{y:90,rotationX:-35,opacity:0}},{{y:0,rotationX:0,opacity:1,duration:0.55,ease:"back.out(1.5)"}},{(0.9+i*0.12)*k:.2f});'
ps += (f'tl.fromTo("#pl-line",{{scaleX:0}},{{scaleX:1,duration:1.1,ease:"power2.inOut"}},{1.0*k:.2f});'
       f'tl.to("#pc0",{{boxShadow:"0 0 0 4px rgba(224,168,74,.55),0 30px 60px -20px rgba(224,168,74,.75)",duration:0.4}},{2.85*k:.2f});'
       f'tl.to(["#pc1","#pc2","#pc3","#pc4","#pc5"],{{opacity:0.45,duration:0.35}},{2.85*k:.2f});')
for i in range(1, 6):
    ps += f'tl.to("#pc{i}",{{opacity:1,boxShadow:"0 0 0 3px rgba(79,179,232,.6),0 26px 50px -22px rgba(47,111,143,.7)",duration:0.3}},{(4.4+(i-1)*0.12)*k:.2f});'
ps += (f'tl.fromTo("#pl-pulse",{{x:0,opacity:0}},{{x:1480,opacity:1,duration:1.4,ease:"power1.inOut"}},{4.4*k:.2f});'
       f'tl.to("#pl-pulse",{{opacity:0,duration:0.2}},{5.9*k:.2f});'
       f'tl.fromTo("#pl-stamp",{{scale:1.6,opacity:0,rotation:-14}},{{scale:1,opacity:1,rotation:-8,duration:0.45,ease:"back.out(2)"}},{5.85*k:.2f});'
       f'tl.fromTo("#pl-sub",{{opacity:0,y:10}},{{opacity:1,y:0,duration:0.5}},{2.8*k:.2f});')
scene("pipeline", f"""#pl-bg{{position:absolute;inset:0;background:radial-gradient(1200px 700px at 50% 30%,{C['river_soft']},{C['bg']} 70%);}}
#pl-stage{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;perspective:1700px;}}
#pl-row{{position:absolute;left:210px;top:380px;width:1516px;height:300px;transform-style:preserve-3d;}}
#pl-line{{position:absolute;left:0;top:140px;width:1516px;height:4px;border-radius:4px;background:linear-gradient(90deg,{C['river']},{C['glow']});box-shadow:0 0 18px {C['glow']};transform-origin:0 50%;}}
#pl-pulse{{position:absolute;left:0;top:130px;width:24px;height:24px;border-radius:50%;background:#fff;box-shadow:0 0 0 6px rgba(79,179,232,.5),0 0 30px {C['glow']};}}
.pc{{position:absolute;top:0;width:230px;height:290px;border-radius:22px;background:{C['card']};border:1px solid {C['line']};padding:22px 20px;box-shadow:0 20px 44px -22px rgba(34,49,58,.4);}}
.pc .num{{font:600 30px Inter;color:{C['muted']};letter-spacing:.08em}}
.pc .nm{{font:600 36px/1.08 Fraunces,serif;margin:10px 0 10px;color:{C['ink']}}}
.pc .ds{{font:500 28px/1.25 Inter;color:{C['muted']};min-height:72px}}
.pc .tg{{display:inline-block;margin-top:14px;padding:6px 14px;border-radius:999px;font:700 28px Inter;}}
.pc.ai .tg{{background:#fbf0d4;color:#8a5b0c;border:1px solid {C['gold']}}}
.pc.code .tg{{background:{C['river_soft']};color:{C['river']};border:1px solid rgba(47,111,143,.35)}}
#pl-appeal{{position:absolute;left:210px;top:140px;width:900px;padding:22px 28px;border-radius:20px;background:{C['card']};border:1px solid {C['line']};box-shadow:0 20px 44px -24px rgba(34,49,58,.4);font:500 28px/1.4 Inter;color:{C['ink']}}}
#pl-appeal b{{display:block;font:600 28px Inter;letter-spacing:.12em;color:{C['muted']};text-transform:uppercase;margin-bottom:6px}}
#pl-stamp{{position:absolute;left:1560px;top:230px;padding:12px 22px;border:4px solid {C['green']};border-radius:14px;color:{C['green']};font:700 34px Fraunces,serif;letter-spacing:.04em;background:rgba(226,242,232,.9)}}
#pl-sub{{position:absolute;left:1180px;top:150px;width:560px;font:600 40px/1.2 Fraunces,serif;color:{C['river']};text-align:right}}""",
      f"""<div id="pl-bg"></div>
<div id="pl-appeal"><b>Any appeal</b>&ldquo;Marshall, North Carolina&hellip; Families need diapers, generators and fuel.&rdquo;</div>
<div id="pl-sub">The AI only reads.<br>Code decides.</div>
<div id="pl-stage" data-layout-allow-overflow><div id="pl-row"><div id="pl-line"></div><div id="pl-pulse"></div>{cards}</div></div>
<div id="pl-stamp">VERDICT</div>""", ps, root_bg=C["bg"])

# ---------------- 7. Jess's post
L = LEN["jess"]
scene("jess", f"""#js-bg{{position:absolute;inset:0;background:radial-gradient(1100px 700px at 50% 40%,{C['river_soft']},{C['bg']} 72%);}}
#js-card{{position:absolute;left:310px;top:260px;width:1300px;padding:46px 56px;border-radius:30px;background:{C['card']};border:1px solid {C['line']};box-shadow:0 40px 90px -40px rgba(34,49,58,.45);transform-origin:50% 50%}}
#js-who{{display:flex;align-items:center;gap:22px;font:600 34px Inter;color:{C['ink']}}}
#js-av{{width:80px;height:80px;border-radius:50%;background:linear-gradient(140deg,{C['river_soft']},#fff);border:2px solid {C['line']};display:grid;place-items:center;font:700 36px Inter;color:{C['river']}}}
#js-who span{{display:block;font:500 28px Inter;color:{C['muted']};margin-top:4px}}
#js-txt{{font:500 48px/1.4 Inter;color:{C['ink']};margin-top:30px}}
#js-tag{{position:absolute;left:310px;top:170px;padding:10px 20px;border-radius:999px;background:{C['card']};border:1px solid {C['line']};font:600 28px Inter;color:{C['muted']}}}""",
      """<div id="js-bg"></div><div id="js-tag">Test appeal from our evaluation set &middot; synthetic account, real place</div>
<div id="js-card"><div id="js-who"><div id="js-av">J</div><div>@madisoncounty_jess<span>2024-09-29 &middot; Marshall, North Carolina</span></div></div>
<div id="js-txt">Marshall, North Carolina. The French Broad came right through downtown on Sept 27, 2024. Families need diapers, generators and fuel. Anything helps.</div></div>""",
      fade("#js-bg", 0, 0.3) + 'tl.fromTo("#js-card",{y:60,opacity:0,scale:.97},{y:0,opacity:1,scale:1,duration:0.8,ease:"power3.out"},0.1);'
      'tl.fromTo("#js-tag",{opacity:0,y:-10},{opacity:1,y:0,duration:0.5},0.4);'
      f'tl.to("#js-card",{{scale:1.04,duration:{L-0.9},ease:"none"}},0.9);', root_bg=C["bg"])


# ---------------- 8. Marshall on the 3D map (map already framed on the town; the map itself pushes in)
def track_js(lab, samples, media_start, scene_len, dy=-30):
    pts = [(round(tt - media_start, 2), x, y + dy) for tt, x, y in samples if 0 <= tt - media_start <= scene_len + 0.2]
    js = f'tl.set("#{lab}",{{x:{pts[0][1]},y:{pts[0][2]}}},0);'
    for (t0, _, _), (t1, x1, y1) in zip(pts, pts[1:]):
        js += f'tl.to("#{lab}",{{x:{x1},y:{y1},duration:{max(0.01, t1-t0):.2f},ease:"none"}},{t0:.2f});'
    return js


L = LEN["marshall"]
MS = 0.3
scene("marshall", f"""#ms-leg{{position:absolute;left:32px;top:32px;padding:12px 20px;border-radius:14px;background:rgba(255,253,249,.92);font:600 28px Inter;color:{C['ink']};box-shadow:0 10px 30px -12px rgba(0,0,0,.35)}}
#ms-leg i{{display:inline-block;width:34px;height:14px;border-radius:7px;background:#5aaee0;margin-right:12px;vertical-align:middle}}""",
      f"""<div class="wrap" id="ms-w" style="transform-origin:50% 40%"><video class="clip" src="assets/rec3/marshall.mp4" data-start="0" data-duration="{L}" data-media-start="{MS}" muted playsinline></video></div>
<div class="mlab stem" id="ms-lab">Marshall, NC</div>""",
      track_js("ms-lab", MK["marshall_track"], MS, L, dy=-96) + fade("#ms-lab", 0.0, 0.3) + fade("#ms-leg", 0.3, 0.4), root_bg=C["bg"],
      clip=True, outer='<div id="ms-leg"><i></i>Satellite-observed flood water</div>')

# ---------------- 9. VERIFIED card, then "What Lifeline verifies" (one smooth scroll on a 1.5x page still)
L = LEN["verified"]
PV = MK["page_verified"]
ph = PV["height"]
vtop, ttop = PV["verdict"][1], PV["trust"][1] + PV["trust"][3]
mid = (vtop + ttop) / 2
s0 = 1.26
vs = (pagecam("#vf-p", 0, 960, vtop - 260, s0, ph) + fade("#vf-p", 0, 0.3) +
      pagecam("#vf-p", 0.4, 960, mid, s0, ph, 4.2, "power2.inOut") +
      pagecam("#vf-p", 4.6, 960, mid + 20, 1.34, ph, L - 4.6, "none"))
scene("verified", "", f'<div class="page" id="vf-p"><img src="assets/rec3/page_verified.png"></div>', vs, root_bg=C["bg"], clip=True)

# ---------------- 10-13. Donate (real sandbox payment). Media times found from the recording itself.
D = MK["donate"]
ex = lambda r, pad=0: r
L1, L2, L3, L4 = LEN["don1"], LEN["don2"], LEN["don3"], LEN["don4"]
M1 = 2.0
scene("don1", "", f"""<div class="wrap" id="d1-w"><video class="clip" src="assets/rec3/donate.mp4" data-start="0" data-duration="{L1}" data-media-start="{M1}" muted playsinline></video>{ring("d1-r1", D["pp1"])}</div>""",
      cam("#d1-w", 0, 952, 520, 1.28) + cam("#d1-w", 0.01, 952, 530, 1.28, L1, "none") +
      ring_in("d1-r1", voice_at("don1", "s10") + wtime("s10", "PayPal")), root_bg=C["bg"], clip=True)
M2 = M1 + L1
t2a = voice_at("don2", "s11")
scene("don2", "", f"""<div class="wrap" id="d2-w"><video class="clip" src="assets/rec3/donate.mp4" data-start="0" data-duration="{L2}" data-media-start="{M2:.2f}" muted playsinline></video>
{ring("d2-r1", D["pp1"])}{ring("d2-r2", D["pp2"])}{ring("d2-r3", D["pp3"])}{ring("d2-r4", D["slots"])}</div>""",
      cam("#d2-w", 0, 952, 530, 1.28) + cam("#d2-w", 0.01, 952, 545, 1.28, L2, "none") + 'tl.set("#d2-r1",{opacity:1},0);' +
      ring_in("d2-r2", t2a + wtime("s11", "captured") - 0.2) + ring_in("d2-r3", t2a + wtime("s11", "split") - 0.1) +
      ring_in("d2-r4", t2a + wtime("s11", "three")) +
      "", root_bg=C["bg"], clip=True)
M3 = M2 + L2
em = D["earmark"]
scene("don3", "", f"""<div class="wrap" id="d3-w"><video class="clip" src="assets/rec3/donate.mp4" data-start="0" data-duration="{L3}" data-media-start="{M3:.2f}" muted playsinline></video></div>""",
      cam("#d3-w", 0, 952, 545, 1.28) + cam("#d3-w", 0.01, 952, 600, 1.28, L3, "none"), root_bg=C["bg"], clip=True)
# don4: glide onto PayPal Donate (28.7-30.1), click (33.4-34.0; identical static frames between), receipt + coin split
# (54.7-59.7), app scroll to the receipt (59.7-62.3), then the final frame (statuses SUCCESS) as a still with a push-in.
segs = [(28.7 + (L3 - 13.43 if False else 0), 1.4), (33.4, 0.55), (54.7, 5.0), (59.7, 2.6)]
segs[0] = (M3 + L3, 1.4)
vids, t0 = "", 0.0
starts = []
for i, (ms, dd) in enumerate(segs):
    vids += f'<div class="wrap" id="d4-w{i}"><video class="clip" src="assets/rec3/donate.mp4" data-start="{t0:.2f}" data-duration="{dd}" data-media-start="{ms:.2f}" muted playsinline></video></div>'
    starts.append(t0)
    t0 += dd
fin = t0
d4 = (cam("#d4-w0", 0, 952, 600, 1.28) + cam("#d4-w1", 0, 952, 600, 1.28) +
      'tl.set(["#d4-w2","#d4-w3"],{x:-258.6,y:-390.8,scale:1.28},0);' +
      f'tl.fromTo("#d4-w2",{{y:-410.8}},{{y:-370.8,duration:{segs[2][1]},ease:"none"}},{starts[2]:.2f});' +
      f'tl.fromTo("#d4-fin",{{opacity:0}},{{opacity:1,duration:0.45,ease:"power1.inOut"}},{fin:.2f});' +
      f'tl.set("#d4-fin",{{x:{960-952*1.2:.1f},y:{905-990*1.2:.1f},scale:1.2}},{fin:.2f});' +
      f'tl.to("#d4-fin",{{x:{960-952*1.25:.1f},y:{905-990*1.25:.1f},scale:1.25,duration:{L4-fin:.2f},ease:"none"}},{fin+0.01:.2f});')
scene("don4", "", vids + f'<div class="wrap" id="d4-fin" style="opacity:0"><img src="assets/rec3/donate_final.png" style="position:absolute;left:0;top:0;width:{W}px;height:{H}px"></div>',
      d4, root_bg="#f3f0e9", clip=True)

# ---------------- 14. PayPal slide
L = LEN["ppslide"]
v14 = voice_at("ppslide", "s14")
scene("ppslide", f"""#ps-bg{{position:absolute;inset:0;background:radial-gradient(1200px 720px at 50% 42%,{C['deep2']},{C['deep']} 72%);}}
#ps-box{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;transform-origin:50% 42%;}}
#ps-plate{{position:absolute;left:{(W-420)//2}px;top:90px;width:420px;height:150px;border-radius:24px;background:#fff;display:grid;place-items:center;box-shadow:0 24px 60px -24px rgba(0,0,0,.7)}}
#ps-plate img{{width:300px;height:85px}}
#ps-h{{position:absolute;left:0;width:{W}px;top:300px;text-align:center;font:700 96px Fraunces,serif;color:#fffaf1;letter-spacing:-.01em}}
#ps-row{{position:absolute;left:0;width:{W}px;top:480px;display:flex;justify-content:center;align-items:center;gap:26px}}
.ps-st{{padding:26px 40px;border-radius:22px;background:#fffdf9;color:{C['ink']};font:700 54px Inter;box-shadow:0 20px 50px -20px rgba(0,0,0,.7)}}
.ps-st.cap{{background:{C['green']};color:#fff}}
.ps-ar{{color:#9fd3ee;font:700 60px Inter}}
#ps-or{{position:absolute;left:{(W-760)//2}px;width:760px;top:680px;text-align:center;padding:22px 0;border-radius:22px;border:3px solid #f0a08e;color:#ffd9cf;font:700 50px Inter}}""",
      """<div id="ps-bg"></div><div id="ps-box"><div id="ps-plate"><img src="assets/brand/paypal-color.svg" alt="PayPal"></div>
<div id="ps-h">Only possible with PayPal</div>
<div id="ps-row"><span class="ps-st" id="ps-a">Authorize</span><span class="ps-ar" id="ps-r1">&rarr;</span><span class="ps-st" id="ps-v">Verify</span><span class="ps-ar" id="ps-r2">&rarr;</span><span class="ps-st cap" id="ps-c">Capture &amp; split</span></div>
<div id="ps-or">or Void: never charged</div></div>""",
      fade("#ps-bg", 0, 0.3) + 'tl.fromTo("#ps-plate",{opacity:0,y:-16},{opacity:1,y:0,duration:0.6,ease:"power2.out"},0.15);'
      'tl.fromTo("#ps-h",{opacity:0,y:20},{opacity:1,y:0,duration:0.7,ease:"power3.out"},0.35);'
      f'tl.fromTo("#ps-a",{{opacity:0,y:24}},{{opacity:1,y:0,duration:0.45,ease:"power3.out"}},{v14 + wtime("s14", "authorize") - 0.1:.2f});'
      f'tl.fromTo(["#ps-r1","#ps-v"],{{opacity:0,y:24}},{{opacity:1,y:0,duration:0.45,stagger:0.1,ease:"power3.out"}},{v14 + wtime("s14", "capture") - 0.6:.2f});'
      f'tl.fromTo(["#ps-r2","#ps-c"],{{opacity:0,y:24}},{{opacity:1,y:0,duration:0.45,stagger:0.1,ease:"power3.out"}},{v14 + wtime("s14", "capture") - 0.1:.2f});'
      f'tl.fromTo("#ps-or",{{opacity:0,scale:1.15}},{{opacity:1,scale:1,duration:0.45,ease:"back.out(2)"}},{v14 + wtime("s14", "void") - 0.1:.2f});'
      f'tl.fromTo("#ps-box",{{scale:1}},{{scale:1.06,duration:{L},ease:"none"}},0);', root_bg=C["deep"])

# ---------------- 15. Raleigh: pin far from the flood water, then the NOT VERIFIED card
L = LEN["raleigh"]
RS, RM = 0.3, 6.2
PR = MK["page_raleigh"]
cr = MK["raleigh_crop"]
fx, fy = [(MK["raleigh_proj"][0][0] - cr[0]) * W / cr[2], (MK["raleigh_proj"][0][1] - cr[1]) * H / cr[3]]
rv = PR["verdict"]
scene("raleigh", f"""#ra-flood{{position:absolute;left:430px;top:400px;}}
#ra-flood .mlab{{background:#e3f1fa;color:{C['river']}}} #ra-flood .mlab:after{{border-top-color:#e3f1fa}}
#ra-lab{{}} #ra-lab.mlab{{color:{C['red']}}}""",
      f"""<div class="wrap" id="ra-m" style="transform-origin:50% 50%"><video class="clip" src="assets/rec3/raleigh_map.mp4" data-start="0" data-duration="{RM}" data-media-start="{RS}" muted playsinline></video></div>
<div id="ra-ov"><div id="ra-flood"><div class="mlab">Helene flood area</div></div><div class="mlab" id="ra-lab">Raleigh</div></div>
<div class="page" id="ra-p" style="opacity:0"><img src="assets/rec3/page_raleigh.png"></div>""",
      track_js("ra-lab", MK["raleigh_track"], RS, RM) + fade("#ra-lab", 0.2, 0.3) + fade("#ra-flood", 0.9, 0.4) +
      f'tl.to("#ra-ov",{{opacity:0,duration:0.3}},{RM - 0.4});' +
      pagecam("#ra-p", RM - 0.4, 960, rv[1] + rv[3] / 2, 1.22, PR["height"]) +
      f'tl.to("#ra-p",{{opacity:1,duration:0.4,ease:"power1.inOut"}},{RM - 0.4});' +
      pagecam("#ra-p", RM, 960, rv[1] + rv[3] / 2 - 10, 1.3, PR["height"], L - RM, "none"), root_bg=C["bg"], clip=True)

# ---------------- 16. Asheville attack: hidden instruction highlighted, smooth move to the verdict, Donate safely instead
L = LEN["asheville"]
PA = MK["page_asheville"]
av, ab = PA["verdict"], PA["btn"]
hl = "".join(f'<div class="as-hl" style="left:{x-4:.0f}px;top:{y-2:.0f}px;width:{w+8:.0f}px;height:{h+6:.0f}px"></div>' for x, y, w, h in MK["ash_lines"])
v16 = voice_at("asheville", "s16")
tmove = v16 + wtime("s16", "Lifeline") - 1.4
scene("asheville", f""".as-hl{{position:absolute;border-radius:6px;background:rgba(180,68,47,.18);border-bottom:4px solid {C['red']};transform-origin:0 50%;}}""",
      f"""<div class="page" id="as-p"><img src="assets/rec3/page_asheville.png">{hl}{ring("as-r", ab, 10)}</div>""",
      pagecam("#as-p", 0, 960, 330, 1.26, PA["height"]) + fade("#as-p", 0, 0.3) +
      pagecam("#as-p", 0.01, 960, 300, 1.3, PA["height"], tmove, "none") +
      f'tl.fromTo(".as-hl",{{scaleX:0,opacity:0}},{{scaleX:1,opacity:1,duration:0.5,stagger:0.3,ease:"power2.out"}},{v16 + wtime("s16", "hides") - 0.2:.2f});' +
      pagecam("#as-p", tmove, 960, av[1] + av[3] / 2 - 20, 1.3, PA["height"], 2.6, "power2.inOut") +
      ring_in("as-r", v16 + wtime("s16", "points") - 0.2) +
      pagecam("#as-p", tmove + 2.6, 960, av[1] + av[3] / 2, 1.34, PA["height"], L - tmove - 2.6, "none"), root_bg=C["bg"], clip=True)

# ---------------- 17. Gemini alone vs Lifeline
L = LEN["gemini"]
v17 = voice_at("gemini", "s17")
tg = v17 + wtime("s17", "Gemini") - 0.2
tl_ = v17 + wtime("s17", "Lifeline") - 0.2


def lit(rid, t):
    return (f'tl.to("#{rid}",{{opacity:1,duration:0.35,ease:"power1.out"}},{t:.2f});'
            f'tl.fromTo("#{rid}",{{backgroundColor:"rgba(79,179,232,0)",boxShadow:"0 0 0 0 rgba(79,179,232,0)"}},'
            f'{{backgroundColor:"rgba(79,179,232,.22)",boxShadow:"0 0 34px 0 rgba(79,179,232,.45)",duration:0.35,ease:"power1.out"}},{t:.2f});'
            f'tl.to("#{rid}",{{backgroundColor:"rgba(79,179,232,.06)",boxShadow:"0 0 0 0 rgba(79,179,232,0)",duration:1.2,ease:"power1.inOut"}},{t+1.4:.2f});')


f0 = v17 + wtime("s17", "funded", 0)
gs = (lit("gm-l1r", tg) + lit("gm-l2r", f0 - 0.1) + lit("gm-l3r", f0 + 1.3) +
      lit("gm-r1r", tl_) + lit("gm-r2r", v17 + wtime("s17", "funded", 1) - 0.1) + lit("gm-r3r", v17 + wtime("s17", "sent") - 0.1) +
      f'tl.fromTo("#gm-box",{{scale:1}},{{scale:1.035,duration:{L},ease:"none"}},0);')
row = lambda rid, lab, val, vid: f'<div class="gm-row" id="{rid}"><span>{lab}</span><b id="{vid}">{val}</b></div>'
scene("gemini", f"""#gm-bg{{position:absolute;inset:0;background:radial-gradient(1300px 760px at 50% 40%,{C['deep2']},{C['deep']} 74%);}}
#gm-box{{position:absolute;inset:0;transform-origin:50% 45%;}}
#gm-h{{position:absolute;left:0;width:{W}px;top:64px;text-align:center;font:600 60px Fraunces,serif;color:#f7f3ec}}
.gm-col{{position:absolute;top:175px;width:780px;height:600px;padding:36px 40px;border-radius:28px}}
#gm-l{{left:150px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14)}}
#gm-r{{left:990px;background:rgba(79,179,232,.10);border:2px solid rgba(79,179,232,.55);box-shadow:0 0 60px -20px rgba(79,179,232,.6)}}
.gm-t{{font:700 50px Fraunces,serif;color:#fffaf1;padding:0 8px}} .gm-s{{font:500 28px Inter;color:#b9c7cf;margin:8px 0 22px;padding:0 8px}}
.gm-row{{display:flex;justify-content:space-between;align-items:baseline;padding:20px 8px;border-top:1px solid rgba(255,255,255,.14);border-radius:14px;font:500 32px Inter;color:#d9e3e8;opacity:.38}}
.gm-row b{{font:700 64px Fraunces,serif;color:#fffaf1;font-variant-numeric:tabular-nums}}
#gm-r .gm-row b{{color:#bfe6ff}} #gm-r3 {{color:#7fe0a5 !important}}
#gm-note{{position:absolute;left:0;width:{W}px;top:800px;text-align:center;font:500 30px Inter;color:#9fb3bd}}""",
      f"""<div id="gm-bg"></div><div id="gm-box"><div id="gm-h">Same 40 appeals, answers locked first</div>
<div class="gm-col" id="gm-l"><div class="gm-t">Gemini alone</div><div class="gm-s">same appeal, no tools or rules</div>
{row("gm-l1r", "Correct verdicts", "10 of 40", "gm-l1")}{row("gm-l2r", "Genuine appeals funded", "1 of 15", "gm-l2")}{row("gm-l3r", "Sent to unverified appeals", "$100", "gm-l3")}</div>
<div class="gm-col" id="gm-r"><div class="gm-t">Lifeline</div><div class="gm-s">six agents, code decides</div>
{row("gm-r1r", "Correct verdicts", "38 of 40", "gm-r1")}{row("gm-r2r", "Genuine appeals funded", "13 of 15", "gm-r2")}{row("gm-r3r", "Sent to unverified appeals", "$0", "gm-r3")}</div>
<div id="gm-note">40 test appeals, answers locked before any run.</div></div>""", gs, root_bg=C["deep"])


# ---------------- 18. Closing: Flow drone (<= 6 s, slow push-in), then the live app's hero map
L = LEN["closing"]
DR = 6.0
scene("closing", "", f"""<div class="wrap" id="cl-w" style="transform-origin:50% 50%"><video class="clip" src="assets/footage/flow.mp4" data-start="0" data-duration="{DR}" data-media-start="0" data-playback-rate="0.5" muted playsinline></video></div>
<div id="cl-hc" style="position:absolute;inset:0;opacity:0;background:{C['bg']}"><div class="rclip" style="background:{C['bg']}"><div class="rshift"><div class="wrap" id="cl-h" style="transform-origin:50% 50%"><video class="clip" src="assets/rec/hero.mp4" data-start="{DR-0.5}" data-duration="{L-DR+0.5:.2f}" data-media-start="1.0" muted playsinline></video></div></div></div></div>""",
      'tl.fromTo("#cl-w",{scale:1.0},{scale:1.1,duration:%s,ease:"none"},0);' % DR + fade("#cl-w", 0, 0.6) +
      f'tl.to("#cl-hc",{{opacity:1,duration:0.5,ease:"power1.inOut"}},{DR-0.5});tl.fromTo("#cl-h",{{scale:1.0}},{{scale:1.05,duration:{L-DR+0.5:.2f},ease:"none"}},{DR-0.5});',
      root_bg="#0a161e")

# ---------------- 19. End card (music tail only)
scene("endcard", f"""#ec-bg{{position:absolute;inset:0;background:radial-gradient(1100px 600px at 50% 35%,{C['river_soft']},{C['bg']} 70%);}}
#ec-word{{position:absolute;left:0;width:{W}px;top:200px;text-align:center;font:600 170px/1 Fraunces,serif;color:{C['river']};letter-spacing:-.03em}}
#ec-tag{{position:absolute;left:0;width:{W}px;top:420px;text-align:center;font:500 44px Inter;color:{C['muted']}}}
.ec-ln{{position:absolute;left:0;width:{W}px;text-align:center;font:500 34px Inter;color:{C['ink']}}} .ec-ln b{{font-weight:700}}
#ec-links{{position:absolute;left:0;width:{W}px;top:760px;display:flex;justify-content:center;gap:28px}}
.ec-pill{{padding:16px 28px;border-radius:999px;background:{C['card']};border:1px solid {C['line']};font:600 32px Inter;color:{C['river']};box-shadow:0 14px 30px -18px rgba(34,49,58,.4)}}
.ec-pill span{{color:{C['muted']};font-weight:500;margin-right:12px}}""",
      """<div id="ec-bg"></div><div id="ec-word">Lifeline</div><div id="ec-tag">Every dollar finds the flood.</div>
<div class="ec-ln" style="top:560px">Built with <b>PayPal</b>, <b>Gemini</b> and <b>Render</b></div>
<div class="ec-ln" style="top:620px">Built with <b>Cursor</b> and <b>Claude Code</b></div>
<div id="ec-links"><div class="ec-pill"><span>Live</span>lifeline-3fug.onrender.com</div><div class="ec-pill"><span>Code</span>github.com/micneeraj/lifeline</div></div>""",
      fade("#ec-bg", 0, 0.3) + 'tl.fromTo(["#ec-word","#ec-tag",".ec-ln","#ec-links"],{opacity:0,y:14},{opacity:1,y:0,duration:0.35,stagger:0.05,ease:"power2.out"},0.0);',
      root_bg=C["bg"])

# ---------------- Captions: one full sentence at a time, plain white text with a soft shadow, no strip
CAPTEXT = {  # display text per sentence (numbers as digits where spoken as words)
    "s17": ["We locked the answers before running anything.",
            "On 40 test appeals, Gemini alone, asked whether to release the money, funded just one genuine appeal out of fifteen.",
            "Lifeline got 38 of 40 right, funded 13 of 15, and sent $0 to unverified appeals."],
}


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]


caps = []
for sid, k, _, _ in PLAN:
    ss_ = sentences(LINES[k])
    disp = CAPTEXT.get(k, ss_)
    ws = words(k)
    n = len(ws)
    counts = [len(s.split()) for s in ss_]
    tot = sum(counts)
    i0 = 0
    for j, (s, cnt) in enumerate(zip(ss_, counts)):
        i1 = n if j == len(ss_) - 1 else max(i0 + 1, round(sum(counts[:j + 1]) / tot * n))
        caps.append([disp[j], ws[i0]["start"] + VO[k], ws[i1 - 1]["end"] + VO[k]])
        i0 = i1
caps.sort(key=lambda c: c[1])
for j in range(len(caps)):
    nxt = caps[j + 1][1] if j + 1 < len(caps) else 999
    caps[j][1] = round(caps[j][1] - 0.08, 2)
    caps[j][2] = round(min(nxt - 0.12, caps[j][2] + 0.45), 2)


def wrap2(t):
    if len(t) <= 56:
        return t
    best = min((abs(len(t[:m]) - len(t[m + 1:])), m) for m in range(len(t)) if t[m] == " ")[1]
    return t[:best] + "<br>" + t[best + 1:]


DARK = {"flow", "phone", "scams", "ppslide", "gemini"}
LIGHT = [(s0, s0 + L0) for sid, s0, L0 in SC if sid not in DARK and sid != "closing"]
_cs = dict((a, b) for a, b, _ in SC)["closing"]
LIGHT.append((_cs + DR - 0.5, _cs + LEN["closing"]))
lightcue = lambda s, e: any(s < b and e > a for a, b in LIGHT)
cls = lambda t, s, e: " ".join(c for c in (("sm" if len(t) > 120 else ""), ("")) if c)
cap_html = "".join(f'<div class="cg" id="cg{j}"><span{(' class=' + cls(t, s, e)) if cls(t, s, e) else ""}>{wrap2(t)}</span></div>' for j, (t, s, e) in enumerate(caps))
cap_js = "".join(f'tl.set("#cg{j}",{{visibility:"visible"}},{s});tl.fromTo("#cg{j} span",{{opacity:0}},{{opacity:1,duration:0.18,ease:"none"}},{s});'
                 f'tl.to("#cg{j} span",{{opacity:0,duration:0.15,ease:"none"}},{round(e-0.15,2)});tl.set("#cg{j}",{{visibility:"hidden"}},{e});'
                 for j, (t, s, e) in enumerate(caps))
SH = "0 0 2px rgba(0,0,0,.95),0 0 4px rgba(0,0,0,.8),0 2px 10px rgba(0,0,0,.75),0 0 24px rgba(0,0,0,.45)"
(COMP / "captions.html").write_text(f"""<template>
<style>
#root{{position:absolute;inset:0;pointer-events:none;}}
#root .cg{{position:absolute;left:0;width:{W}px;bottom:58px;display:flex;justify-content:center;visibility:hidden;}}
#root .cg span{{display:inline-block;max-width:1680px;color:#ffffff;font:600 42px/1.28 Inter,sans-serif;text-align:center;text-shadow:{SH};-webkit-text-stroke:3px rgba(8,16,22,.7);paint-order:stroke fill;}}
#root .cg span.sm{{font-size:38px;}}
</style>
<div id="root" data-composition-id="captions" data-width="{W}" data-height="{H}" data-layout-allow-caption-zone>
{cap_html}
</div>
<script>
const tl = gsap.timeline({{paused:true}});
{cap_js}
tl.set({{}},{{}},{TOTAL - 0.05});
window.__timelines["captions"] = tl;
</script>
</template>
""", encoding="utf-8")

# ---------------- Root
voice_html, segs_ = "", []
for k, o in VO.items():
    d = vdur(k)
    segs_.append((o, o + d))
    voice_html += f'<audio id="vo{k}" class="clip" src="assets/v3/{k}.wav" data-start="{o}" data-duration="{d:.3f}" data-volume="1" data-track-index="20"></audio>\n'
LOW, HIGH = 0.13, 0.30
pts = [{"t": 0, "v": 0.0}, {"t": 1.0, "v": HIGH}]
for a, b in segs_:
    pts += [{"t": round(max(0, a - 0.45), 2), "v": HIGH}, {"t": round(a - 0.05, 2), "v": LOW},
            {"t": round(b + 0.15, 2), "v": LOW}, {"t": round(b + 0.6, 2), "v": HIGH}]
pts += [{"t": round(TOTAL - 2.6, 2), "v": 0.34}, {"t": round(TOTAL - 0.05, 2), "v": 0.0}]
pts = sorted({p["t"]: p for p in pts}.values(), key=lambda p: p["t"])
auto = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": pts}]})
hosts = "".join(f'<div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" data-start="{s}" data-duration="{L}" '
                f'data-track-index="{i % 2 + 1}" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="z-index:{i+1}"></div>\n'
                for i, (sid, s, L) in enumerate(SC))
(ROOT / "index.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ margin:0; width:{W}px; height:{H}px; overflow:hidden; background:{C['deep']}; }}
#bgfill {{ position:absolute; inset:0; background:{C['deep']}; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
<div id="bgfill"></div>
{hosts}<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-track-kind="captions" data-width="{W}" data-height="{H}" style="z-index:50"></div>
{voice_html}<audio id="bgm" class="clip" src="assets/bgm/track3.wav" data-start="0" data-duration="{TOTAL}" data-volume="1" data-track-index="21" data-automation='{auto}'></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = gsap.timeline({{ paused: true }});
</script>
</body>
</html>
""", encoding="utf-8")
json.dump({"scenes": SC, "voice": VO, "total": TOTAL, "caps": caps}, open(ROOT / "tools" / "timing3.json", "w"), indent=1)
print("total", TOTAL, "captions", len(caps))
for s in SC:
    print(" ", s)
