"""Lifeline entry point.

  python run.py            start the web app on http://localhost:8000
  python run.py --sample   FAST JUDGE MODE: offline, no keys, recorded LLM responses, stubbed PayPal
  python run.py --eval     live evaluation (needs LLM key) -> eval/results_<tag>.json
"""
import os, sys, time


def sample():
    os.environ["LIFELINE_SAMPLE"] = "1"
    t0 = time.time()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("=" * 64)
    print(" LIFELINE — SAMPLE MODE (offline · recorded LLM responses · PayPal STUBBED)")
    print("=" * 64)
    import json
    from eval import run_eval
    from lifeline import paypal, pipeline
    sys.argv = ["run_eval", "--tag", "sample"]
    out = run_eval.main()
    # one end-to-end payment in stub mode for a verified and a non-verified appeal
    print("\n--- Payment flow (SAMPLE MODE stub, no real money) ---")
    appeals = {a["id"]: a for a in json.loads(open("eval/appeals.json", encoding="utf-8").read())}
    for aid in ("in-02", "out-01"):
        a = appeals[aid]
        r = pipeline.run_check(a["text"], a["posted_at"], appeal_id=aid, explain=False)
        o = paypal.create_order(25, aid)
        rc = paypal.settle(r, paypal.authorize(o["id"], aid), 25)
        print(f"{aid}: {r['verdict']:6s} -> {rc['action']}; " +
              (", ".join(f"{p['charity']} ${p['amount']}" for p in rc["payouts"]) or
               f"redirect: {(rc.get('redirect') or {}).get('charity')}") + f"  receipt {rc['receipt_sha256'][:16]}...")
    print(f"\nSAMPLE MODE finished in {time.time() - t0:.1f}s. Re-check every hash with: python verify.py")
    return out


if __name__ == "__main__":
    if "--sample" in sys.argv:
        sample()
    elif "--eval" in sys.argv:
        from eval import run_eval
        sys.argv = [a for a in sys.argv if a != "--eval"]
        run_eval.main()
    else:
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
