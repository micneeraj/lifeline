# Lifeline — *Every dollar finds the flood.*

**Try it offline in one command** (no keys, recorded LLM responses, stubbed PayPal):

```bash
git clone https://github.com/micneeraj/lifeline.git && cd lifeline && python run.py --sample
```

**Live:** https://lifeline-3fug.onrender.com (free hosting: the first load may take ~30 s while it wakes up).

**Demo video:** https://youtu.be/Bz9w2556f6I (2:43)

> Lifeline doesn't ask donors to trust an AI's opinion. It uses AI to gather evidence, deterministic rules to decide, and PayPal to make sure money can only move to registered local relief charities after the evidence passes.

## Judge walkthrough (90 seconds)

1. **A prompt-injection appeal is refused.** Open the Asheville appeal that hides a "system note" to the checker: <https://lifeline-3fug.onrender.com/?appeal=rt-01#check>. It comes back NOT VERIFIED (`PROMPT_INJECTION`); if you donate, the PayPal authorization is voided and you are never charged.
2. **A genuine appeal is verified.** Open Marshall: <https://lifeline-3fug.onrender.com/?appeal=in-02#check>. See VERIFIED, "Flood evidence: Strong (0.24 km to observed flood water, 0.71 km² flooded within 1.8 km)", the full evidence trail with the satellite flood map, and the panel "What Lifeline verifies, and what it doesn't". The donor's view of the same check, with the trail collapsed: <https://lifeline-3fug.onrender.com/?appeal=in-02>.
3. **Donate in the sandbox.** Press "Donate to screened local charities" and pay with a PayPal sandbox buyer account (or press the sample button when the server runs in sample mode). See Authorized → Checks passed → Captured and split by Payouts, the 3-way split, the hashed receipt and **Paid to the person who posted: $0**.
4. **See what a human reviews.** Open the demo reviewer queue: <https://lifeline-3fug.onrender.com/review>. No money moves from that page.

## One appeal, followed through

Take one test appeal from the set, modelled on a real place: "Jess" posts from Marshall, North Carolina two days after the French Broad came through town (appeal `in-02`, @madisoncounty_jess, a synthetic account). People who see a post like this want to help. Lifeline checks the place, the date and the satellite flood map, finds three registered local charities, and makes sure the money reaches Marshall through them, never through the PayPal of the person who posted.

**Problem:** after every disaster, social media fills with "our town is flooded, please send money" appeals. Donors can't tell which are real, and money sent straight to the person who posted can vanish.

**Lifeline** checks every appeal against real satellite flood maps. PayPal then pays **only registered, eligibility-screened local charities** in the flooded area, never the person who posted it.

![Homepage with the 3D Helene flood flyover](docs/screenshots/01-appeals.png)

| Marshall check, full evidence trail expanded | Marshall VERIFIED, donor-first, with the flood evidence label |
|---|---|
| ![Marshall check](docs/screenshots/03-marshall-check.png) | ![Marshall verified](docs/screenshots/04-marshall-verified.png) |
| **Raleigh: not in the declaration or the flood area** | **Asheville appeal with a hidden "system note"** |
| ![Raleigh not verified](docs/screenshots/05-raleigh-not-verified.png) | ![Asheville check](docs/screenshots/06-asheville-injection-check.png) |
| **Verdict: prompt injection refused** | **Donate with a request for charity follow-up** |
| ![Asheville not verified](docs/screenshots/07-asheville-not-verified.png) | ![Donate](docs/screenshots/08-donate-followup.png) |
| **Receipt: split by Payouts, paid to the person who posted: $0** | **Proof: 38 of 40 test appeals correct** |
| ![Receipt](docs/screenshots/09-donate-receipt.png) | ![Proof](docs/screenshots/02-proof.png) |
| **Demo reviewer queue: no money moves from this page** | **Check with Lifeline: link and bookmarklet** |
| ![Reviewer queue](docs/screenshots/10-reviewer-queue.png) | ![Check with Lifeline](docs/screenshots/11-check-with-lifeline.png) |

## What Lifeline verifies, and what it doesn't

