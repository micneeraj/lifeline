"""Runs the six steps, emits each step as it finishes, writes a JSONL trace, hashes the result."""
import hashlib, json, time, uuid
from datetime import datetime, timezone

from . import agents, config

VERDICT_TEXT = {"GREEN": "VERIFIED", "RED": "NOT VERIFIED", "YELLOW": "UNVERIFIABLE"}
REASON_TEXT = {
    "NOT_IN_FLOOD_AREA": "The place is not inside the satellite-observed flood area.",
    "DATE_MISMATCH": "The appeal's date does not fit the {short_name} event window.",
    "NO_DISASTER_DECLARATION": "The county is not in the FEMA {fema_decl} disaster declaration.",
    "PROMPT_INJECTION": "The appeal contains hidden instructions aimed at the checker.",
    "AMBIGUOUS_PLACE": "This town name exists in several states and the appeal does not say which.",
    "EDGE_OF_FLOOD": "The observed flood only touches the edge of this place.",
    "NO_ELIGIBLE_CHARITY_NEARBY": "No currently-eligible registered relief charity was found nearby.",
    "NEEDS_HUMAN": "Something needs a human look before money moves.",
}


FLAG_TEXT = {
    "LOOKALIKE_CHARITY": "The charity named in the appeal looks like a registered charity but is not one, so a human should check before money moves.",
    "TINY_FLOOD_OVERLAP": "Only a very small observed flood area touches this place, so a human should check before money moves.",
    "NAMED_CHARITY_NOT_ELIGIBLE": "The charity named in the appeal is not currently eligible in the IRS register, so a human should check before money moves.",
}


def specific_reason(code, flags, trace):
    if code == "NEEDS_HUMAN":
        for f in flags:
            if f in FLAG_TEXT:
                return FLAG_TEXT[f]
        if any(r["rule"] in ("NO_PLACE", "PLACE_NOT_FOUND", "PLACE_NOT_IN_STATE") for r in trace):
            return "The place in the appeal could not be found in US Census data, so a human should check before money moves."
        if any(r["rule"] == "DATE_UNKNOWN" for r in trace):
            return "The appeal has no date, so a human should check before money moves."
    return REASON_TEXT[code].format(**config.EVENT_MANIFEST)


EDGE_NOTE = "Near the edge of the observed flood. A reviewer may double-check."


def summary_line(verdict, reason_text):
    """One plain-English line for the donor-first view."""
    if verdict == "GREEN":
        return "The disaster, the place, the date and the local charities all checked out."
    return reason_text[0] if reason_text else "A check could not be completed."


def rank_for_display(charities):
    """County-first ordering of the screened payees for display: partner-approved, then charities whose IRS
    address county is in the event's declared counties, then by distance. Does not change who is paid."""
    return sorted(charities, key=lambda c: (not c.get("partner"), not c.get("county_declared"), c["distance_km"]))


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha(obj):
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def decide(text, posted_at, extracted, loc, flood, charities, n_eligible, flags, injection):
    return agents.judge(injection, extracted, loc, flood, charities, n_eligible, flags)


