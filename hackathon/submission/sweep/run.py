#!/usr/bin/env python3
"""Sweep runner: wraps ../run_eval.py so the ledger lives in sweep/ledger.csv (cap $5) and results in sweep/results/.
Usage: python3 run.py --model M --prompt ../prompts/v1_plain.txt [run_eval args...]  (--out is set automatically from --tag)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SUB = os.path.dirname(HERE)
sys.path.insert(0, SUB)
import fw
fw.LEDGER = os.path.join(HERE, "ledger.csv"); fw.CAP = 5.00
import run_eval
argv = sys.argv[1:]
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
if "--out" not in argv:
    model = arg("--model").split("/")[-1]; tag = arg("--tag"); seed = arg("--seed", "0")
    if not tag: sys.exit("pass --tag")
    argv += ["--out", os.path.join(HERE, "results", f"{model}__{tag}__s{seed}.json")]
sys.argv = ["run_eval.py"] + argv
run_eval.main()
