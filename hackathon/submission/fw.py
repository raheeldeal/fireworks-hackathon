#!/usr/bin/env python3
"""Shared Fireworks client: retry/backoff, ledger, pricing, reasoning handling. Stdlib only."""
import json, os, time, urllib.request, urllib.error, csv, datetime, threading

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
CAP = 3.00
URL = "https://api.fireworks.ai/inference/v1/chat/completions"
PRICING = {  # $ per 1M tokens (input, output), PROTOCOL.md 2026-11-01
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}
SHORT = {k.split("/")[-1]: k for k in PRICING}
_lock = threading.Lock()

def model_id(m):
    return SHORT.get(m, m)

def cost_of(model, tin, tout):
    pi, po = PRICING.get(model_id(model), (0.0, 0.0))
    return (tin * pi + tout * po) / 1e6

def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))

def log_ledger(model, tin, tout, note=""):
    c = cost_of(model, tin, tout)
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
            w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), model_id(model), tin, tout, f"{c:.6f}", note])
    return c

class CapReached(Exception):
    pass

def chat(model, messages, max_tokens=512, temperature=0, extra=None, note="", timeout=120, retries=5):
    """Returns dict: content, reasoning, latency, in_tokens, out_tokens, reasoning_tokens, finish_reason, raw."""
    if ledger_total() >= CAP:
        raise CapReached(f"ledger total ${ledger_total():.2f} >= cap ${CAP}")
    key = os.environ["FIREWORKS_API_KEY"]
    body = {"model": model_id(model), "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    delay = 2
    for attempt in range(retries + 1):
        req = urllib.request.Request(URL, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay); delay = min(delay * 2, 30); continue
            raise RuntimeError(f"HTTP {e.code}: {body_txt}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                time.sleep(delay); delay = min(delay * 2, 30); continue
            raise
    latency = time.time() - t0
    ch = out["choices"][0]
    msg = ch["message"]
    usage = out.get("usage", {}) or {}
    tin = usage.get("prompt_tokens", 0); tout = usage.get("completion_tokens", 0)
    rt = ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0
    log_ledger(model, tin, tout, note)
    return {"content": msg.get("content") or "", "reasoning": msg.get("reasoning_content") or "",
            "latency": latency, "in_tokens": tin, "out_tokens": tout, "reasoning_tokens": rt,
            "finish_reason": ch.get("finish_reason"), "raw": out}

if __name__ == "__main__":
    print(f"ledger total: ${ledger_total():.4f}")
