"""Re-records the donor-facing explanations (live LLM) for the 40 appeals so sample mode replays them.

Prunes eval/recorded_llm.json to the prompts the official eval uses (Reader + baseline) and the
new explanation prompts. Verdicts are unaffected: explanations are not part of any verdict hash.
Usage: python eval/record_explanations.py
"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lifeline import agents, llm, pipeline  # noqa: E402
from eval.run_eval import BASELINE_PROMPT  # noqa: E402


def key(p):
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


def main():
    appeals = json.loads((ROOT / "eval/appeals.json").read_text(encoding="utf-8"))
    rec = llm._recordings()
    v1 = {r["id"]: r for r in json.loads((ROOT / "eval/results_v1.json").read_text(encoding="utf-8"))["rows"]}
    keep, missing = set(), []
    for a in appeals:
        kr = key(agents.READER_PROMPT.format(text=a["text"]))
        kb = key(BASELINE_PROMPT.format(text=a["text"], posted_at=a["posted_at"]))
        keep |= {kr, kb}
        # in v1 a failed LLM call has no recording by design (replay reproduces the failure)
        if kr not in rec and v1[a["id"]]["lifeline"]["extractor"] != "fallback":
            missing.append((a["id"], "reader"))
        if kb not in rec and v1[a["id"]]["baseline"]["source"] != "error":
            missing.append((a["id"], "baseline"))
    if missing:
        sys.exit(f"eval recordings missing {missing}; refusing to prune")
    for k in list(rec):
        if k not in keep:
            del rec[k]
    # Eval prompts (Reader/baseline) must REPLAY the official v1 recordings; only explanations go live.
    live = llm.complete

    def guarded(prompt, timeout=None):
        if key(prompt) in keep:
            r = rec.get(key(prompt))
            return (r["text"], {"source": "recorded"}) if r else (None, {"source": "unavailable"})
        return live(prompt, timeout)
    agents.llm.complete = guarded
    used_llm = 0
    for a in appeals:
        r = pipeline.run_check(a["text"], a["posted_at"], appeal_id=a["id"], explain=True)
        facts = agents.explain_facts(r["label"], r["reason_text"], r["location"].get("place"), len(r["charities"]))
        src = "llm" if r["explanation"] != facts else "template"
        used_llm += src == "llm"
        print(f"{a['id']:7s} {r['verdict']:6s} [{src:8s}] {r['explanation']}")
    print(f"\n{used_llm}/40 LLM rephrasings accepted; others fell back to the fact template.")
    print(f"recordings: {len(rec)}")


if __name__ == "__main__":
    main()
