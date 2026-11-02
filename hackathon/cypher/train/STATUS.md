# cypher/train status

Updated ~12:25 PT. **Done. No training running, no RFT round 2.** Details and diagnosis: `TRAIN.md`. Deploy: `DEPLOY.md`.

| config | file | accuracy | error | empty | in/out tok per call |
|---|---|---|---|---|---|
| base | results/train_base.json | 48.5% | 2.0% | 4.0% | 841 / 48.6 |
| SFT (headline), 3 runs | results/train_sft.json, _seed1, _seed2 | 56.5 / 57.0 / 56.5% | 0.5% | 1.0% | 841 / 44.3 |
| SFT, pruned schema | results/train_sft_pruned.json | 54.5% | 0.0% | 2.0% | 668 / 43.9 |
| RFT r1 advantage-weighted | results/train_rft_r1.json | 32.5% | 7.5% | 14.5% | 841 / 50.1 |
| RFT r1 rejection sampling | results/train_rft_r1_reject.json | 57.5% | 0.5% | 2.5% | 841 / 42.6 |
| RFT r2 | not run (budget, and the coordinator asked for a diagnosis first) | | | | |

- Weighted RFT regression: caused by unbounded negative-weight cross-entropy (REINFORCE with no ratio, clip or KL), not by prompt mismatch, sample count, a cold start, or degenerate rewards. See TRAIN.md.
- Training sessions: SFT, r1 and r1-reject were each deleted right after saving (all show EXPIRED). Promoted models READY: `cypher-sft-1150`, `cypher-r1-1201`, `cypher-r1rej-1204`.
- Leftover: 13 sampler-only sessions from this run's eval/sample clients (state UNSPECIFIED, created 19:42Z to 20:05Z). Per the docs these hold no training slot. My delete call was blocked by the permission classifier; a human can delete them.
- Incidents: first r1 sampling crashed at reward time (train rows had no stored gold rows; fixed, ~$1.29 of samples lost). The r2 sampling run from the weighted model was stopped at 150/316 questions ($0.43 wasted).
- Spend: $5.569 of $6.00 (ledger.csv). Training $0.
