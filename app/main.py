"""Lifeline web API. Run: uvicorn app.main:app --reload"""
import asyncio, json, os, queue, threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lifeline import config, earmark, paypal, pipeline

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Lifeline", description="Every dollar finds the flood.", version="1.0.0")
CHECKS: dict = {}       # check_id -> result (server-side, so a client can never forge a verdict)
RECEIPTS: dict = {}
REVIEWER_TOKEN = os.getenv("LIFELINE_REVIEWER_TOKEN", "")


def public(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


class CheckIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=4000)
    posted_at: str | None = None
    appeal_id: str | None = None


class OrderIn(BaseModel):
    check_id: str
    amount: float = Field(..., gt=0, le=10000)


class SettleIn(BaseModel):
    check_id: str
    order_id: str
    amount: float = Field(..., gt=0, le=10000)
    reviewer_token: str | None = None
    family: str | None = Field(None, max_length=400)
    note: str | None = Field(None, max_length=1000)
    post_link: str | None = Field(None, max_length=1000)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "sample_mode": config.SAMPLE_MODE, "paypal_stub": paypal.is_stub(),
            "llm": config.LLM_MODELS.get(config.LLM_PROVIDER or "gemini") if config.LLM_API_KEY else None}


@app.get("/api/config")
def cfg():
    return {"paypal_client_id": None if paypal.is_stub() else config.PAYPAL_CLIENT_ID,
            "sample_mode": config.SAMPLE_MODE or paypal.is_stub(), "event": config.EVENT,
            "reviewer_enabled": bool(REVIEWER_TOKEN)}


@app.get("/api/appeals")
def appeals():
    a = json.loads((ROOT / "eval" / "appeals.json").read_text(encoding="utf-8"))
    return [{k: x[k] for k in ("id", "text", "posted_at", "handle", "platform")} for x in a]


@app.get("/api/flood.geojson")
def flood():
    return FileResponse(ROOT / "data" / "flood_wnc.geojson", media_type="application/geo+json")


def _run(body: CheckIn, emit=None):
    r = pipeline.run_check(body.text, body.posted_at, emit=emit)
    CHECKS[r["check_id"]] = r
    return r


@app.post("/api/check")
def check(body: CheckIn):
    return public(_run(body))


@app.post("/api/check/stream")
async def check_stream(body: CheckIn):
    """Server-sent events: one `step` event per agent as it runs, then `result`."""
    q: queue.Queue = queue.Queue()

    def work():
        try:
            r = _run(body, emit=lambda step, payload: q.put(("step", {"step": step, **payload})))
            q.put(("result", public(r)))
        except Exception as e:  # never hang the client
            q.put(("error", {"error": type(e).__name__, "detail": str(e)[:300]}))
        q.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def gen():
        while True:
            try:
                item = await asyncio.to_thread(q.get, True, 60)
            except Exception:
                yield "event: error\ndata: {\"error\": \"timeout\"}\n\n"
                return
            if item is None:
                return
            ev, data = item
            yield f"event: {ev}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/check/{check_id}")
def get_check(check_id: str):
    if check_id not in CHECKS:
        raise HTTPException(404, "unknown check")
    return public(CHECKS[check_id])


@app.post("/api/paypal/order")
def create_order(body: OrderIn):
    if body.check_id not in CHECKS:
        raise HTTPException(404, "run a check first")
    try:
        o = paypal.create_order(body.amount, body.check_id)
    except paypal.PayPalError as e:
        raise HTTPException(502, e.body)
    return {"id": o["id"], "status": o.get("status"), "sample": paypal.is_stub()}


@app.post("/api/paypal/settle")
def settle(body: SettleIn):
    """Authorize (hold) the approved order, then capture+payout on GREEN, otherwise void."""
    r = CHECKS.get(body.check_id)
    if not r:
        raise HTTPException(404, "unknown check")
    try:
        try:  # untrusted text; never reaches the verdict
            em = earmark.clean(body.family, body.note, body.post_link)
        except (earmark.LinkRejected, earmark.NoteRejected) as e:
            raise HTTPException(400, {"message": str(e)})
        auth = paypal.authorize(body.order_id, body.check_id)
        result = r
        if r["verdict"] == "YELLOW" and REVIEWER_TOKEN and body.reviewer_token == REVIEWER_TOKEN and r["charities"]:
            result = dict(r, verdict="GREEN", reasons=r["reasons"] + ["HUMAN_APPROVED"])
        receipt = paypal.settle(result, auth, body.amount, em)
    except paypal.PayPalError as e:
        raise HTTPException(502, e.body)
    RECEIPTS[receipt["check_id"]] = receipt
    return receipt


@app.get("/api/receipt/{check_id}")
def receipt(check_id: str):
    if check_id not in RECEIPTS:
        raise HTTPException(404, "no receipt")
    return RECEIPTS[check_id]


@app.get("/api/payouts/{check_id}")
def payout_status(check_id: str):
    rc = RECEIPTS.get(check_id)
    if not rc or not rc.get("payout_batch_id"):
        raise HTTPException(404, "no payout batch")
    try:
        return paypal.payout_status(rc["payout_batch_id"])
    except paypal.PayPalError as e:
        raise HTTPException(502, e.body)


@app.get("/api/proof")
def proof():
    files = sorted((ROOT / "eval").glob("results_*.json"))
    official = ROOT / "eval" / "results_v1.json"
    f = official if official.exists() else (files[-1] if files else None)
    if not f:
        return JSONResponse({"error": "no eval run yet"}, 404)
    d = json.loads(f.read_text(encoding="utf-8"))
    appeals_by_id = {a["id"]: a for a in json.loads((ROOT / "eval" / "appeals.json").read_text(encoding="utf-8"))}
    for row in d["rows"]:
        row["text"] = appeals_by_id[row["id"]]["text"]
    return d


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
