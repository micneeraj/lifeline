"""Re-derives every verdict and receipt hash offline.

1. Answer key matches its locked SHA-256.
2. For every appeal in the official eval run, re-runs the deterministic pipeline offline (recorded LLM extraction)
   and checks the verdict and verdict_sha256 match what was published.
3. Every receipt in trace/trace.jsonl re-hashes to its receipt_sha256.
"""
import hashlib, json, os, sys
from pathlib import Path

os.environ["LIFELINE_SAMPLE"] = "1"
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lifeline import pipeline  # noqa: E402


def main(results_file="eval/results_v1.json"):
    ok = True
    kb = (ROOT / "eval/answer_key.json").read_bytes()
    lock = (ROOT / "eval/LOCKED_HASH.txt").read_text().strip()
    k_ok = hashlib.sha256(kb).hexdigest() == lock
    print(f"[{'OK' if k_ok else 'FAIL'}] answer key sha256 == locked {lock[:16]}…")
    ok &= k_ok
    res = json.loads((ROOT / results_file).read_text(encoding="utf-8"))
    appeals = {a["id"]: a for a in json.loads((ROOT / "eval/appeals.json").read_text(encoding="utf-8"))}
    n = bad = 0
    for row in res["rows"]:
        a = appeals[row["id"]]
        r = pipeline.run_check(a["text"], a["posted_at"], appeal_id=a["id"], explain=False)
        n += 1
        same = r["verdict"] == row["lifeline"]["verdict"] and r["verdict_sha256"] == row["lifeline"]["verdict_sha256"]
        if not same:
            bad += 1
            print(f"[FAIL] {a['id']}: published {row['lifeline']['verdict']} {row['lifeline']['verdict_sha256'][:12]} "
                  f"re-derived {r['verdict']} {r['verdict_sha256'][:12]}")
    print(f"[{'OK' if not bad else 'FAIL'}] {n - bad}/{n} verdicts re-derived with identical SHA-256 ({results_file})")
    ok &= not bad
    rc_n = rc_bad = 0
    tf = ROOT / "trace/trace.jsonl"
    if tf.exists():
        for line in tf.open(encoding="utf-8"):
            d = json.loads(line)
            if d.get("type") == "payment" and d.get("kind") == "receipt":
                rc = {k: v for k, v in d.items() if k not in ("type", "kind")}
                rc_n += 1
                if pipeline.sha({k: v for k, v in rc.items() if k != "receipt_sha256"}) != rc["receipt_sha256"]:
                    rc_bad += 1
    print(f"[{'OK' if not rc_bad else 'FAIL'}] {rc_n - rc_bad}/{rc_n} receipts re-hash to their receipt_sha256")
    ok &= not rc_bad
    print("ALL CHECKS PASSED" if ok else "VERIFICATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
