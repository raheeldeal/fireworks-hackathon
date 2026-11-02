"""Lock the test set: take the first 180 OK rows of data/all.jsonl as test, the rest as train.
Strips generation metadata. Prints the sha256 so it can be recorded in RESULTS.md."""
import hashlib, json, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "all.jsonl")) if l.strip()]
ok = [r for r in rows if r.get("ok") and r.get("text")]
rng = random.Random(2026)
rng.shuffle(ok)
test, train = ok[:180], ok[180:]
for name, part in (("test", test), ("train", train)):
    with open(os.path.join(HERE, "data", f"{name}.jsonl"), "w") as f:
        for r in part:
            f.write(json.dumps({"id": r["id"], "text": r["text"], "codes": r["codes"]}) + "\n")
print(f"all={len(rows)} ok={len(ok)} test={len(test)} train={len(train)}")
print("test sha256", hashlib.sha256(open(os.path.join(HERE, "data", "test.jsonl"), "rb").read()).hexdigest())
