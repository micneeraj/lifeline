"""One small adapter for Gemini / Anthropic / OpenAI / NVIDIA.

Every call: hard timeout, never raises, returns (text or None, meta).
Responses are recorded to eval/recorded_llm.json keyed by sha256(provider|model|prompt) so
sample mode (`run.py --sample`) replays them fully offline.
"""
import hashlib, json, threading, time
from . import config

REC_PATH = config.ROOT / "eval" / "recorded_llm.json"
_lock = threading.Lock()
_rec = None


def _recordings():
    global _rec
    if _rec is None:
        try:
            _rec = json.loads(REC_PATH.read_text(encoding="utf-8"))
        except Exception:
            _rec = {}
    return _rec


def _key(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def provider_model():
    p = config.LLM_PROVIDER if config.LLM_PROVIDER in config.LLM_MODELS else "gemini"
    return p, config.LLM_MODELS[p]


def _call(prompt, provider, model, timeout):
    import httpx
    k = config.LLM_API_KEY
    if provider == "gemini":
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                       headers={"x-goog-api-key": k},
                       json={"contents": [{"parts": [{"text": prompt}]}],
                             "generationConfig": {"temperature": 0}},
                       timeout=timeout)
        r.raise_for_status()
        return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"] if not p.get("thought"))
    if provider == "anthropic":
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": k, "anthropic-version": "2023-06-01"},
                       json={"model": model, "max_tokens": 600, "temperature": 0,
                             "messages": [{"role": "user", "content": prompt}]}, timeout=timeout)
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    url = ("https://api.openai.com/v1/chat/completions" if provider == "openai"
           else "https://integrate.api.nvidia.com/v1/chat/completions")
    r = httpx.post(url, headers={"Authorization": f"Bearer {k}"},
                   json={"model": model, "temperature": 0, "max_tokens": 600,
                         "messages": [{"role": "user", "content": prompt}]}, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def complete(prompt, timeout=None):
    """Returns (text|None, meta). Never raises, never hangs past timeout."""
    provider, model = provider_model()
    key = _key(prompt)
    meta = {"provider": provider, "model": model, "prompt_sha256": key}
    rec = _recordings()
    if config.SAMPLE_MODE or not config.LLM_API_KEY:
        if key in rec:
            meta["source"] = "recorded"
            return rec[key]["text"], meta
        meta["source"] = "unavailable"
        return None, meta
    t0 = time.time()
    result = {}

    def run():
        for attempt in range(2):  # one retry
            try:
                result["text"] = _call(prompt, provider, model, timeout or config.LLM_TIMEOUT_S)
                return
            except Exception as e:  # noqa
                result["error"] = type(e).__name__ + ": " + str(e)[:200]
                time.sleep(1.5)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join((timeout or config.LLM_TIMEOUT_S) * 2 + 4)
    meta["latency_s"] = round(time.time() - t0, 2)
    text = result.get("text")
    if text is None:
        meta["source"] = "error"
        meta["error"] = result.get("error", "timeout")
        if key in rec:  # fall back to a recording if we have one
            meta["source"] = "recorded_fallback"
            return rec[key]["text"], meta
        return None, meta
    meta["source"] = "live"
    with _lock:
        rec[key] = {"provider": provider, "model": model, "text": text}
        REC_PATH.parent.mkdir(exist_ok=True)
        REC_PATH.write_text(json.dumps(rec, indent=1, sort_keys=True), encoding="utf-8")
    return text, meta


def parse_json(text):
    if not text:
        return None
    t = text.strip()
    if "```" in t:
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    s, e = t.find("{"), t.rfind("}")
    if s < 0 or e < 0:
        return None
    try:
        return json.loads(t[s:e + 1])
    except Exception:
        return None
