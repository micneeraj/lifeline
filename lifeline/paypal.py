"""PayPal sandbox: Orders v2 (intent AUTHORIZE = money held), capture or void, Payouts split.

SAMPLE MODE / no credentials -> a stub that returns clearly-labelled fake ids ("SAMPLE-...").
Every money movement is appended to trace/payments.jsonl.
"""
import base64, json, time, uuid
from . import config
from .pipeline import log_trace, sha
from . import earmark as earmark_mod

SANDBOX_LABEL = "SANDBOX DEMO RECEIVER"


def is_stub():
    return config.SAMPLE_MODE or not (config.PAYPAL_CLIENT_ID and config.PAYPAL_CLIENT_SECRET)


_tok = {"t": None, "exp": 0}


def token():
    import httpx
    if _tok["t"] and _tok["exp"] > time.time() + 60:
        return _tok["t"]
    auth = base64.b64encode(f"{config.PAYPAL_CLIENT_ID}:{config.PAYPAL_CLIENT_SECRET}".encode()).decode()
    r = httpx.post(config.PAYPAL_BASE + "/v1/oauth2/token", data={"grant_type": "client_credentials"},
                   headers={"Authorization": "Basic " + auth}, timeout=20)
    r.raise_for_status()
    j = r.json()
    _tok.update(t=j["access_token"], exp=time.time() + j["expires_in"])
    return _tok["t"]


def _req(method, path, body=None, idem=None):
    import httpx
    h = {"Authorization": "Bearer " + token(), "Content-Type": "application/json",
         "PayPal-Request-Id": idem or uuid.uuid4().hex}
    r = httpx.request(method, config.PAYPAL_BASE + path, json=body, headers=h, timeout=30)
    try:
        j = r.json()
    except Exception:
        j = {}
    if r.status_code >= 400:
        raise PayPalError(r.status_code, j)
    return j


class PayPalError(Exception):
    def __init__(self, status, body):
        super().__init__(f"PayPal {status}: {json.dumps(body)[:400]}")
        self.status, self.body = status, body


def receiver_email(i, charity):
    """Sandbox only: each verified charity maps to a clearly-labelled sandbox receiver."""
    if config.PAYPAL_RECEIVER_EMAIL:
        return config.PAYPAL_RECEIVER_EMAIL
    return f"lifeline-demo-receiver-{i + 1}@example.com"


def _log(kind, obj):
    log_trace({"type": "payment", "kind": kind, **obj})


def create_order(amount, check_id, card=None):
    amount = f"{float(amount):.2f}"
    body = {"intent": "AUTHORIZE",
            "purchase_units": [{"reference_id": check_id, "description": "Lifeline flood relief (authorized; captured only after checks pass)",
                                "custom_id": check_id, "amount": {"currency_code": "USD", "value": amount}}]}
    if card:
        body["payment_source"] = {"card": card}
    if is_stub():
        o = {"id": "SAMPLE-ORDER-" + uuid.uuid4().hex[:10].upper(), "status": "CREATED", "sample": True}
    else:
        o = _req("POST", "/v2/checkout/orders", body)
    _log("order_created", {"check_id": check_id, "order_id": o["id"], "amount": amount, "status": o.get("status")})
    return o


def authorize(order_id, check_id=None):
    if is_stub():
        a = {"order_id": order_id, "authorization_id": "SAMPLE-AUTH-" + uuid.uuid4().hex[:10].upper(),
             "status": "CREATED", "amount": None, "sample": True}
    else:
        o = _req("GET", f"/v2/checkout/orders/{order_id}")
        if o["status"] == "COMPLETED":  # card orders authorize on create
            pu = o["purchase_units"][0]
        else:
            o = _req("POST", f"/v2/checkout/orders/{order_id}/authorize", {})
            pu = o["purchase_units"][0]
        au = pu["payments"]["authorizations"][0]
        a = {"order_id": order_id, "authorization_id": au["id"], "status": au["status"],
             "amount": au["amount"]["value"], "check_id": pu.get("custom_id") or pu.get("reference_id")}
    _log("authorized", {"check_id": check_id, **a})
    return a


def capture(auth_id):
    if is_stub():
        c = {"id": "SAMPLE-CAPTURE-" + uuid.uuid4().hex[:10].upper(), "status": "COMPLETED", "sample": True}
    else:
        c = _req("POST", f"/v2/payments/authorizations/{auth_id}/capture", {"final_capture": True})
    _log("captured", {"authorization_id": auth_id, "capture_id": c["id"], "status": c["status"]})
    return c


def void(auth_id, reason):
    if is_stub():
        ok = True
    else:
        _req("POST", f"/v2/payments/authorizations/{auth_id}/void", None)
        ok = True
    _log("voided", {"authorization_id": auth_id, "reason": reason})
    return {"authorization_id": auth_id, "status": "VOIDED" if ok else "ERROR", "reason": reason}


