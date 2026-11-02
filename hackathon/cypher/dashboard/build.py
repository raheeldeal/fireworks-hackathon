"""Build dashboard/index.html from results/*.json, results/train/*.json and ledger.csv.

  python dashboard/build.py          # run from hackathon/cypher/ after any run; the page is self-contained

Each row of the ablation table (HARNESS.md section 8) is one (result file, stage) pair: a full-harness run is read at
several stages (metrics.cut), so one run supplies several rows. Rows whose file doesn't exist yet are skipped.
"""
import csv, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import metrics  # noqa: E402

# id, label, family, result file (results/<tag>.json), stage to read it at, not citable (chosen on the test set)
CONFIGS = [
    ("R1", "Base model, no harness", "harness", "r1_base", "first", False),
    ("R2", "+ retrieved examples", "harness", "r5_full", "first", False),
    ("R3", "+ arrow fix", "harness", "r5_full", "fix", False),
    ("R4", "+ repair loop", "harness", "r5_full", "repair", False),
    ("R5", "+ escalate to Kimi K3", "harness", "r5_full", "escalate", False),
    ("R5w", "R5 + repair on DB warnings", "harness", "r5w_full", "escalate", False),
    ("R6a", "FT1: SFT on gold, examples only", "finetune", "r6_ft1", "first", False),
    ("R6", "FT1: SFT on gold + harness", "finetune", "r6_ft1", "escalate", False),
    ("R6z", "FT1, no retrieved examples", "finetune", "r6z_ft1_noshots", "escalate", False),
    ("R7d", "FT-D: distilled (Muse + gpt-oss + glm verified)", "finetune", "r7_ftd", "escalate", False),
    ("R6b", "FT1-big: SFT on 4,386 gold + harness", "finetune", "r6b_ft1big", "escalate", False),
    ("R6bx", "FT-BX: 4,386 gold + 2,114 other-graph gold", "finetune", "r6bx_ftbx", "escalate", False),
    ("R6bxa", "FT-BX, examples only (no repair/escalation)", "finetune", "r6bx_ftbx", "first", False),
    ("R6kd", "FT-KD: FT1 gold + Kimi K3 answers where Muse failed", "finetune", "r6kd_ftkd", "escalate", False),
    ("R6hf", "FT-HF: FT1 gold, trace-flagged failures doubled", "finetune", "r6hf_fthf", "escalate", False),
    ("R7", "FT2: SFT on traces", "finetune", "r7_ft2", "escalate", False),
    ("R8", "FT3: traces + repairs", "finetune", "r8_ft3", "escalate", False),
    ("R9", "FT4: self-improving round 2", "finetune", "r9_ft4", "escalate", False),
    ("R11", "FT6: RL, execution reward", "finetune", "r11_ft6", "escalate", False),
    ("R12", "Qwen 3.6 35B A3B, best recipe", "small", "r12_small", "escalate", False),
    ("R13", "gpt-oss-120b + harness", "small", "r13_gptoss", "repair", False),
    ("R13e", "gpt-oss-120b + harness + escalate", "small", "r13_gptoss", "escalate", False),
    ("R15", "glm-5p3 + harness", "small", "r15_glm", "repair", False),
    ("R16", "Vote: R6 + R15 + R13 by result rows", "small", "r16_vote3", "first", False),
    ("R17", "Kimi K3 (2.8T) + harness", "small", "r17_kimi", "repair", False),
    ("R23", "Kimi K3 (2.8T), zero-shot, no harness", "small", "r23_kimi_plain", "first", False),
    ("R22", "Qwen2.5 1.5B, untuned, local + examples + fix", "small", "r22_qwen15", "fix", False),
    ("R18", "Vote: R6 + R6b + Kimi K3 by result rows", "finetune", "r18_vote_ft", "first", False),
    ("R19", "Vote R6+R6b+R6z (PICKED ON TEST, not citable)", "finetune", "r19_vote_muse", "first", True),
    ("R20", "Vote of 4 Muse 30B adapters, picked on dev", "finetune", "r20_vote_devpick", "first", False),
]
# Design experiments on the dev split (200 train questions, never the test set). Each is (group, label, file, stage).
DEV = [
    ("Retrieval: keyword vs embedding (FT1 model)", "keyword top 3", "dev_ft1_keyword3", "escalate"),
    ("Retrieval: keyword vs embedding (FT1 model)", "keyword top 5", "dev_ft1_keyword5", "escalate"),
    ("Retrieval: keyword vs embedding (FT1 model)", "keyword top 10", "dev_ft1_keyword10", "escalate"),
    ("Retrieval: keyword vs embedding (FT1 model)", "embedding top 3", "dev_ft1_embed3", "escalate"),
    ("Retrieval: keyword vs embedding (FT1 model)", "embedding top 5", "dev_ft1_embed5", "escalate"),
    ("Retrieval: keyword vs embedding (FT1 model)", "embedding top 10", "dev_ft1_embed10", "escalate"),
    ("Examples in context (untuned Muse 30B, no repair)", "0 examples", "dev_base_k0", "first"),
    ("Examples in context (untuned Muse 30B, no repair)", "keyword top 3", "dev_base_keyword3", "first"),
    ("Examples in context (untuned Muse 30B, no repair)", "keyword top 5", "dev_base_keyword5", "first"),
    ("Examples in context (untuned Muse 30B, no repair)", "keyword top 10", "dev_base_keyword10", "first"),
    ("Examples in context (untuned Muse 30B, no repair)", "embedding top 3", "dev_base_embed3", "first"),
    ("Examples in context (untuned Muse 30B, no repair)", "embedding top 5", "dev_base_embed5", "first"),
    ("Examples in context (untuned Muse 30B, no repair)", "embedding top 10", "dev_base_embed10", "first"),
    ("Teacher bake-off (harness, no escalation)", "Kimi K3", "dev_teacher_kimi-k3", "repair"),
    ("Teacher bake-off (harness, no escalation)", "glm-5p3", "dev_teacher_glm-5p3", "repair"),
    ("Teacher bake-off (harness, no escalation)", "deepseek-v4p1-flash", "dev_teacher_deepseek-v4p1-flash", "repair"),
    ("Teacher bake-off (harness, no escalation)", "gpt-oss-120b", "dev_teacher_gpt-oss-120b", "repair"),
    ("Teacher bake-off (harness, no escalation)", "Muse 30B (R5 config)", "dev_r5w", "escalate"),
    ("Example pool (gpt-oss-120b)", "500-row pool, top 3", "dev_teacher_gpt-oss-120b", "repair"),
    ("Example pool (gpt-oss-120b)", "4,586-row pool, top 3", "dev_gptoss_pool3", "repair"),
    ("Example pool (gpt-oss-120b)", "4,586-row pool, top 5", "dev_gptoss_pool5", "repair"),
]

