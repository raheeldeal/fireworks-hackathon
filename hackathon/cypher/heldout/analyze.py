"""Tables + paired bootstrap for HELDOUT.md. No API calls."""
import json, os, random
HERE = os.path.dirname(os.path.abspath(__file__)); CY = os.path.dirname(HERE)
L = lambda p: json.load(open(p))
M = [("glm-5p3-flash (default reasoning)", "glm-5p3-flash.json", "glm-5p3-flash_v1_plain_n200.json"),
     ("Muse Glimmer 30B base", "muse_base.json", "train_base.json"),
     ("Muse Glimmer + SFT (cypher-sft-1150)", "muse_sft.json", "train_sft.json"),
     ("Muse Glimmer + SFT + RFT (cypher-r1rej-1204)", "muse_sft_rft.json", "train_rft_r1_reject.json"),
     ("kimi-k3 (frontier)", "kimi-k3_n50.json", "kimi-k3_v1_plain_n100.json")]
H = {k: L(os.path.join(HERE, "results", h)) for _, h, _ in M for k in [h]}
V = {m: L(os.path.join(CY, "results_v2", m)) for _, _, m in M}
print("| model | n held-out | held-out (gameofthrones) | main exam n | main exam | delta (pts) |\n|---|---|---|---|---|---|")
for name, h, m in M:
    a, b = H[h], V[m]
    print(f"| {name} | {a['n']} | {a['accuracy']:.1%} | {b['n']} | {b['accuracy_v2']:.1%} | {100*(a['accuracy']-b['accuracy_v2']):+.1f} |")
print("\nfirst 50 held-out rows (kimi's slice):")
for name, h, m in M:
    rs = H[h]["rows"][:50]; print(f"  {name}: {sum(r['correct'] for r in rs)/len(rs):.0%}")
print("\nper tier (held-out, score_v2):\n| model | easy | medium | hard |\n|---|---|---|---|")
for name, h, m in M:
    t = H[h]["by_tier_v2"]
    print(f"| {name} | " + " | ".join(f"{t[k]['accuracy_v2']:.0%} (n={t[k]['n']})" if k in t else "-" for k in ("easy", "medium", "hard")) + " |")

def boot(a, b, B=10000, seed=0):
    ids = sorted(set(a) & set(b)); d = [a[i] - b[i] for i in ids]; n = len(d)
    rng = random.Random(seed); obs = sum(d) / n; s = []
    for _ in range(B):
        s.append(sum(d[rng.randrange(n)] for _ in range(n)) / n)
    s.sort(); p = 2 * min(sum(x <= 0 for x in s), sum(x >= 0 for x in s)) / B
    wins = sum(x > 0 for x in d); losses = sum(x < 0 for x in d)
    return n, obs, s[int(.025*B)], s[int(.975*B)], min(p, 1.0), wins, losses
corr = lambda d: {r["id"]: int(r["correct"]) for r in d["rows"]}
print("\npaired bootstrap (10,000 resamples, two-sided):")
for lab, x, y, src in [("SFT vs base, held-out", H["muse_sft.json"], H["muse_base.json"], "held"),
                       ("SFT+RFT vs base, held-out", H["muse_sft_rft.json"], H["muse_base.json"], "held"),
                       ("SFT+RFT vs SFT, held-out", H["muse_sft_rft.json"], H["muse_sft.json"], "held"),
                       ("SFT vs glm-5p3-flash, held-out", H["muse_sft.json"], H["glm-5p3-flash.json"], "held"),
                       ("SFT vs base, main 200", V["train_sft.json"], V["train_base.json"], "main")]:
    n, o, lo, hi, p, w, l = boot(corr(x), corr(y))
    print(f"  {lab}: n={n} diff {100*o:+.1f} pts, 95% CI [{100*lo:+.1f}, {100*hi:+.1f}], p={p:.3f}, rows only A right {w}, only B right {l}")
