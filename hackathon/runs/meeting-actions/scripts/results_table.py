#!/usr/bin/env python3
"""Print the RESULTS.md table (markdown) from results/*.json. Seeds are folded into mean ± range."""
import glob, json, os, re, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
runs = {}
for p in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
    if "smoke" in os.path.basename(p): continue
    d = json.load(open(p)); key = (d["model"], d["prompt"]); runs.setdefault(key, []).append(d)
def label(model, prompt):
    m = model.split("/")[-1]
    if m.startswith("route("): return f"routing {m[6:-1]} thr={prompt.split('_thr')[-1]}", m
    return {"v1_plain": "baseline plain prompt", "v2_rubric": "rubric prompt", "v3_rubric_conf": "rubric + confidence",
            "v2_rubric_json": "rubric + JSON mode", "v4_fewshot": "rubric + 5-shot"}.get(prompt, prompt), m
print("| config | model | accuracy (item F1) | P / R | due acc | invalid | p50 s | p95 s | $/1k | seeds |")
print("|---|---|---|---|---|---|---|---|---|---|")
order = ["nemotron", "glm-5p3-flash", "gpt-oss", "deepseek", "glm-5p3", "kimi", "route"]
def rank(k): m = k[0].split("/")[-1]; return next((i for i, o in enumerate(order) if m.startswith(o) or (o == "glm-5p3" and m == "glm-5p3")), 99)
for key in sorted(runs, key=lambda k: (rank(k), k[1])):
    ds = runs[key]; cfg, m = label(*key)
    f1s = [d["f1"] for d in ds]; base = ds[0]
    f1 = f"{statistics.mean(f1s):.3f}" + (f" ± {(max(f1s)-min(f1s))/2:.3f}" if len(ds) > 1 else "")
    n = base["n"]; note = f" (n={n})" if n < 150 else ""
    print(f"| {cfg}{note} | {m} | {f1} | {base['precision']:.3f} / {base['recall']:.3f} | {base['due_acc']:.3f} | {sum(d.get('invalid_outputs', d.get('invalid', 0)) for d in ds)} | {base['p50_latency_s']:.2f} | {base['p95_latency_s']:.2f} | {base['cost_per_1k_requests_usd']:.3f} | {len(ds)} |")
