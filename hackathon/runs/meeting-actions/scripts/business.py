#!/usr/bin/env python3
"""BUSINESS.md table from results: 50k meetings/day, 3.6 items/meeting. Picks the key configurations."""
import glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER_DAY, ITEMS = 50_000, 3.6
MONTH = PER_DAY * 30
want = [("nemotron-lightning-3p5-30b-a3b_v1_plain", "nemotron 30B-A3B, plain"), ("glm-5p3-flash_v1_plain", "glm-5p3-flash, plain"),
        ("glm-5p3-flash_v4_fewshot", "glm-5p3-flash, rubric + 5-shot (best small)"), ("deepseek-v4p1-flash_v1_plain", "deepseek-v4p1-flash, plain (best overall)"),
        ("route_glm-5p3-flash_deepseek-v4p1-flash_v3_rubric_conf_t0.9", "routing flash -> deepseek, thr 0.9"),
        ("glm-5p3_v1_plain", "glm-5p3 (large), plain"), ("kimi-k3_v1_plain", "kimi-k3 (frontier), plain, n=70")]
print("| config | F1 | $/1k meetings | $/month | item errors / month | p50 s |")
print("|---|---|---|---|---|---|")
for fn, label in want:
    p = os.path.join(ROOT, "results", fn + ".json")
    if not os.path.exists(p): continue
    d = json.load(open(p))
    cost_month = d["cost_per_1k_requests_usd"] / 1000 * MONTH
    errors = (1 - d["f1"]) * MONTH * ITEMS
    print(f"| {label} | {d['f1']:.3f} | {d['cost_per_1k_requests_usd']:.3f} | ${cost_month:,.0f} | {errors:,.0f} | {d['p50_latency_s']:.2f} |")
