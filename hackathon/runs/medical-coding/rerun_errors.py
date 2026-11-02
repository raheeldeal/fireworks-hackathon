"""Re-run only the rows whose call errored (finish_reason == 'error') in a results file and patch it in place."""
import json, os, sys
import fw, run_eval
path, model, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
max_tokens = int(sys.argv[5]) if len(sys.argv) > 5 else 2048
d = json.load(open(path))
sp = run_eval.build_system(prompt, os.path.join(run_eval.HERE, "data", "train.jsonl"), seed=d.get("seed", 7))
bad = [i for i, r in enumerate(d["rows"]) if r.get("finish_reason") == "error"]
print("re-running", len(bad), "rows")
for i in bad:
    ex = {"id": d["rows"][i]["id"], "text": d["rows"][i]["text"], "codes": d["rows"][i]["label"]}
    d["rows"][i] = run_eval.run_one(model, sp, ex, max_tokens, extra, f"rerun_{fw.SHORT[model]}")
new = run_eval.summarize(model, d["prompt"], d["rows"], {k: d[k] for k in ("seed", "extra", "wall_s", "data") if k in d})
json.dump(new, open(path, "w"), indent=2)
print(f"F1 {new['accuracy']:.3f} exact {new['exact_accuracy']:.3f} invalid {new['invalid_outputs']}")
