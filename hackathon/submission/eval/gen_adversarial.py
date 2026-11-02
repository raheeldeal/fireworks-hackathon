#!/usr/bin/env python3
"""Generate adversarial.jsonl: 30 gold-first rows written by glm-5p3 (the same generator as the locked set,
never a model under evaluation at the small tier).

Gold-first: sample the gold tool FIRST (seeded), then ask the generator for one request that needs exactly that
tool. The label is therefore never model-chosen. Four styles, ~8 rows each, cycled over the sampled tools:
  near_miss     the request must rule out a named same-server sibling by one concrete detail
  two_plausible both the gold and a named rival look plausible until one context clue decides
  sloppy        typos, missing punctuation, lowercase, abbreviations
  non_native    written by a non-native English speaker with a few grammar slips

Spend is logged to eval/ledger.csv (cap $2.00). Rerun: python3 gen_adversarial.py [--n 30] [--seed 2026] [--fill]  (--fill regenerates only ids missing from the file)
"""
import argparse, json, os, random, re, sys, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import fw
fw.LEDGER = os.path.join(HERE, "ledger.csv")
fw.CAP = 2.00

GEN_MODEL = "accounts/fireworks/models/glm-5p3"
STYLES = {
    "near_miss": "Write it so a careless reader would pick the RIVAL tool, but one concrete detail in the request makes the TARGET the only correct choice. Do not use the catalog's action verb for the target.",
    "two_plausible": "Write it so both TARGET and RIVAL are plausible at first read; include exactly one context clue (what the user already has, what they want to end up with, or where it must happen) that decides for the TARGET.",
    "sloppy": "Write it the way a rushed person types on a phone: at least three typos, no capitalisation, little punctuation, an abbreviation or two. Still must need the TARGET and not the RIVAL.",
    "non_native": "Write it as a non-native English speaker would, with two or three natural grammar slips (articles, tense, word order) and no typos. Still must need the TARGET and not the RIVAL.",
}
SYS = "You write realistic user requests for testing an AI assistant's tool routing. Output strictly valid JSON."


def prompt(tool, rival, others, style):
    neigh = "\n".join(f"- {t['name']}: {t['description']}" for t in others)
    return f"""TARGET TOOL (the request must need exactly this tool):
- {tool['name']}: {tool['description']}

RIVAL TOOL (the request must clearly NOT be solvable by this one):
- {rival['name']}: {rival['description']}

OTHER TOOLS the request must also not need:
{neigh}

Style: {STYLES[style]}

Write ONE user request: a single message a real person would type to an assistant, 12 to 45 words. It must require the TARGET tool and not the RIVAL or any other tool, and must not contain the tool name or the server name literally (saying "GitHub" is fine, saying "create_issue" is not).

Return JSON: {{"request": "..."}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=os.path.join(HERE, "adversarial.jsonl"))
    ap.add_argument("--fill", action="store_true", help="keep rows already in --out, generate only the missing ids")
    args = ap.parse_args()
    existing = {}
    if args.fill and os.path.exists(args.out):
        existing = {r["id"]: r for r in (json.loads(l) for l in open(args.out) if l.strip())}

    cat = json.load(open(os.path.join(HERE, "..", "data", "catalog.json")))
    by_server = {}
    for t in cat:
        by_server.setdefault(t["server"], []).append(t)
    rng = random.Random(args.seed)
    tools = rng.sample(cat, args.n)                      # gold sampled first
    styles = list(STYLES)
    plan = []
    for k, tool in enumerate(tools):
        sib = [t for t in by_server[tool["server"]] if t["name"] != tool["name"]]
        rival = rng.choice(sib) if sib else rng.choice([t for t in cat if t is not tool])
        others = rng.sample([t for t in cat if t["server"] != tool["server"]], 3) + [t for t in sib if t is not rival][:2]
        if f"adv{k:03d}" not in existing:
            plan.append((k, tool, rival, others, styles[k % len(styles)]))

    def gen(item):
        k, tool, rival, others, style = item
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": prompt(tool, rival, others, style)}]
        for attempt in range(3):
            r = fw.chat(GEN_MODEL, msgs, max_tokens=600, temperature=0.8, note=f"adv:{style}",
                        extra={"reasoning_effort": "low", "response_format": {"type": "json_object"}})
            txt = re.sub(r"^```(json)?|```$", "", r["content"].strip()).strip()
            try:
                req = json.loads(txt)["request"].strip()
                low = req.lower()
                suffix = tool["name"].split(".")[1]
                leaked = tool["name"].lower() in low or ("_" in suffix and suffix in low)   # "create_issue" leaks; "click" is plain English
                if 12 <= len(req.split()) <= 60 and not leaked:
                    return {"id": f"adv{k:03d}", "text": req, "label": tool["name"], "style": style, "rival": rival["name"]}
                print("rejected", tool["name"], req[:60], file=sys.stderr)
            except Exception as e:
                print("parse fail", tool["name"], str(e)[:80], file=sys.stderr)
        return None

    rows = list(existing.values())
    with cf.ThreadPoolExecutor(4) as ex:
        for out in ex.map(gen, plan):
            if out:
                rows.append(out); print(out["style"][:9].ljust(10), out["label"].ljust(30), out["text"][:70])
    rows.sort(key=lambda r: r["id"])
    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} rows to {args.out}; ledger ${fw.ledger_total():.4f}")


if __name__ == "__main__":
    main()
