"""Append phase-7 (Muse Glimmer SFT) results to RESULTS.md once the run completes."""
import json, csv, pathlib, datetime
root = pathlib.Path(__file__).resolve().parent.parent
rows = []
for label in ("base", "tuned"):
    p = root / f"results/muse-glimmer-30b_{label}_s7.json"
    if not p.exists():
        continue
    r = json.load(open(p))
    rows.append(f"| muse-glimmer-30b {label} (serverless sampler, {len(r['rows'])} rows) | {r['accuracy']*100:.1f}% | {r['mean_field_accuracy']*100:.1f}% | {r['invalid_outputs']} | {r.get('p50_latency_s', 0):.2f} s | ${r['cost_per_1k_requests_usd']:.3f} |")
spend = sum(float(x["cost"]) for x in csv.DictReader(open(root / "ledger.csv")))
block = "\n## Phase 7 addendum (auto-appended %s PT)\nMuse Glimmer 30B LoRA SFT completed on the serverless training slot. Training $0 (promotion); sampler tokens are in ledger.csv. Total spend now $%.2f.\n\n| Run | All-fields | Mean field | Invalid | p50 | $/1k |\n|---|---|---|---|---|---|\n%s\n" % (
    datetime.datetime.now().strftime("%H:%M"), spend, "\n".join(rows))
with open(root / "RESULTS.md", "a") as f:
    f.write(block)
print(block)
