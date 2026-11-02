"""Shared Fireworks client for this run: retries, ledger, pricing. Stdlib only."""
import csv, json, os, sys, time, urllib.request, urllib.error, threading
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 3.00
URL = "https://api.fireworks.ai/inference/v1/chat/completions"

# $ per 1M tokens (input, output). From runs/PROTOCOL.md, verified 2026-11-01.
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


def cost_of(model, in_tok, out_tok):
    pi, po = PRICING.get(model, (0.0, 0.0))
    return (in_tok * pi + out_tok * po) / 1e6


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def _log(model, in_tok, out_tok, cost, note=""):
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), SHORT.get(model, model), in_tok, out_tok, f"{cost:.6f}", note])


class CapReached(Exception):
    pass


def chat(model, messages, max_tokens=1500, temperature=0, response_format=None, note="", timeout=120, extra=None):
    """Returns (content, reasoning_content, latency_s, in_tok, out_tok, finish_reason). Raises CapReached at the cap."""
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        sys.exit("FIREWORKS_API_KEY not set; run: source ~/.zshrc")
    if ledger_total() >= CAP_USD:
        raise CapReached(f"ledger total >= ${CAP_USD}")
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
    if response_format:
        body["response_format"] = response_format
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    delay = 5.0
    for attempt in range(9):
        req = urllib.request.Request(URL, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.load(resp)
            lat = time.time() - t0
            break
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < 8:
                time.sleep(delay); delay = min(delay * 2, 90); continue
            raise RuntimeError(f"HTTP {e.code}: {txt}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 8:
                time.sleep(delay); delay = min(delay * 2, 90); continue
            raise
    msg = d["choices"][0]["message"]
    usage = d.get("usage") or {}
    in_tok = usage.get("prompt_tokens", 0) or 0
    out_tok = usage.get("completion_tokens", 0) or 0
    c = cost_of(model, in_tok, out_tok)
    _log(model, in_tok, out_tok, c, note)
    return (msg.get("content") or ""), (msg.get("reasoning_content") or ""), lat, in_tok, out_tok, d["choices"][0].get("finish_reason")
