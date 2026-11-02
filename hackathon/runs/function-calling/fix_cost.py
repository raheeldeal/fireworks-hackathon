"""Recompute total_cost_usd / cost_per_1k for result files written with the short-name price bug (decision 12)."""
import json, sys, glob
from run_eval import PRICING
for p in sys.argv[1:] or glob.glob("results/*_mt4096*.json"):
    if p.startswith("results/route_"): continue
    r = json.load(open(p))
    if r.get("total_cost_usd", 0) > 0 or "rows" not in r: continue
    pin, pout = PRICING["accounts/fireworks/models/" + r["model"].split("/")[-1]]
    r["total_cost_usd"] = round((r["in_tokens"] * pin + r["out_tokens"] * pout) / 1e6, 5)
    r["cost_per_1k_requests_usd"] = round(r["total_cost_usd"] / r["n"] * 1000, 4)
    r["cost_note"] = "recomputed from token counts (short-name price bug)"
    json.dump(r, open(p, "w"))
    print(p, r["total_cost_usd"], r["cost_per_1k_requests_usd"])
