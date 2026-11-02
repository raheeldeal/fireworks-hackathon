"""Shared Fireworks client for the medical-coding run: retries, ledger, price table.
Standard library only."""
import csv, json, os, sys, time, threading, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 3.00
URL = "https://api.fireworks.ai/inference/v1/chat/completions"

# $ per 1M tokens (input, output). From hackathon/runs/PROTOCOL.md, verified 2026-11-01.
PRICING = {
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}
SHORT = {k: k.split("/")[-1] for k in PRICING}
_lock = threading.Lock()


def cost_of(model, tin, tout):
    pi, po = PRICING[model]
    return (tin * pi + tout * po) / 1_000_000


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def log_ledger(model, tin, tout, tag=""):
    c = cost_of(model, tin, tout)
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "tag"])
            w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), SHORT[model], tin, tout, f"{c:.6f}", tag])
    return c


class CapReached(Exception):
    pass


def chat(model, messages, max_tokens=512, temperature=0, tag="", extra=None, timeout=180):
    """One chat completion with up to 5 retries on 429/5xx. Returns dict with
    content, reasoning_tokens, in_tokens, out_tokens, latency, finish_reason, cost."""
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        sys.exit("FIREWORKS_API_KEY not set (source ~/.zshrc)")
    if ledger_total() >= CAP_USD:
        raise CapReached(f"ledger total {ledger_total():.2f} >= cap {CAP_USD}")
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    last = None
    for attempt in range(5):
        req = urllib.request.Request(URL, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.load(resp)
            lat = time.time() - t0
            break
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")[:300]
            last = f"HTTP {e.code}: {txt}"
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt + 0.5)
                continue
            raise RuntimeError(last)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt + 0.5)
    else:
        raise RuntimeError(f"gave up after 5 attempts: {last}")
    ch = d["choices"][0]
    msg = ch["message"]
    content = msg.get("content") or ""
    usage = d.get("usage", {}) or {}
    tin = usage.get("prompt_tokens", 0) or 0
    tout = usage.get("completion_tokens", 0) or 0
    rt = ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0
    c = log_ledger(model, tin, tout, tag)
    return {"content": content, "reasoning_tokens": rt, "in_tokens": tin, "out_tokens": tout,
            "latency": lat, "finish_reason": ch.get("finish_reason"), "cost": c,
            "reasoning": msg.get("reasoning_content") or msg.get("reasoning") or ""}
