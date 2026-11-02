#!/bin/bash
# 3 seeds (shuffled order, temperature 0) for a model+prompt. Usage: scripts/variance.sh <model id> <prompt path> [--json-mode]
cd "$(dirname "$0")/.."; for s in 1 2 3; do python3 run_eval.py --model "$1" --prompt "$2" --seed $s $3; done
