"""Turn verified data into SFT files: one JSON line = {id, question, graph, source, messages, answer}.

  python build_sft.py gold    --rows data/harvest1.jsonl                          --out data/sft_ft1_gold.jsonl
  python build_sft.py traces  --rows data/harvest1.jsonl --results results/harvest1.json --out data/sft_ft2_traces.jsonl
  python build_sft.py repairs --rows data/harvest1.jsonl --results results/harvest1.json --out data/sft_ft3_repairs.jsonl
  python build_sft.py gold    --rows data/train_pool.jsonl --exclude data/dev.jsonl         --out data/sft_ft1big_gold.jsonl
  python build_sft.py distill --rows data/harvest1.jsonl --results results/harvest1.json results/harvest1_gptoss.json \
                              results/harvest1_glm.json --out data/sft_ftd_distill.jsonl

gold     FT1. The dataset's gold query as the answer to the harness's first prompt.
traces   FT2. Only questions the harness solved: its final, execution-verified query becomes the answer to the
         *first* prompt, so the model learns to get it right without repair calls.
repairs  FT3. FT2's examples plus the repair turns that led to a correct query
         (first prompt -> wrong query -> database feedback -> fixed query).
teacher  FT-KD extra data. --results <student run> <teacher run>: the teacher's verified query, only on questions
         the student's run did *not* solve (FT-D showed that answers the student already gets right teach little).
distill  FT-D. Rejection-sampling distillation from several harness runs (the student's own and teachers'): for each
         question, the verified query from the first run, in the order given, whose answer matched gold.

Every prompt is built with harness.build_messages and the same example pool as test time, so train and test prompts
match. The leak check refuses to write a file if any question or answer also appears in data/test.jsonl.
"""
import argparse, json, os, sys

from harness import build_messages
from retrieve import Retriever

HERE = os.path.dirname(os.path.abspath(__file__))


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def norm(text):
    return " ".join(text.split()).lower()


def example(row, messages, answer, source):
    return {"id": row["id"], "question": row["question"], "graph": row["graph"], "source": source,
            "messages": messages, "answer": answer}


def gold(rows, retriever, shots):
    for r in rows:
        shots_ = retriever.top(r["question"], r["graph"], shots, exclude_ids={r["id"]})
        yield example(r, build_messages(r, shots_), r["cypher"], "gold")


def traces(rows, results, retriever, with_repairs):
    by_id = {r["id"]: r for r in rows}
    pool = {e["id"]: e for graph in retriever.by_graph.values() for e, _ in graph}
    for res in results["rows"]:
        if res["outcome"] != "correct":
            continue
        row = by_id[res["id"]]
        first = build_messages(row, [pool[i] for i in res["examples"]])  # the exact prompt the harness used
        yield example(row, first, res["final_cypher"], "trace")
        if not with_repairs:
            continue
        # Replay the loop that produced the correct query, if it got there through repairs.
        winner = next(a for a in reversed(res["attempts"]) if a["cypher"] == res["final_cypher"])
        if not winner["source"].split(":")[-1].startswith("repair"):
            continue  # solved first time or by the arrow fix: no repair turn to learn from
        escalated = winner["source"].startswith("escalate:")
        loop = [a for a in res["attempts"] if a["model"] and a["source"].startswith("escalate:") == escalated]
        messages = list(first)
        for a in loop[: loop.index(winner)]:  # the model's earlier tries in this loop, with the feedback it got
            messages += [{"role": "assistant", "content": a["output"]}, {"role": "user", "content": a["feedback"]}]
        yield example(row, messages, winner["cypher"], "repair")


def distill(rows, runs, retriever):
    """One example per question that at least one run solved; earlier runs win ties."""
    by_id = {r["id"]: r for r in rows}
    pool = {e["id"]: e for graph in retriever.by_graph.values() for e, _ in graph}
    taken = set()
    for run in runs:
        for res in run["rows"]:
            if res["outcome"] == "correct" and res["id"] not in taken:
                taken.add(res["id"])
                row = by_id[res["id"]]
                first = build_messages(row, [pool[i] for i in res["examples"]])
                yield example(row, first, res["final_cypher"], f"distill:{run['model'].split('/')[-1]}")


def teacher(rows, student, teacher_run, retriever):
    """Teacher answers where the teacher was right and the student wrong."""
    solved = {r["id"] for r in student["rows"] if r["outcome"] == "correct"}
    misses = {"split": teacher_run["split"], "model": teacher_run["model"],
              "rows": [r for r in teacher_run["rows"] if r["id"] not in solved]}
    yield from distill(rows, [misses], retriever)


def leak_check(examples, test_path=os.path.join(HERE, "data", "test.jsonl")):
    """Drop (and name) every example whose question or answer text matches a test row.

    The pool already excludes exact test questions and gold queries, but the dataset contains paraphrased duplicates
    across its splits: a train question worded differently can have exactly a test question's answer (seen: p01475).
    """
    test = load_jsonl(test_path)
    test_q, test_c = {norm(r["question"]) for r in test}, {norm(r["cypher"]) for r in test}
    keep = [e for e in examples if norm(e["question"]) not in test_q and norm(e["answer"]) not in test_c]
    dropped = sorted({e["id"] for e in examples} - {e["id"] for e in keep})
    print(f"leak check: dropped {len(examples) - len(keep)} of {len(examples)} examples that match the "
          f"{len(test)}-row test set {dropped}")
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["gold", "traces", "repairs", "distill", "teacher"])
    ap.add_argument("--rows", required=True, help="the train questions (with gold) the data comes from")
    ap.add_argument("--results", nargs="+", help="run_eval.py output(s) on those rows; distill takes several, in priority order")
    ap.add_argument("--examples", default=os.path.join(HERE, "data", "train.jsonl"), help="pool for retrieved shots")
    ap.add_argument("--shots", type=int, default=3)
    ap.add_argument("--exclude", nargs="*", default=[], help="question files to leave out (e.g. data/dev.jsonl)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    excluded = {r["id"] for path in args.exclude for r in load_jsonl(path)}
    rows = [r for r in load_jsonl(args.rows) if r["id"] not in excluded]
    retriever = Retriever(load_jsonl(args.examples))
    if args.kind == "gold":
        out = list(gold(rows, retriever, args.shots))
    else:
        runs = [json.load(open(p)) for p in args.results]
        assert all(r["split"] == "train" for r in runs), "training data may only come from train-split runs"
        if args.kind == "distill":
            out = list(distill(rows, runs, retriever))
        elif args.kind == "teacher":
            out = list(teacher(rows, runs[0], runs[1], retriever))
        else:
            out = list(traces(rows, runs[0], retriever, with_repairs=args.kind == "repairs"))
    out = leak_check(out)
    with open(args.out, "w") as f:
        for e in out:
            f.write(json.dumps(e) + "\n")
    counts = {}
    for e in out:
        counts[e["source"]] = counts.get(e["source"], 0) + 1
    print(f"wrote {args.out}: {len(out)} examples {counts}")


if __name__ == "__main__":
    main()
