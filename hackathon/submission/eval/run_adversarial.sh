#!/usr/bin/env bash
# Score any model on adversarial.jsonl with the same prompt, scorer and JSON output shape as ../run_eval.py.
#   ./run_adversarial.sh <model> [extra run_eval.py args...]
#   ./run_adversarial.sh glm-5p3-flash
#   ./run_adversarial.sh nemotron-lightning-3p5-30b-a3b --reasoning none
#   ./run_adversarial.sh accounts/<acct>/models/<tuned-lora> --prompt ../prompts/v1_plain.txt
# Output: results_adversarial/<model>__<tag>__s0.json  (then: python3 tier_report.py is for the locked set only;
# use `python3 -c` below or compare.py on the adversarial file). Spend is logged to eval/ledger.csv, cap $2.
set -euo pipefail
cd "$(dirname "$0")"
MODEL="${1:?usage: run_adversarial.sh <model> [run_eval args]}"; shift || true
[ -n "${FIREWORKS_API_KEY:-}" ] || source ~/.zshrc
SHORT="${MODEL##*/}"
mkdir -p results_adversarial
python3 - "$MODEL" "$@" <<'EOF'
import os, sys
here = os.path.dirname(os.path.abspath("run_adversarial.sh"))
sys.path.insert(0, os.path.join(here, ".."))
import fw
fw.LEDGER = os.path.join(here, "ledger.csv"); fw.CAP = 2.00
import run_eval
model, extra = sys.argv[1], sys.argv[2:]
argv = ["run_eval.py", "--model", model, "--data", os.path.join(here, "adversarial.jsonl")]
if "--prompt" not in extra: argv += ["--prompt", os.path.join(here, "..", "prompts", "v1_plain.txt")]
if "--out" not in extra: argv += ["--out", os.path.join(here, "results_adversarial", model.split("/")[-1] + "__adv__s0.json")]
sys.argv = argv + extra
run_eval.main()
EOF
OUT="results_adversarial/${SHORT}__adv__s0.json"
python3 - "$OUT" <<'EOF'
import json, sys, collections
d = json.load(open(sys.argv[1]))
style = {json.loads(l)["id"]: json.loads(l)["style"] for l in open("adversarial.jsonl")}
t = collections.defaultdict(lambda: [0, 0])
for r in d["rows"]:
    s = style.get(r["id"], "?"); t[s][0] += bool(r["correct"]); t[s][1] += 1
print(f"\nadversarial accuracy by style ({d['model'].split('/')[-1]}):")
for s, (k, n) in sorted(t.items()):
    print(f"  {s:14s} {k}/{n} = {k/n:.0%}")
print(f"  {'all':14s} {sum(v[0] for v in t.values())}/{d['n']} = {d['accuracy']:.1%}")
EOF