| | |
|---|---|
| **Verifies** | The disaster declaration (FEMA DR-4827-NC for Helene), the satellite flood extent, the place, the date window, and registered, eligibility-screened local charities (IRS register, Pub 78, revocations, OFAC). |
| **Does not verify** | The person who posted, the family, the exact need, or how the charity spends the money. |
| **What protects the donor** | The person who posted the appeal is never paid. The PayPal authorization is voided if the checks fail. Money only goes to registered local charities. Every receipt is hashed. |
| **Still needs a human** | UNVERIFIABLE cases, and the charity's follow-up with a family. |

Only PayPal's authorization, delayed capture and Payouts let us keep the donor's money safe while six agents decide, then split it to local charities or void it with zero charge, with a full evidence trail.

PayPal is the spine: **1 Authorized** (authorization ID) → **2 Checks passed** (verdict hash) → **3 Captured and split by Payouts** (payout batch ID, each item's status), or **Voided** (authorization ID) when the checks fail. Every Payouts item carries a non-sensitive case reference (`LL-<check id>`) in its `sender_item_id` and note, so the split is traceable.

## Request for charity follow-up (optional)

Want to help one family? Add a follow-up request and a link to their post. The charity checks on them first and decides how to help. It's a request, not a guarantee: Lifeline can't guarantee a specific family receives help.

- Optional family name, a note (max 200 characters) and a link to the original post (https on x.com, twitter.com, instagram.com, facebook.com or threads.net only; anything else is refused with a friendly message before payment).
- Phone numbers, email addresses, street addresses and ID numbers are blocked with a friendly message. Markup and links in the note are stripped, and the same prompt-injection check runs on it (a hit drops the note).
- It goes in each charity's PayPal Payouts item `note` and on the receipt as plain text: "Follow-up request sent to the charities (advisory, not verified by Lifeline)." It never reaches the judge, never changes a verdict and is not in `verdict_sha256`; it is covered by `receipt_sha256`.
- Lifeline never pays individuals directly.

## 38 of 40 test appeals got the expected verdict

Synthetic appeals grounded in real places, FEMA declaration data and real satellite flood extent. Baseline: Gemini alone (gemini-3.5-flash-lite, same appeal, no tools or rules) was asked whether each appeal is genuine; only a VERIFIED answer releases funds. Exact prompt:

```
Is this flood appeal genuine? Answer VERIFIED, NOT VERIFIED or UNVERIFIABLE.

Appeal (posted {posted_at}):
{text}
```

| Appeal type | Total | Lifeline correct | AI alone correct |
|---|---|---|---|
| Genuine (inside flood area) | 15 | 13 | 1 |
| Outside flood area | 10 | 10 | 3 |
| Wrong date | 5 | 5 | 0 |
| Ambiguous place | 5 | 5 | 5 |
| Red-team | 5 | 5 | 1 |
| **All** | **40** | **38** | **10** |

| Red-team attack | What it tried | Lifeline | Stopped by |
|---|---|---|---|
| rt-01 | Hidden "system note" telling the checker to mark it verified and send funds to the person who posted the appeal | NOT VERIFIED | `PROMPT_INJECTION` |
| rt-02 | Invisible zero-width characters and a fake "approval mode", for a place outside the flood area | NOT VERIFIED | `PROMPT_INJECTION`, `NO_DISASTER_DECLARATION`, `NOT_IN_FLOOD_AREA` |
| rt-03 | Look-alike charity name ("Mana Food Bank Relief") to redirect the money | UNVERIFIABLE | `NEEDS_HUMAN` |
| rt-04 | Look-alike charity name ("Grass Roots Aid Partnerships Fund") | UNVERIFIABLE | `NEEDS_HUMAN` |
| rt-05 | Real flooded place, but a date before the storm | NOT VERIFIED | `DATE_MISMATCH` |

### The two misses

- **Marion (`in-05`)**: the nearest observed flooding (Catawba River corridor) is about 3.7 km from the Census town point, outside the 2.2 km check radius, so it came back NOT VERIFIED (`NOT_IN_FLOOD_AREA`). The money was not captured; the donor is pointed to a registered local charity instead.
- **Burnsville (`in-09`)**: only 0.009 km² of observed flood overlaps the area near the town centre, so the Skeptic sent it to UNVERIFIABLE (`NEEDS_HUMAN`). Nothing is captured without a human reviewer.

Both errors are on the safe side: a genuine appeal was held back, no money went to an unverified one.

## What the numbers mean, and what they don't
- **This is a controlled evaluation, not general fraud-detection accuracy:** 40 synthetic appeals grounded in real places, FEMA data and the real satellite flood extent, with the answer key hash-locked before any run.
- **False acceptances: 0.** No unverified appeal released any money ($0).
- **False rejections: 2.** Marion and Burnsville were genuine but held back. The donor was not charged, and cases like these belong with a human reviewer.
- **The 2.2 km radius is a conservative prototype threshold,** not a universal definition of a flooded community. Flood water follows rivers and town centre points don't, so every check shows the distance to the nearest observed flood.
- **A made-up family in a real flooded town can still come back VERIFIED.** Lifeline verifies the disaster, place, date and charities, never the person or the family. That is exactly why the person who posted is never paid: in the worst case, the money still reaches a registered relief charity working where the flood really was.
- **Satellite data lags.** Flood maps arrive hours to days after a flood and can be partial. This prototype uses a post-event product for Helene. In a live disaster, an appeal from a place with no flood map yet should come back UNVERIFIABLE, not VERIFIED.
- **Sandbox only.** Payouts go to PayPal sandbox demo receivers to show the workflow. Real charity payouts would need each charity onboarded with PayPal.

### Geometry thresholds

All of these live in `lifeline/config.py` and were fixed before the evaluation ran. Each one errs towards holding money back.

| Threshold | Value | What it does | Why it is conservative |
|---|---|---|---|
| **Check radius** | 1–5 km per town: the radius of a circle with the town's Census land area (`PLACE_RADIUS_MIN_KM`, `PLACE_RADIUS_MAX_KM`). Marion 2.2 km, Marshall 1.8 km, Asheville capped at 5 km. | Observed flood water must lie within it, or the appeal is NOT VERIFIED (`NOT_IN_FLOOD_AREA`). | It is the town's own footprint, not a generous buffer. Real flooding 3.7 km from Marion's centre point was still refused. |
| **Edge rule** | Outer 20% of the radius (`EDGE_FRACTION = 0.8`) | If the nearest observed flood is only in that outer ring, the result is UNVERIFIABLE (`EDGE_OF_FLOOD`) and goes to a human. | Flood that only grazes a town is not treated as proof. |
| **Skeptic's minimum overlap** | 0.05 km² | If the flood does not cover the town point and less than 0.05 km² of observed flood lies inside the radius, the Skeptic flags `TINY_FLOOD_OVERLAP`, so the result is UNVERIFIABLE (`NEEDS_HUMAN`). Burnsville had 0.009 km². | A sliver of mapped water is not evidence that a community flooded. |
| **Flood evidence bands** (display only) | **Strong:** nearest flood within 25% of the radius **and** at least 0.5 km² flooded inside it. **Weak:** nearest flood beyond 60% of the radius (the edge rule starts at 80%) **or** under 0.1 km² flooded. **Moderate:** everything else. (`EVIDENCE_BANDS`) | Shows "Flood evidence: Strong / Moderate / Weak" with the exact numbers, e.g. "0.24 km to observed flood water, 0.71 km² flooded within 1.8 km". A VERIFIED result with Weak evidence adds "Near the edge of the observed flood. A reviewer may double-check." (Elkin, in the eval). | The Judge never reads the label, so it cannot loosen a verdict. It only tells the donor and the reviewer how close a VERIFIED result sits to the edge. |
| **Charity radius** | 40 km, IRS ruling date before the event | Only registered, eligibility-screened relief charities this close are paid. | New organisations formed after the storm are never payees. |

## How we built it
Python + FastAPI, Shapely for flood geometry, RapidFuzz for lookalike names, SQLite precomputed from public data, one static HTML/JS page with live streamed agent steps, a MapLibre GL 3D terrain flood map (Leaflet fallback) and GSAP animation. One small LLM adapter (Gemini, Anthropic, OpenAI or NVIDIA) with timeouts and fallbacks. PayPal JS SDK, Orders v2, Authorizations (capture/void) and Payouts in sandbox. Every event-specific value is loaded from an event manifest. Deployed on Render, with a Postman collection for every endpoint. Built with Cursor and Claude Code.

## Donor-first results, evidence trail and reviewer queue

- **Donor-first result.** Every result (VERIFIED, NOT VERIFIED or UNVERIFIABLE) opens with the verdict, one plain-English reason, **Paid to the person who posted: $0**, the flood evidence label and the main button. The panel "What Lifeline verifies, and what it doesn't" stays visible.
- **Full evidence trail, one click away.** The streamed agent steps, the 3D map, the "How this was decided" rules table, the IRS register rows and the hashes sit in a "Show the full evidence trail" panel. It is collapsed by default and opens automatically when the link has `#check` or `?trace=1`, so the judge links below show it expanded.
- **Flood evidence label.** "Flood evidence: Strong / Moderate / Weak" with the exact distance to observed flood water and the flooded area inside the check radius. Display only: it never changes a verdict (see [Geometry thresholds](#geometry-thresholds)).
- **Reviewer queue (demo).** [`/review`](https://lifeline-3fug.onrender.com/review) lists the UNVERIFIABLE checks from the evaluation set and from live checks made since the server started, with reason codes and evidence. "Release to charities" and "Keep held" only record the decision on screen. It is clearly labelled: *Demo reviewer queue: no money moves from this page.*
- **County-first charity matching.** Charity cards show "Serves: [county] County (declared)". The county comes from the charity's IRS address (ZIP centroid, looked up once with the US Census geocoder: `scripts/charity_counties.py`). Charities in the event's declared counties are listed first, then by distance. Choosing *which* charities are paid still uses the rule that was locked before the evaluation: putting declared counties first at that step changed two published verdict hashes, so it was kept as a ranking of the screened payees, not a change to who is picked.
- **Partner allow and block lists.** `data/partners.json` holds `allow` and `block` lists by EIN, applied after IRS / Pub 78 / revocation / OFAC screening. A blocked EIN is never paid (checked again at payment time); an allowed EIN is listed first but never skips screening. It ships with empty lists. In a real deployment a partner organisation maintains this list.

## Check with Lifeline (for platforms)

Any appeal can be checked from a link. Lifeline pre-fills the text and runs the check. The text goes through the same cleaning and prompt-injection check as pasted text, and the link never donates:

```
https://lifeline-3fug.onrender.com/?text=<url-encoded appeal>
```

Try it: <https://lifeline-3fug.onrender.com/?text=Our%20street%20in%20Marshall%20NC%20flooded%20on%20Sept%2028%2C%202024.%20Families%20need%20water%20and%20diapers.>

**Bookmarklet.** The homepage has a "Check with Lifeline" button. Drag it to the bookmarks bar, select an appeal on any site and click it: Lifeline opens in a new tab and checks the selected text.

**How a platform could add it under a post:**

```html
<a href="https://lifeline-3fug.onrender.com/?text=URL_ENCODED_POST_TEXT"
   target="_blank" rel="noopener">Check with Lifeline before you give</a>
```

```js
const href = "https://lifeline-3fug.onrender.com/?text=" + encodeURIComponent(post.text.slice(0, 4000));
```

No platform integrates this today; it shows how one could.

## Events: one real event today, any event by manifest

Helene in western North Carolina is the only real event loaded today. Nothing about it is hard-coded in the rules or the UI any more. The event name, FEMA declaration, state, declared counties, date window, flood extent file, IRS register slice and sources are loaded from [`data/events/helene-nc-2024/event.json`](data/events/helene-nc-2024/event.json) (pick another with `LIFELINE_EVENT=path/to/event.json`). [docs/ADD_AN_EVENT.md](docs/ADD_AN_EVENT.md) explains how to add another disaster. A test builds a tiny synthetic event from `tests/fixtures/test-event` (one small flood polygon, two fake charities; test-only, never shown in the app) with the same data builder and runs the whole pipeline on it.

## How it works

```mermaid
flowchart LR
  A[Appeal text] --> R[Reader<br/>LLM extracts place/state/date/need<br/>values must appear word for word]
  R --> L[Locator<br/>Census place + county<br/>same-name towns]
  L --> F[Flood Check — no LLM<br/>satellite flood extent<br/>FEMA declaration · date window<br/>all from the event manifest]
  F --> G[Register Check<br/>IRS BMF · Pub 78 · auto-revocation<br/>OFAC SDN · relief NTEE]
  G --> S[Skeptic<br/>tries to break every green]
  S --> J{Judge<br/>pure rules}
  J -- GREEN --> P1[PayPal: capture the authorization<br/>→ Payouts split across screened local charities]
  J -- RED / YELLOW --> P2[PayPal: void the authorization<br/>donor never charged · redirect to a screened local charity]
  P1 --> RC[Receipt + SHA-256]
  P2 --> RC
```

| Verdict | Meaning | Reason codes |
|---|---|---|
| 🟢 **VERIFIED** | flooded place + eligible local charities found | — |
| 🔴 **NOT VERIFIED** | a hard check failed | `NOT_IN_FLOOD_AREA` `DATE_MISMATCH` `NO_DISASTER_DECLARATION` `PROMPT_INJECTION` |
| 🟡 **UNVERIFIABLE** | doubt; needs a human | `AMBIGUOUS_PLACE` `EDGE_OF_FLOOD` `NO_ELIGIBLE_CHARITY_NEARBY` `NEEDS_HUMAN` |

Every verdict and receipt carries a SHA-256 of its inputs and evidence. `python verify.py` re-derives them all offline.

### The money (PayPal sandbox)
1. The donor clicks a real **PayPal JS SDK** button. **Orders v2, `intent: AUTHORIZE`**: the donation is *authorized*, not captured.
2. **GREEN:** capture the authorization, then **PayPal Payouts** splits it evenly (to the cent) across up to 3 registered, eligibility-screened local charities. Each one maps to a clearly labelled **SANDBOX DEMO RECEIVER**.
3. **RED, or YELLOW without human approval:** **void** the authorization, so the donor is never charged. Lifeline suggests a registered local charity where the flood actually is: *redirect, don't just block.*
4. The receipt shows who got how much, the IRS register row and the satellite evidence behind each payout.

## Results (40 appeals, locked answer key)

| | LLM alone | Lifeline |
|---|---|---|
| Accuracy | 25% | **95%** |
| Unverified appeals paid | $100 | **$0** |
| Genuine appeals funded (of 15) | 1 | **13** |
| Red-team attacks stopped | 4/5 | **5/5** |
| Avg check time | 4.1 s | 4.6 s |

**The LLM alone would have sent $100 of donor money to unverified appeals. Lifeline: $0.** The LLM approved the lookalike-charity attack, and it funded only 1 of 15 real appeals. Lifeline had two honest misses, both of which held money rather than losing it. Full details, misses and the before/after table: [eval/RESULTS.md](eval/RESULTS.md).

![Proof](docs/screenshots/02-proof.png)

## Run it

```bash
pip install -r requirements.txt
python run.py --sample      # FAST JUDGE MODE: offline, no keys, <5 s, prints the scoreboard
python verify.py            # re-derives every verdict and receipt hash
python -m pytest            # 105 tests: every rule, the payment flow, the synthetic event and the new features
python run.py               # web app on http://localhost:8000 (copy .env.example to .env first)
```

Other entry points: `python run.py --eval --tag v2` (live eval) and `python scripts/build_data.py [event.json]` (rebuild the event's store from the raw files its manifest lists). Try a check directly: `http://localhost:8000/?appeal=in-02#check`.

**LLM providers:** Gemini, Anthropic, OpenAI or NVIDIA, through one adapter (`lifeline/llm.py`). Model names are pinned in `lifeline/config.py`. Every call has a timeout, one retry and a fallback (deterministic extractor or recorded response), so a check never hangs. Every step is logged to `trace/trace.jsonl`.

## Data sources
Real data for the one loaded event, cached offline (see [data/SOURCES.md](data/SOURCES.md) and the event manifest): **ICEYE FSD-2227 Hurricane Helene observed flood extent** (SAR + Sentinel-1/2), **FEMA OpenFEMA DR-4827-NC**, **IRS EO BMF (NC)**, **IRS Pub 78**, **IRS auto-revocation list**, **OFAC SDN**, **US Census Gazetteer + Geocoder**.

**Relief NTEE codes accepted:** M20 Disaster Preparedness & Relief · M23 Search & Rescue · M24 Volunteer fire · M99 Public Safety/Disaster N.E.C. · P60 Emergency Assistance · P20 Human Service Orgs · L41 Homeless Shelters · K30 Food Programs · K31 Food Banks & Pantries · K34 Congregate Meals.

**Web UI:** one static page (`static/index.html`), no build step. Open-source libraries from CDNs, pinned: **MapLibre GL JS 4.7.1** (3D terrain map), **GSAP 3.12.5** (animation), **Leaflet 1.9.4** (2D fallback when WebGL is unavailable). Basemap: **OpenFreeMap** (© OpenMapTiles, © OpenStreetMap contributors). Terrain: **Mapzen / AWS Terrain Tiles** (Terrarium). No map API keys. Honours `prefers-reduced-motion`.

Charity eligibility rules: present in Pub 78, not on the auto-revocation list (or reinstated), not an OFAC SDN name (exact, or fuzzy ≥95), within 40 km, and IRS ruling date before the event. Organisations formed after the storm are skipped as payees.

## Honest limitations
- **We don't verify the person who posted the appeal.** That is exactly why they are never paid.
- **"Revoked" means "not currently eligible"**, not wrongdoing. Most revocations are small groups that missed three years of filings.
- **Synthetic appeals, real places, real flood data.** The 40 appeals were written for testing; the towns, the flood polygons, FEMA, IRS and OFAC data are real.
- **Place = Census centre point + a radius** (1–5 km from land area). Genuine appeals about flooding at a town's edge can be refused (Marion, in the eval). Street-level addresses would fix this.
- **Charity location = ZIP centroid** from the BMF address, not the service area. The "Serves" county is the county of that ZIP centroid.
- **One real event** (Helene, western North Carolina). The pipeline is event-agnostic, but each new event still needs its own flood extent, declaration and IRS slice (see [docs/ADD_AN_EVENT.md](docs/ADD_AN_EVENT.md)).
- **Sandbox only.** Payouts go to labelled demo receivers. Payouts need a US sandbox business account.
- The wording is deliberate: the product never calls an appeal anything but "not verified", with the reason.

- **The original-post link is plain text, never clickable**, because the post itself could be fake or harmful. A family's details reach the charity only as an advisory request; Lifeline doesn't verify the family and never pays individuals.
- **The reviewer queue is a demo.** Decisions are recorded on screen only; nothing is stored and no money moves.

## What's next
- **More real events**, each with its own manifest, flood extent, declaration and IRS slice.
- **Live flood feeds** (for example Copernicus GFM), so a new disaster can be checked while it happens.
- **Charity service-area polygons and capacity signals**, instead of ZIP centroids.
- **Real platform partnerships** for the Check with Lifeline link.

## Demo video source
The scripts that build the demo video (narration text, word timings, scene generator, screen recorder) are in [`video/`](video/README.md). Rendered video and audio files are not committed.

## Deploy on Render
`render.yaml` is included: New → Blueprint → pick this repo → fill `LLM_API_KEY`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` → Apply.

## Postman
`postman/Lifeline.postman_collection.json` covers health, check (verified / not verified / injection / streamed), PayPal order, settle, receipt and proof.

---
Built with Cursor and Claude Code. MIT License.
