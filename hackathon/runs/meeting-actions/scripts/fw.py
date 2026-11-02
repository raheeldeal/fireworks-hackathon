"""Shared Fireworks client: retries, ledger, price table. stdlib only."""
import csv, json, os, sys, time, urllib.request, urllib.error, threading
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(ROOT, "ledger.csv")
CAP = 3.00
URL = "https://api.fireworks.ai/inference/v1/chat/completions"

PRICING = {  # $ per 1M tokens (input, output); PROTOCOL.md table, verified 2026-11-01
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
    pi, po = PRICING.get(model, (0.0, 0.0))
    return (tin * pi + tout * po) / 1e6


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def log(model, tin, tout, tag=""):
    c = cost_of(model, tin, tout)
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "tag"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), SHORT.get(model, model), tin, tout, f"{c:.6f}", tag])
    return c


class CapReached(Exception):
    pass


def chat(model, messages, max_tokens=1024, temperature=0, extra=None, tag="", timeout=180, retries=5):
    """Returns (content, latency_s, in_tokens, out_tokens, raw_json). Raises CapReached if the ledger is at the cap."""
    if ledger_total() >= CAP:
        raise CapReached(f"ledger at ${ledger_total():.2f} >= cap ${CAP:.2f}")
    key = os.environ.get("FIREWORKS_API_KEY") or sys.exit("FIREWORKS_API_KEY not set")
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
    if extra:
        body.update(extra)
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    delay = 2.0
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            lat = time.time() - t0
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            usage = data.get("usage") or {}
            tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            log(model, tin, tout, tag)
            return content, lat, tin, tout, data
        except urllib.error.HTTPError as e:
            body_txt = e.read()[:300].decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay); delay *= 2; continue
            raise RuntimeError(f"HTTP {e.code} from {model}: {body_txt}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries:
                time.sleep(delay); delay *= 2; continue
            raise
