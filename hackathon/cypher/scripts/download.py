from datasets import load_dataset
import collections, sys
name = sys.argv[1]
ds = load_dataset(name)
print(ds)
for split in ds:
    ds[split].to_json(f"raw/{name.split('/')[-1]}_{split}.jsonl")
    c = collections.Counter(ds[split]["database_reference_alias"])
    print(split, c.most_common(25))