# CypherBench held-out exam (cypherbench/README.md): 100 questions on 2 graphs never seen in training, same harness and
# scorer. Each is (result file, display name, group, main-test config id with the same setup or None if not run there).
CYPHERBENCH = [
    ("cb_r1_base", "Muse 30B, untuned, plain", "ours", "R1"),
    ("cb_r5_full", "Muse 30B + harness", "ours", "R5"),
    ("cb_r6_ft1", "Muse 30B + SFT (1.5k gold) + harness", "ours", "R6"),
    ("cb_r6bx_ftbx", "Muse 30B + SFT (6.5k gold) + harness", "ours", "R6bx"),
    ("cb_kimi-k3", "Kimi K3 2.8T, plain", "open", "R23"),
    ("cb_glm-5p3-flash", "GLM 5.3 flash, plain", "open", None),
    ("cb_deepseek-v4p1-flash", "DeepSeek V4.1 flash, plain", "open", None),
]

# Published reference (CypherGuard, arxiv.org/html/2610.41755; Neo4j Text2Cypher audited subset, n=1,003).
REFERENCES = [{"label": "Claude Sonnet 4.6, zero-shot (published)", "accuracy": 0.5663},
              {"label": "Claude Sonnet 4.6 + CypherGuard (published)", "accuracy": 0.6251}]
SONNET_PRICE = (3.00, 15.00)  # $/M in/out, Anthropic list price for claude-sonnet-4-6; used only for an estimate


def load(tag):
    path = os.path.join(ROOT, "results", f"{tag}.json")
    return json.load(open(path)) if os.path.exists(path) else None


