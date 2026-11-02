"""Fireworks model access for the harness, plus a spend ledger with a hard cap.

Two backends, same call shape: `llm(messages) -> Reply`.
  ServerlessChat   - models on serverless inference (e.g. kimi-k3).
  TrainingSampler  - the serverless *training* sampler. Muse Glimmer 30B base and our LoRA checkpoints are only
                     reachable here (checked 2026-11-02: not on serverless inference).

Every call is logged to ledger.csv; once the ledger reaches CAP no further calls are made.
"""
import csv, datetime, json, os, threading, time, urllib.error, urllib.request
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
CAP = 45.00  # dollars; HARNESS.md section 11

CHAT_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
TRAINING_URL = "https://api.fireworks.ai/training/v1/serverless"

# $ per 1M tokens (input, output). Serverless rates from ../submission/fw.py (2026-11-01); training-sampler rates
# from docs.fireworks.ai/fine-tuning/training-api/serverless (2026-11-02). Cached-prefill discounts are ignored,
# so logged cost is an upper bound.
PRICES = {
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/muse-glimmer-30b": (1.96, 4.88),
    "accounts/fireworks/models/qwen3-embedding-8b": (0.10, 0.0),  # fireworks.ai/pricing, "Qwen3 8B" embeddings, 2026-11-02
}
EMBED_MODEL = "accounts/fireworks/models/qwen3-embedding-8b"
EMBED_URL = "https://api.fireworks.ai/inference/v1/embeddings"


def embed(texts, note="", batch=64):
    """Embedding vectors for a list of texts (qwen3-embedding-8b, 4,096 dims), logged to the ledger."""
    check_cap()
    headers = {"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}", "Content-Type": "application/json"}
    out = []
    for i in range(0, len(texts), batch):
        body = json.dumps({"model": EMBED_MODEL, "input": texts[i: i + batch]}).encode()
        for attempt in range(6):
            try:
                with urllib.request.urlopen(urllib.request.Request(EMBED_URL, data=body, headers=headers), timeout=120) as r:
                    resp = json.load(r)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
        out += [d["embedding"] for d in sorted(resp["data"], key=lambda d: d["index"])]
        charge(EMBED_MODEL, resp.get("usage", {}).get("prompt_tokens", 0), 0, note)
    return out
MUSE = "accounts/fireworks/models/muse-glimmer-30b"
MUSE_TOKENIZER = "meta-models/Muse-Glimmer-30B"


def full_id(model):
    return model if "/" in model else f"accounts/fireworks/models/{model}"


@dataclass
class Reply:
    text: str
    in_tokens: int
    out_tokens: int
    cost: float
    secs: float


# ---------- ledger ----------
_lock = threading.Lock()


class CapReached(RuntimeError):
    pass


def spent():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def charge(model, tin, tout, note=""):
    """Log one call and return its cost in dollars."""
    pin, pout = PRICES[model]
    cost = (tin * pin + tout * pout) / 1e6
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
            w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), model, tin, tout, f"{cost:.6f}", note])
    return cost


def check_cap():
    if spent() >= CAP:
        raise CapReached(f"ledger ${spent():.2f} >= cap ${CAP:.2f}")


# ---------- backend 1: serverless chat ----------
class ServerlessChat:
    def __init__(self, model, max_tokens=400, temperature=0.0, extra=None, note=""):
        self.name = full_id(model)
        self.max_tokens, self.temperature, self.extra, self.note = max_tokens, temperature, extra or {}, note

    def __call__(self, messages):
        check_cap()
        body = {"model": self.name, "messages": messages, "max_tokens": self.max_tokens,
                "temperature": self.temperature, **self.extra}
        headers = {"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}", "Content-Type": "application/json"}
        t0 = time.time()
        tries = 10  # rate limits hit when several runs share a model (dev pool runs lost 3-5 rows at 6 tries)
        for attempt in range(tries):  # retry rate limits and transient server errors with backoff
            try:
                req = urllib.request.Request(CHAT_URL, data=json.dumps(body).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=120) as resp:
                    out = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                    raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == tries - 1:
                    raise
            time.sleep(min(2 ** attempt, 60))
        usage = out.get("usage") or {}
        tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        text = out["choices"][0]["message"].get("content") or ""
        return Reply(text, tin, tout, charge(self.name, tin, tout, self.note), time.time() - t0)


# ---------- backend 2: training sampler (Muse Glimmer base or a LoRA checkpoint) ----------
class TrainingSampler:
    """Samples Muse Glimmer 30B through the serverless training API.

    Muse opens a hidden `to=self` reasoning channel unless the reply is pre-filled with ` to=user<|message|>`
    (found in ../submission/train/tune.py). Base and tuned checkpoints get the same prefill, so differences
    come from the weights, not the prompt.
    """

    def __init__(self, model_path=None, max_tokens=400, temperature=0.0, note=""):
        from transformers import AutoTokenizer
        from fireworks.training import sdk
        from fireworks.training.sdk import FiretitanServiceClient
        self.sdk = sdk
        self.tok = AutoTokenizer.from_pretrained(MUSE_TOKENIZER)
        service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=TRAINING_URL)
        if model_path:  # a fine-tuned checkpoint
            self.client = service.create_sampling_client(model_path=model_path, tokenizer=self.tok)
        else:
            self.client = service.create_sampling_client(base_model=MUSE, tokenizer=self.tok)
        self.name = model_path or MUSE
        self.note = note
        self.eot = self.tok.convert_tokens_to_ids("<|eot|>")
        self.params = sdk.SamplingParams(max_tokens=max_tokens, temperature=temperature, stop=[self.eot])
        self.prefill = self._answer_prefill()

    def _render(self, messages, add_generation_prompt):
        text = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_generation_prompt,
                                            reasoning_strength="low")
        return list(self.tok(text, add_special_tokens=False)["input_ids"])

    def _answer_prefill(self):
        """Tokens the template puts between 'assistant' and the answer text, up to and including <|message|>."""
        probe = [{"role": "user", "content": "probe"}]
        prompt = self._render(probe, True)
        full = self._render(probe + [{"role": "assistant", "content": "x"}], False)
        msg = self.tok.convert_tokens_to_ids("<|message|>")
        return full[len(prompt): len(full) - full[::-1].index(msg)]

    def prompt_ids(self, messages):
        return self._render(messages, True) + self.prefill

    def __call__(self, messages):
        check_cap()
        ids = self.prompt_ids(messages)
        t0 = time.time()
        for attempt in range(5):
            try:
                res = self.client.sample(prompt=self.sdk.ModelInput.from_ints(ids), num_samples=1,
                                         sampling_params=self.params).result()
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        toks = [t for t in (res.sequences[0].tokens or []) if t != self.eot]
        text = self.tok.decode(toks, skip_special_tokens=True)
        model = MUSE  # checkpoints are billed at the base model's sampler rate
        return Reply(text, len(ids), len(toks), charge(model, len(ids), len(toks), self.note), time.time() - t0)


def make_llm(model, model_path=None, **kw):
    """'muse-glimmer-30b' (optionally with a checkpoint path) -> TrainingSampler; anything else -> ServerlessChat."""
    if full_id(model) == MUSE:
        return TrainingSampler(model_path=model_path, **{k: v for k, v in kw.items() if k != "extra"})
    return ServerlessChat(model, **kw)


if __name__ == "__main__":
    print(f"ledger: ${spent():.4f} of ${CAP:.2f}")
