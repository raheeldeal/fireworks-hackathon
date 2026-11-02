"""Generate synthetic clinical notes with glm-5p3. Labels are SAMPLED first (seeded RNG),
then the model writes a note implying exactly those conditions. Batches of 10 notes per call
to amortise the model's hidden reasoning tokens. Output: data/all.jsonl (500 rows)."""
import json, os, random, re, sys, argparse
from concurrent.futures import ThreadPoolExecutor
import fw

HERE = os.path.dirname(os.path.abspath(__file__))
GEN_MODEL = "accounts/fireworks/models/glm-5p3"
CODES = json.load(open(os.path.join(HERE, "data", "codes.json")))["codes"]
DESC = dict(CODES)
BATCH = 10

SYSTEM = """You write SYNTHETIC clinical notes for a training dataset. No real patients; invent every detail.
For each item you are given a list of diagnoses. Write a realistic 80-150 word outpatient or inpatient note
(history, exam findings, relevant medications, plan) that lets a medical coder infer EXACTLY those diagnoses.
Rules:
- Imply the conditions through clinical language, findings, labs and medications. You may name the condition
  in plain words (e.g. "COPD") or only imply it; vary your style across notes.
- NEVER write any ICD-10 code (no strings like E11 or I10).
- Do NOT introduce any other codable diagnosis beyond the ones listed. Incidental symptoms are fine only if they
  belong to the listed conditions. Do not mention obesity, tobacco use, diabetes, hypertension etc. unless listed.
- Vary age, sex, setting (clinic, ED, hospital, telehealth), note style (SOAP, narrative, bullet-ish) and specialty.
Return ONLY a JSON object: {"notes": [{"n": 1, "note": "..."}, ...]} with one entry per item, in order."""

SETTINGS = ["primary care clinic", "emergency department", "hospital ward", "telehealth visit", "urgent care",
            "cardiology clinic", "endocrinology clinic", "pulmonology clinic", "gastroenterology clinic",
            "psychiatry outpatient", "neurology clinic", "orthopedic clinic", "nephrology clinic", "dermatology clinic"]


def sample_labels(rng, n):
    rows = []
    for i in range(n):
        k = rng.choices([1, 2, 3, 4], weights=[0.25, 0.35, 0.25, 0.15])[0]
        codes = sorted(rng.sample([c for c, _ in CODES], k))
        rows.append({"id": f"mc-{i:03d}", "codes": codes,
                     "age": rng.randint(18, 89), "sex": rng.choice(["female", "male"])})
    return rows


def build_user(batch):
    lines = []
    for j, r in enumerate(batch, 1):
        conds = "; ".join(f"{DESC[c]}" for c in r["codes"])
        lines.append(f"{j}. Patient: {r['age']}-year-old {r['sex']}. Diagnoses: {conds}")
    return ("Write one note per item. Pick a fitting care setting yourself (vary clinic, ED, ward, telehealth). "
            "Write directly without deliberating.\n\n" + "\n".join(lines))


def parse(content):
    content = content.strip()
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d.get("notes")


CODE_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d+)?\b")


def ok(note):
    w = len(note.split())
    return 60 <= w <= 190 and not CODE_RE.search(note)


def do_batch(batch, bi):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": build_user(batch)}]
    for attempt in range(3):
        # glm-5p3 is thinking-only; reasoning_effort "low" cuts hidden tokens from ~600/note to ~1/note
        r = fw.chat(GEN_MODEL, msgs, max_tokens=4000, temperature=0.8, tag=f"gen-b{bi}",
                    extra={"reasoning_effort": "low"})
        notes = parse(r["content"])
        if notes and len(notes) == len(batch):
            out = []
            for row, n in zip(batch, notes):
                note = (n.get("note") or "").strip()
                out.append(dict(row, text=note, ok=ok(note)))
            print(f"batch {bi}: ok={sum(o['ok'] for o in out)}/{len(out)} reasoning={r['reasoning_tokens']} out={r['out_tokens']} ${r['cost']:.4f}", flush=True)
            return out
        print(f"batch {bi}: parse failed (attempt {attempt}), finish={r['finish_reason']}", flush=True)
    return [dict(row, text="", ok=False) for row in batch]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "data", "all.jsonl"))
    ap.add_argument("--limit_batches", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    rows = sample_labels(rng, args.n)
    batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
    if args.limit_batches:
        batches = batches[: args.limit_batches]
    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(lambda t: do_batch(t[1], t[0]), enumerate(batches)))
    flat = [r for b in results for r in b]
    with open(args.out, "w") as f:
        for r in flat:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(flat)} rows, {sum(r['ok'] for r in flat)} ok, ledger ${fw.ledger_total():.3f}")


if __name__ == "__main__":
    main()