def explorer_rows(doc, stage):
    out = []
    for r in doc["rows"]:
        c = metrics.cut(r, stage)
        keep = [a for a in r["attempts"] if metrics.STAGES.index(metrics.stage_of(a["source"])) <= metrics.STAGES.index(stage)]
        out.append({"id": r["id"], "graph": r["graph"], "tier": r["tier"], "question": r["question"],
                    "gold": r["gold_cypher"], "final": c.get("cypher"), "outcome": c["outcome"], "stage": c["stage"],
                    "trace": r.get("langfuse_trace_id"),
                    "attempts": [{"source": a["source"], "status": a["status"], "outcome": a.get("outcome"),
                                  "cypher": a["cypher"], "error": (a.get("error") or "")[:240],
                                  "warnings": [w[:160] for w in a.get("warnings", [])], "n_rows": a["n_rows"]}
                                 for a in keep]})
    return out


def grid(doc, stage):
    """Accuracy by graph x tier."""
    cells = defaultdict(list)
    for r in doc["rows"]:
        cells[(r["graph"], r["tier"])].append(metrics.cut(r, stage)["outcome"] == "correct")
    return {f"{g}|{t}": {"acc": sum(v) / len(v), "n": len(v)} for (g, t), v in cells.items()}


def sonnet_cost_estimate(doc):
    """What one first-attempt call would cost at Sonnet 4.6 list price, using our own prompt and output sizes."""
    firsts = [r["attempts"][0] for r in doc["rows"] if r["attempts"]]
    tin = sum(a["in_tokens"] for a in firsts) / len(firsts)
    tout = sum(a["out_tokens"] for a in firsts) / len(firsts)
    return (tin * SONNET_PRICE[0] + tout * SONNET_PRICE[1]) / 1e6


def spend():
    path = os.path.join(ROOT, "ledger.csv")
    by = defaultdict(float)
    if os.path.exists(path):
        for row in csv.DictReader(open(path)):
            by[row["note"].split(" ")[0] or "other"] += float(row["cost"])
    return {"total": sum(by.values()), "cap": 45.0, "credits": 50.0, "by_tag": dict(sorted(by.items()))}


def training_logs():
    folder = os.path.join(ROOT, "results", "train")
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        info = json.load(open(os.path.join(folder, name)))
        out.append({"tag": info["tag"], "examples": info["examples"], "epochs": info["epochs"],
                    "points": [[p["step"], p["mean_nll"]] for p in info["log"] if p.get("mean_nll") is not None]})
    return out


def waterfall_steps():
    """The waterfall of dashboard/waterfall.py, with the questions each step fixed and broke.

    For every step: the accuracy before and after, and per question that changed, the query and rows on each side
    plus both Langfuse trace ids. Uses the same START and STEPS as waterfall.png, so the tab and the image agree."""
    import waterfall as wf  # dashboard/waterfall.py
    test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(ROOT, "data", "test.jsonl"))}

    def run(tag, stage):
        doc = load(tag)
        return {r["id"]: (r, metrics.cut(r, stage)) for r in doc["rows"]} if doc else None

    def side(row, cut):
        a = next((a for a in reversed(row["attempts"]) if a["cypher"] == cut.get("cypher")), None)
        return {"cypher": cut.get("cypher"), "outcome": cut["outcome"], "stage": cut["stage"],
                "rows": (a or {}).get("preview", [])[:3], "n_rows": (a or {}).get("n_rows", 0),
                "trace": row.get("langfuse_trace_id")}

    def changed(before, after):
        out = {"fixed": [], "broke": []}
        for i in sorted(before):
            b_ok, a_ok = before[i][1]["outcome"] == "correct", after[i][1]["outcome"] == "correct"
            if b_ok != a_ok:
                t = test[i]
                out["fixed" if a_ok else "broke"].append({
                    "id": i, "graph": t["graph"], "tier": t["complexity"]["tier"], "question": t["question"],
                    "gold": t["cypher"], "gold_rows": t["gold_result"]["rows"][:3],
                    "before": side(*before[i]), "after": side(*after[i])})
        return out

    acc = lambda r: 100 * sum(c["outcome"] == "correct" for _, c in r.values()) / len(r)
    current = run(*wf.START[1:])
    steps = [{"label": wf.START[0], "kind": "start", "value": acc(current)}]
    for label, tag, stage, adopted, compare_with in wf.STEPS:
        new = run(tag, stage)
        if not new:
            continue
        ref = run(*compare_with) if compare_with else current
        d = changed(ref, new)
        steps.append({"label": label, "kind": "step" if adopted else "tried", "from": acc(ref), "to": acc(new),
                      "n_fixed": len(d["fixed"]), "n_broke": len(d["broke"]), **d})
        if adopted:
            current = new
    steps.append({"label": "Overall: best system", "kind": "total", "value": acc(current)})
    refs = [{"label": "Frontier: Claude Sonnet 4.6, zero-shot (published)", "value": wf.FRONTIER}]
    kimi = run("r23_kimi_plain", "first")
    if kimi:
        refs.append({"label": "Frontier, run by us: Kimi K3 2.8T, zero-shot", "value": acc(kimi)})
    return {"steps": steps, "frontier": wf.FRONTIER, "refs": refs}


