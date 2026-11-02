"""Minimal ReAct agent: Thought -> Action -> Observation, in a loop, with guardrails."""
import json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TICKETS = os.path.join(HERE, "..", "hackathon", "eval", "data", "tickets.jsonl")
MODEL = "accounts/fireworks/models/glm-5p3-flash"
PRICE_PER_M = (0.20, 0.60)  # $ per 1M tokens (input, output). Approximate; check fireworks.ai/pricing.


# ---------- 1. talking to the model ----------
def call_model(messages):
    """Send the chat transcript to Fireworks. Returns (text, cost_in_dollars, seconds)."""
    body = {"model": MODEL, "messages": messages, "max_tokens": 1024, "temperature": 0}
    req = urllib.request.Request(
        "https://api.fireworks.ai/inference/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}",
                 "Content-Type": "application/json"})
    t0 = time.time()
    resp = json.load(urllib.request.urlopen(req, timeout=90))
    usage = resp["usage"]
    cost = (usage["prompt_tokens"] * PRICE_PER_M[0] + usage["completion_tokens"] * PRICE_PER_M[1]) / 1e6
    text = resp["choices"][0]["message"].get("content") or ""  # reasoning models may return None
    return text, cost, time.time() - t0


# ---------- 2. tools ----------
def calculator(expression):
    """Safe arithmetic. Only digits, + - * / . ( ) and spaces are allowed."""
    pass  # TODO(Raheel): your turn


if __name__ == "__main__":
    text, cost, secs = call_model([{"role": "user", "content": sys.argv[1]}])
    print(f"{text}\n-- ${cost:.6f}, {secs:.1f}s")
