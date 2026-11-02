"""Eval Protocol evaluator for managed RFT: same reward as tune.py (correct tool x length factor).

NOT RUN TODAY: dataset uploads are disabled on this account (HTTP 403), and docs.fireworks.ai says managed RFT is deprecated
in favour of the Training API. The RFT numbers in results/ come from tune.py (rejection sampling on the same reward).
If uploads are enabled on a teammate's account:

    pip install eval-protocol
    cd submission/train
    ep local-test                       # runs this file with pytest against data/rft_prompts.jsonl (needs FIREWORKS_API_KEY)
    eval-protocol create rft \
      --base-model accounts/fireworks/models/muse-glimmer-30b \
      --chunk-size 10                   # add --force to re-upload after edits; see `firectl rftj create --help` for epochs / lora rank

Dataset rows (data/rft_prompts.jsonl): {"messages": [{"role":"system","content":"Reply with the single best tool name."},
                                                      {"role":"user","content":"<request>"}], "ground_truth": "<tool name>"}
"""
import os
import sys

from eval_protocol.models import EvaluateResult, EvaluationRow
from eval_protocol.pytest import default_single_turn_rollout_processor, evaluation_test

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import score  # submission/score.py: deterministic, unit-tested parser (handles think blocks, JSON wrappers, case)

MAX_SHORT_TOKENS = 8


def reward(reply: str, gold: str, out_tokens: int) -> float:
    """1.0 if the top-1 parsed tool equals the gold tool else 0.0, times 1.0 if the reply is <= 8 tokens else 0.5."""
    correct = score.score(reply, gold)["top1"]
    length_factor = 1.0 if out_tokens <= MAX_SHORT_TOKENS else 0.5
    return (1.0 if correct else 0.0) * length_factor


@evaluation_test(
    input_dataset=[os.path.join(HERE, "data", "rft_prompts.jsonl")],
    completion_params=[{"model": "accounts/fireworks/models/muse-glimmer-30b", "temperature": 0.8, "max_tokens": 32}],
    rollout_processor=default_single_turn_rollout_processor,
    mode="pointwise",
)
def test_tool_routing(row: EvaluationRow) -> EvaluationRow:
    reply = (row.messages[-1].content or "") if row.messages else ""
    gold = row.ground_truth or ""
    # Token count: use the usage the gateway reports when present, else a whitespace-split proxy (tool names are 1 "word").
    usage = getattr(row, "usage", None)
    out_tokens = getattr(usage, "completion_tokens", None) or len(reply.split())
    s = reward(reply, gold, out_tokens)
    row.evaluation_result = EvaluateResult(score=s, reason=f"pred={score.score(reply, gold)['pred']} gold={gold} out_tokens={out_tokens}")
    return row