def split(amount, n):
    cents = int(round(float(amount) * 100))
    base, extra = divmod(cents, n)
    return [(base + (1 if i < extra else 0)) / 100 for i in range(n)]


def case_ref(check_id):
    """Non-sensitive case reference shared by every payout item of one donation."""
    return f"LL-{str(check_id)[:12].upper()}"


def payouts(check_id, amount, charities, earmark=None):
    shares = split(amount, len(charities))
    case = case_ref(check_id)
    items = []
    for i, (c, s) in enumerate(zip(charities, shares)):
        items.append({"recipient_type": "EMAIL", "receiver": receiver_email(i, c),
                      "amount": {"value": f"{s:.2f}", "currency": "USD"},
                      "note": earmark_mod.payout_note(f"Lifeline relief for {c['name']} (EIN {c['ein']}) · Case {case} — {SANDBOX_LABEL}", earmark),
                      "sender_item_id": f"{case}-{c['ein']}"})
    batch_id = f"LIFELINE-{check_id}-{uuid.uuid4().hex[:6]}"
    body = {"sender_batch_header": {"sender_batch_id": batch_id, "email_subject": "Lifeline sandbox relief payout",
                                    "email_message": SANDBOX_LABEL},
            "items": items}
    if is_stub():
        res = {"batch_header": {"payout_batch_id": "SAMPLE-PAYOUT-" + uuid.uuid4().hex[:8].upper(),
                                "batch_status": "SUCCESS", "sample": True}}
    else:
        res = _req("POST", "/v1/payments/payouts", body, idem=batch_id)
        try:  # read back each item's status so the receipt shows what PayPal reports, not what we assume
            got = _req("GET", f"/v1/payments/payouts/{res['batch_header']['payout_batch_id']}")
            st = {i["payout_item"]["sender_item_id"]: i.get("transaction_status") for i in got.get("items", [])}
            for it in items:
                it["status"] = st.get(it["sender_item_id"], "PENDING")
        except PayPalError:
            pass
    _log("payout", {"check_id": check_id, "batch": res["batch_header"], "items": items})
    return res["batch_header"], items, shares


def settle(result, auth, amount, earmark=None):
    """The core rule: pay verified local charities on GREEN, otherwise void. Returns a receipt."""
    verdict = result["verdict"]
    receipt = {"check_id": result["check_id"], "case_ref": case_ref(result["check_id"]), "verdict": verdict, "verdict_sha256": result["verdict_sha256"],
               "amount": f"{float(amount):.2f}", "currency": "USD", "authorization_id": auth["authorization_id"],
               "order_id": auth.get("order_id"), "sample_mode": is_stub(), "poster_paid": False,
               "receiver_label": SANDBOX_LABEL}
    if verdict == "GREEN" and result["charities"]:
        cap = capture(auth["authorization_id"])
        try:
            header, items, shares = payouts(result["check_id"], amount, result["charities"], earmark)
            receipt.update(action="CAPTURED_AND_PAID", capture_id=cap["id"], payout_batch_id=header["payout_batch_id"],
                           payout_status=header.get("batch_status"))
        except PayPalError as e:
            shares = split(amount, len(result["charities"]))
            items = [{"receiver": receiver_email(i, c)} for i, c in enumerate(result["charities"])]
            receipt.update(action="CAPTURED_PAYOUT_FAILED", capture_id=cap["id"], payout_batch_id=None,
                           payout_status="FAILED", payout_error=e.body.get("name") or str(e.status),
                           payout_error_message=e.body.get("message"),
                           note="Donation captured into the Lifeline sandbox account; the split payout was refused by "
                                "PayPal and is held for manual disbursement. Nothing was sent to the poster.")
        fl = result.get("flood", {}).get("flood_row")
        receipt["payouts"] = [{"charity": c["name"], "ein": c["ein"], "city": c["city"], "ntee": c["ntee"],
                               "amount": f"{s:.2f}", "receiver": it["receiver"], "sender_item_id": it.get("sender_item_id"),
                               "item_status": it.get("status") or ("SAMPLE" if is_stub() else receipt.get("payout_status")),
                               "register_row": json.loads(c["raw"]),
                               "satellite_evidence": fl}
                              for c, s, it in zip(result["charities"], shares, items)]
    else:
        v = void(auth["authorization_id"], f"{verdict}: {','.join(result['reasons'])}")
        receipt.update(action="VOIDED_NOT_CHARGED", void_status=v["status"], payouts=[],
                       redirect=({"charity": result["redirect"]["name"], "ein": result["redirect"]["ein"],
                                  "city": result["redirect"]["city"]} if result.get("redirect") else None))
    if earmark:  # already cleaned + redacted; part of the receipt hash only, never the verdict
        receipt["earmark"] = dict(earmark, delivered=bool(receipt["payouts"]) and earmark.get("status") == "FORWARDED_TO_CHARITY")
    receipt["receipt_sha256"] = sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    _log("receipt", receipt)
    return receipt