def cypherbench():
    """Held-out exam rows: accuracy at every stage the run has, plus the same setup on the main test for comparison."""
    tags = {cid: (tag, stage) for cid, _, _, tag, stage, _ in CONFIGS}
    out = []
    for tag, name, group, main_id in CYPHERBENCH:
        doc = load(tag)
        if not doc:
            continue
        stages = list(doc["views"])
        s = metrics.summarize(doc["rows"], stages[-1])
        row = {"tag": tag, "name": name, "group": group,
               "stages": {st: metrics.summarize(doc["rows"], st)["accuracy"] for st in stages},
               **{k: s[k] for k in ("accuracy", "ci95", "n", "cost_per_question", "p50_secs", "by_graph", "by_tier")}}
        main_doc = load(tags[main_id][0]) if main_id else None
        if main_doc:
            m = metrics.summarize(main_doc["rows"], tags[main_id][1])
            row["main"] = {"id": main_id, "accuracy": m["accuracy"], "ci95": m["ci95"],
                           "stages": {st: metrics.summarize(main_doc["rows"], st)["accuracy"] for st in stages if st in main_doc["views"]}}
        out.append(row)
    return out


def main():
    configs = []
    for cid, label, family, tag, stage, not_citable in CONFIGS:
        doc = load(tag)
        if not doc or doc["split"] != "test" or stage not in doc["views"]:
            continue
        s = metrics.summarize(doc["rows"], stage)
        configs.append({"id": cid, "label": label, "family": family, "tag": tag, "stage": stage, "model": doc["model"],
                        "citable": not not_citable,
                        **{k: s[k] for k in ("accuracy", "ci95", "n", "cost_per_question", "cost_per_correct",
                                             "calls_per_question", "p50_secs", "p90_secs", "by_stage", "outcomes")},
                        "grid": grid(doc, stage), "rows": explorer_rows(doc, stage)})
    if not configs:
        sys.exit("no test-split results yet")
    refs = [dict(r) for r in REFERENCES]
    base = load("r5_full")
    if base:
        refs[0]["cost_per_question_est"] = sonnet_cost_estimate(base)
    trace_prefix = None
    if os.environ.get("LANGFUSE_BASE_URL") and os.environ.get("LANGFUSE_PROJECT_ID"):
        trace_prefix = f"{os.environ['LANGFUSE_BASE_URL']}/project/{os.environ['LANGFUSE_PROJECT_ID']}/traces/"
    dev = []
    for group, label, tag, stage in DEV:
        doc = load(tag)
        if doc and stage in doc["views"]:
            v = metrics.summarize(doc["rows"], stage)
            dev.append({"group": group, "label": label, "accuracy": v["accuracy"], "ci95": v["ci95"],
                        "cost_per_question": v["cost_per_question"], "p50_secs": v["p50_secs"], "n": v["n"]})
    data = {"configs": configs, "references": refs, "dev": dev, "spend": spend(), "training": training_logs(),
            "waterfall": waterfall_steps(), "cypherbench": cypherbench(),
            "trace_prefix": trace_prefix, "graphs": ["movies", "recommendations", "northwind", "fincen", "twitter"],
            "tiers": ["easy", "medium", "hard"]}
    template = open(os.path.join(HERE, "template.html")).read()
    blob = json.dumps(data, default=str).replace("</", "<\\/")  # safe inside a <script> tag
    out = os.path.join(HERE, "index.html")
    open(out, "w").write(template.replace("/*__DATA__*/null", blob))
    print(f"wrote {os.path.relpath(out, ROOT)}: {len(configs)} configs, spend ${data['spend']['total']:.2f}")


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    from run_eval import load_env
    load_env()
    main()