def run_check(text, posted_at=None, emit=None, appeal_id=None, explain=True, recorded_extract=None):
    emit = emit or (lambda step, payload: None)
    t0 = time.time()
    trace = []
    check_id = appeal_id or uuid.uuid4().hex[:12]

    def step(name, fn):
        n0 = len(trace)
        s = time.time()
        emit(name, {"status": "running"})
        res = fn()
        emit(name, {"status": "done", "ms": int((time.time() - s) * 1000), "rules": trace[n0:]})
        return res

    injection = agents.detect_injection(text)
    if injection:
        agents.rule(trace, "Reader", "PROMPT_INJECTION", "fail",
                    f"Appeal contains instructions aimed at the checker: {injection}")
    if recorded_extract is not None:
        extracted, rmeta = recorded_extract, {"extractor": "recorded"}
        step("Reader", lambda: agents.rule(trace, "Reader", "EXTRACTED", "info", "replayed extraction", extracted))
    else:
        extracted, rmeta = step("Reader", lambda: agents.reader(text, trace))
    def locate():
        l = agents.locator(extracted, trace)
        if l.get("status") in ("NOT_FOUND", "NO_PLACE"):
            fb = agents.fallback_extract(text).get("place")
            if fb and fb != extracted.get("place"):
                agents.rule(trace, "Locator", "PLACE_RETRY", "info", f"Retrying with another place named in the appeal: '{fb}'")
                l = agents.locator(dict(extracted, place=fb), trace)
        return l
    loc = step("Locator", locate)
    flood = {}
    charities, n_el = [], 0
    if loc.get("lat") is not None:
        def fcheck():
            f = agents.flood_check(loc, extracted, posted_at, trace)
            ev = agents.flood_evidence(f)  # display only; the Judge never reads it
            agents.rule(trace, "Flood Check", "FLOOD_EVIDENCE", "info", f"Flood evidence: {ev['band']} ({ev['text']})", ev)
            return f
        flood = step("Flood Check", fcheck)
        charities, n_el = step("Register Check", lambda: agents.register_check(loc, trace))
    else:
        emit("Flood Check", {"status": "skipped"})
        emit("Register Check", {"status": "skipped"})
    flags = step("Skeptic", lambda: agents.skeptic(extracted, loc, flood, trace))
    def judge():
        v, rs = agents.judge(injection, extracted, loc, flood, charities, n_el, flags)
        agents.rule(trace, "Judge", v, {"GREEN": "pass", "RED": "fail", "YELLOW": "doubt"}[v],
                    f"{VERDICT_TEXT[v]}" + (f" — {', '.join(rs)}" if rs else ""))
        return v, rs
    verdict, reasons = step("Judge", judge)

    redirect = None
    if verdict != "GREEN":
        redirect = flood_redirect(loc, flood, charities)

    inputs = {"text": text, "posted_at": posted_at, "extracted": extracted,
              "config": {"event": config.EVENT, "radius_max": config.PLACE_RADIUS_MAX_KM,
                         "edge": config.EDGE_FRACTION, "charity_km": config.CHARITY_RADIUS_KM}}
    evidence = {"location": loc, "flood": flood, "charities": [{k: c[k] for k in ("ein", "name", "ntee", "distance_km")}
                                                               for c in charities],
                "flags": flags, "injection": injection}
    result = {
        "check_id": check_id, "verdict": verdict, "label": VERDICT_TEXT[verdict], "reasons": reasons,
        "reason_text": [specific_reason(r, flags, trace) for r in reasons], "extracted": extracted, "location": loc, "flood": flood,
        "charities": charities, "redirect": redirect, "rules": trace, "injection": injection,
        "reader": {k: v for k, v in rmeta.items() if k != "raw"},
        "elapsed_s": round(time.time() - t0, 2),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    result["inputs_sha256"] = sha(inputs)
    result["verdict_sha256"] = sha({"inputs": inputs, "evidence": evidence, "verdict": verdict, "reasons": reasons})
    result["_hash_inputs"] = {"inputs": inputs, "evidence": evidence}
    ev = agents.flood_evidence(flood)
    if verdict == "GREEN" and ev["band"] == "Weak":
        ev["note"] = EDGE_NOTE
    result["flood_evidence"] = ev          # display only, added after hashing
    result["summary_line"] = summary_line(verdict, result["reason_text"])
    result["charities_display"] = rank_for_display(charities)
    result["event"] = {"id": config.EVENT_MANIFEST["id"], "name": config.EVENT["name"]}
    if explain:
        result["explanation"] = agents.explain(VERDICT_TEXT[verdict], result["reason_text"], loc.get("place"), len(charities))
    log_trace({"type": "check", **{k: v for k, v in result.items() if k != "charities"}})
    return result


def flood_redirect(loc, flood, charities):
    """Redirect, don't just block: a verified charity where the flood actually is."""
    if flood.get("flood") in ("IN_FLOOD", "EDGE") and charities:
        return charities[0]
    # place not flooded / unknown: nearest observed-flood community to the claimed place (default Asheville)
    d_lat, d_lon = config.EVENT_MANIFEST["default_redirect_point"]
    lat, lon = loc.get("lat", d_lat), loc.get("lon", d_lon)
    tree, geoms, meta = agents.flood_index()
    i = int(tree.nearest(agents.Point(lon, lat)))
    c = geoms[i].representative_point()
    picked, _ = agents.register_check({"lat": c.y, "lon": c.x}, [])
    return picked[0] if picked else None


def log_trace(obj):
    config.TRACE_DIR.mkdir(exist_ok=True)
    with open(config.TRACE_DIR / "trace.jsonl", "a", encoding="utf-8") as f:
        f.write(canon(obj) + "\n")
