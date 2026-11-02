#!/usr/bin/env python3
"""Recompute the cumulative improvement ladder from the per-question result files and write ladder.json.

The result files live in the team fork (github.com/vishwajeet-hogale/fireworks-hackathon, commit 22ab54a,
hackathon/cypher/results/ and data/test_audit.jsonl). Point --data at a folder holding:
  r1_base.json r5_full.json r6_ft1.json r6bx_ftbx.json r7_ftd.json r6kd_ftkd.json r6hf_fthf.json
  r20_vote_devpick.json test_audit.jsonl
  python3 build_ladder.py --data <folder>

A harness run records every attempt in stage order (first -> fix -> repair -> escalate) at temperature 0, so one
full run, cut at each stage, gives the accuracy of a harness that stopped there. This mirrors metrics.cut in the
fork. Every step is compared with the step before it on the same questions (paired bootstrap, 95% CI).
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[sys.argv.index("--data") + 1] if "--data" in sys.argv else os.path.join(HERE, "data")
STAGES = ["first", "fix", "repair", "escalate"]

def stage_of(src):
    return "escalate" if src.startswith("escalate:") else ("repair" if src.startswith("repair") else src)

def cut(row, upto):
    keep = [a for a in row["attempts"] if STAGES.index(stage_of(a["source"])) <= STAGES.index(upto)]
    if not keep:
        return {"outcome": row.get("outcome", "error"), "cost": 0.0}
    clean = [a for a in keep if a["status"] == "rows"]
    warned = [a for a in keep if a["status"] == "warn"]
    final = (clean or warned or keep)[-1]
    return {"outcome": final["outcome"], "cost": sum(a["cost"] for a in keep), "status": final["status"]}

def load(tag, stage):
    doc = json.load(open(os.path.join(DATA, f"{tag}.json")))
    out = {}
    for r in doc["rows"]:
        c = cut(r, stage)
        out[r["id"]] = {"ok": c["outcome"] == "correct", "cost": c["cost"], "q": r["question"],
                        "tier": r["tier"], "graph": r["graph"], "trace": r.get("langfuse_trace_id")}
    return out

def paired(a, b, n_boot=10000, seed=0):
    ids = sorted(set(a) & set(b))
    d = [int(b[i]["ok"]) - int(a[i]["ok"]) for i in ids]
    rng = random.Random(seed)
    boot = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n_boot))
    lo, hi = boot[int(0.025 * n_boot)], boot[int(0.975 * n_boot) - 1]
    return {"diff": 100 * sum(d) / len(d), "lo": 100 * lo, "hi": 100 * hi,
            "significant": lo > 0 or hi < 0, "gained": d.count(1), "lost": d.count(-1)}

def acc(x, ids=None):
    ids = ids or list(x)
    return 100 * sum(x[i]["ok"] for i in ids) / len(ids)

AUDIT = {}
for line in open(os.path.join(DATA, "test_audit.jsonl")):
    r = json.loads(line); AUDIT[r["id"]] = r["label"]

START = ("Untuned open model", "Muse Glimmer 30B", "r1_base", "first")
ADOPTED = [  # (short label, what it is, file, stage)
    ("Retrieved examples", "3 similar solved questions in the prompt", "r5_full", "first"),
    ("Arrow-direction fix", "flip relationship arrows the schema says are backwards", "r5_full", "fix"),
    ("Repair loop", "feed the database error back, retry", "r5_full", "repair"),
    ("Escalate to Kimi K3", "hand the hardest cases to a bigger open model", "r5_full", "escalate"),
    ("SFT", "LoRA fine-tune on 1.5k execution-verified examples", "r6_ft1", "escalate"),
    ("More SFT data", "+ 9 other graphs, 6.5k examples", "r6bx_ftbx", "escalate"),
]
TRIED = [  # (label, file, stage, compared with (file, stage))
    ("RFT-style (own verified answers) instead of SFT", "r7_ftd", "escalate", ("r6_ft1", "escalate")),
    ("Teacher distillation from Kimi K3", "r6kd_ftkd", "escalate", ("r6_ft1", "escalate")),
    ("Hard examples x2", "r6hf_fthf", "escalate", ("r6_ft1", "escalate")),
    ("Vote of 4 adapters", "r20_vote_devpick", "first", ("r6bx_ftbx", "escalate")),
]

def ladder(fair_only):
    pick = (lambda x: {i: v for i, v in x.items() if AUDIT.get(i) not in ("gold_wrong", "ambiguous")}) if fair_only else (lambda x: x)
    cur = pick(load(*START[2:]))
    steps = [{"label": START[0], "detail": START[1], "acc": acc(cur), "kind": "start",
              "cost_per_1k": 1000 * sum(v["cost"] for v in cur.values()) / len(cur)}]
    for label, detail, tag, stage in ADOPTED:
        new = pick(load(tag, stage))
        p = paired(cur, new)
        ex = [new[i] for i in sorted(new) if new[i]["ok"] and not cur.get(i, {}).get("ok", True)]
        steps.append({"label": label, "detail": detail, "acc": acc(new), "kind": "step", **p,
                      "cost_per_1k": 1000 * sum(v["cost"] for v in new.values()) / len(new),
                      "examples": [{"q": e["q"], "tier": e["tier"], "graph": e["graph"], "trace": e["trace"]} for e in ex[:6]]})
        cur = new
    final = cur
    tried = []
    for label, tag, stage, (rt, rs) in TRIED:
        ref, new = pick(load(rt, rs)), pick(load(tag, stage))
        tried.append({"label": label, "acc": acc(new), "ref_acc": acc(ref), **paired(ref, new)})
    misses = [i for i in final if not final[i]["ok"]]
    why = {"gold_wrong": 0, "ambiguous": 0, "format_only": 0, "model_wrong": 0}
    for i in misses:
        lab = AUDIT.get(i)
        why[lab if lab in why else "model_wrong"] += 1
    return {"n": len(final), "steps": steps, "tried": tried, "final_acc": acc(final),
            "misses": len(misses), "miss_reasons": why}

out = {"source": "github.com/vishwajeet-hogale/fireworks-hackathon@22ab54a hackathon/cypher/results",
       "frontier_reference": {"label": "Claude Sonnet 4.6", "acc": 56.63,
                              "note": "published zero-shot number on another subset (CypherGuard, arxiv.org/html/2610.41755); reference only"},
       "audit_counts": {k: list(AUDIT.values()).count(k) for k in set(AUDIT.values())},
       "all200": ladder(False), "fair175": ladder(True)}
json.dump(out, open(os.path.join(HERE, "ladder.json"), "w"), indent=1)
for key in ("all200", "fair175"):
    L = out[key]
    print(f"\n== {key}  n={L['n']}")
    for s in L["steps"]:
        extra = "" if s["kind"] == "start" else f"  {s['diff']:+.1f} [{s['lo']:+.1f},{s['hi']:+.1f}] {'SIG' if s['significant'] else 'ns'}  +{s['gained']}/-{s['lost']}"
        print(f"  {s['label']:22s} {s['acc']:5.1f}%  ${s['cost_per_1k']:.2f}/1k{extra}")
    for t in L["tried"]:
        print(f"  tried: {t['label']:45s} {t['acc']:5.1f} vs {t['ref_acc']:5.1f}  {t['diff']:+.1f} {'SIG' if t['significant'] else 'ns'}")
    print("  misses:", L["misses"], L["miss_reasons"])
print("\naudit labels:", out["audit_counts"])
