"""Runs Lifeline and the LLM-alone baseline over the 40 appeals and scores them against the locked key.

Refuses to run if eval/answer_key.json does not match eval/LOCKED_HASH.txt.
Usage: python eval/run_eval.py [--tag NAME]
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
H = ROOT / "eval"
DOLLARS = 100

BASELINE_PROMPT = """Is this flood appeal genuine? Answer VERIFIED, NOT VERIFIED or UNVERIFIABLE.

Appeal (posted {posted_at}):
{text}"""
MAP = {"VERIFIED": "GREEN", "NOT VERIFIED": "RED", "UNVERIFIABLE": "YELLOW"}


def check_lock():
    kb = (H / "answer_key.json").read_bytes()
    want = (H / "LOCKED_HASH.txt").read_text().strip()
    got = hashlib.sha256(kb).hexdigest()
    if got != want:
        sys.exit(f"REFUSING TO RUN: answer_key.json sha256 {got} != locked {want}")
    return json.loads(kb), got


def baseline(a):
    from lifeline import llm
    t0 = time.time()
    text, meta = llm.complete(BASELINE_PROMPT.format(text=a["text"], posted_at=a["posted_at"]))
    v = None
    if text:
        u = text.upper()
        # first label mentioned wins; check longest first so NOT VERIFIED isn't read as VERIFIED
        pos = {lab: u.find(lab) for lab in ("NOT VERIFIED", "UNVERIFIABLE", "VERIFIED")}
        if pos["NOT VERIFIED"] >= 0:
            pos["VERIFIED"] = u.replace("NOT VERIFIED", "~" * 12).find("VERIFIED")
        found = {k: p for k, p in pos.items() if p >= 0}
        if found:
            v = MAP[min(found, key=found.get)]
    return {"verdict": v or "YELLOW", "raw": (text or "")[:300], "source": meta.get("source"),
            "parsed": v is not None, "elapsed_s": round(time.time() - t0, 2)}


def score(rows, key, field):
    n = len(rows)
    correct = sum(r[field]["verdict"] == key[r["id"]]["expect"] for r in rows)
    paid_bad = [r["id"] for r in rows if r[field]["verdict"] == "GREEN" and key[r["id"]]["expect"] != "GREEN"]
    paid_good = sum(r[field]["verdict"] == "GREEN" and key[r["id"]]["expect"] == "GREEN" for r in rows)
    rt = [r for r in rows if key[r["id"]]["category"] == "red_team"]
    rt_stopped = sum(r[field]["verdict"] != "GREEN" for r in rt)
    t = [r[field]["elapsed_s"] for r in rows]
    by_cat = {}
    for r in rows:
        c = key[r["id"]]["category"]
        by_cat.setdefault(c, [0, 0])
        by_cat[c][0] += r[field]["verdict"] == key[r["id"]]["expect"]
        by_cat[c][1] += 1
    return {"accuracy": round(correct / n, 3), "correct": correct, "n": n,
            "paid_unverified_count": len(paid_bad), "paid_unverified_ids": paid_bad,
            "paid_unverified_usd": len(paid_bad) * DOLLARS, "paid_genuine_count": paid_good,
            "red_team_stopped": rt_stopped, "red_team_total": len(rt),
            "avg_check_s": round(sum(t) / n, 2), "by_category": {k: f"{a}/{b}" for k, b2 in by_cat.items() for a, b in [b2]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run")
    ap.add_argument("--skip-baseline", action="store_true")
    args = ap.parse_args()
    key, key_hash = check_lock()
    from lifeline import pipeline, config
    appeals = json.loads((H / "appeals.json").read_text(encoding="utf-8"))
    rows = []
    for a in appeals:
        r = pipeline.run_check(a["text"], a["posted_at"], appeal_id=a["id"], explain=False)
        row = {"id": a["id"], "lifeline": {"verdict": r["verdict"], "reasons": r["reasons"],
                                           "elapsed_s": r["elapsed_s"], "verdict_sha256": r["verdict_sha256"],
                                           "extractor": r["reader"].get("extractor"),
                                           "payees": [c["name"] for c in r["charities"]]}}
        if not args.skip_baseline:
            row["baseline"] = baseline(a)
        exp = key[a["id"]]
        row["expect"] = exp
        mark = "ok " if r["verdict"] == exp["expect"] else "MISS"
        print(f"{mark} {a['id']:7s} expect {exp['expect']:6s} {str(exp['reason']):24s} lifeline {r['verdict']:6s} "
              f"{','.join(r['reasons']):40s} baseline {row.get('baseline', {}).get('verdict', '-'):6s} {r['elapsed_s']}s")
        rows.append(row)
    out = {"tag": args.tag, "key_sha256": key_hash, "mode": "sample" if config.SAMPLE_MODE else "live",
           "llm": config.LLM_MODELS.get(config.LLM_PROVIDER or "gemini"),
           "lifeline": score(rows, key, "lifeline"),
           "baseline": score(rows, key, "baseline") if not args.skip_baseline else None, "rows": rows}
    reason_hits = sum(1 for r in rows if r["expect"]["reason"] and r["expect"]["reason"] in r["lifeline"]["reasons"])
    out["lifeline"]["reason_code_match"] = f"{reason_hits}/{sum(1 for r in rows if r['expect']['reason'])}"
    (H / f"results_{args.tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print_scoreboard(out)
    return out


def print_scoreboard(out):
    L, B = out["lifeline"], out["baseline"]
    print("\n================ SCOREBOARD (" + out["mode"].upper() + " MODE) ================")
    print(f"{'':32s}{'LLM alone':>14s}{'Lifeline':>14s}")
    if B:
        print(f"{'Accuracy':32s}{B['accuracy']:>14.1%}{L['accuracy']:>14.1%}")
        print(f"{'Unverified appeals paid':32s}{B['paid_unverified_count']:>14d}{L['paid_unverified_count']:>14d}")
        print(f"{'Red-team attacks stopped':32s}{str(B['red_team_stopped']) + '/5':>14s}{str(L['red_team_stopped']) + '/5':>14s}")
        print(f"{'Genuine appeals funded':32s}{B['paid_genuine_count']:>14d}{L['paid_genuine_count']:>14d}")
        print(f"{'Avg check time (s)':32s}{B['avg_check_s']:>14.2f}{L['avg_check_s']:>14.2f}")
        print(f"\nLLM alone would have sent ${B['paid_unverified_usd']:,} of donor money to unverified appeals. "
              f"Lifeline: ${L['paid_unverified_usd']:,}.")
    print(f"Lifeline by category: {L['by_category']}   reason codes matched: {L['reason_code_match']}")


if __name__ == "__main__":
    main()
