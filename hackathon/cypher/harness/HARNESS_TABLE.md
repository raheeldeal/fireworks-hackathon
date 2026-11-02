| config | n | accuracy | lenient | error/invalid | empty | p50 s | p95 s | $/1k | calls/row | escalation |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline glm-5p3-flash (default reasoning, BASELINES.md run) | 200 | 57.0% | 69.5% | 0.5% | 0.5% | 1.624 | 4.308 | $0.241 | 1 | - |
| plain_rdefault | 200 | 52.5% | 66.0% | 1.0% | 1.5% | 1.625 | 4.664 | $0.235 | 1.0 | - |
| plain (same run, reasoning low, no gate) | 200 | 48.0% | - | 1.5% | 2.5% | 1.069 | 1.723 | $0.148 | 1 | - |
| validate_only | 200 | 48.0% | 58.5% | 3.0% | 1.5% | 1.069 | 1.723 | $0.148 | 1.0 | - |
| repair1 | 200 | 50.0% | 62.0% | 0.5% | 1.0% | 1.063 | 2.311 | $0.157 | 1.05 | - |
| vote3 | 200 | 52.0% | 65.5% | 0.0% | 0.0% | 1.243 | 4.9 | $0.474 | 3.175 | - |
| route_big | 200 | 55.0% | 67.5% | 0.0% | 0.0% | 1.151 | 5.824 | $0.771 | 3.26 | 6.0% |
| prune_repair1 | 200 | 47.5% | 60.0% | 0.5% | 2.5% | 0.937 | 2.117 | $0.131 | 1.055 | - |
| repair1_fewshot | 200 | 52.0% | 63.0% | 0.0% | 0.0% | 0.93 | 2.385 | $0.161 | 1.065 | - |
| route_big_u | 200 | 50.5% | 66.0% | 0.5% | 0.0% | 1.218 | 22.273 | $1.895 | 3.525 | 31.5% |
| repair1_rdefault | 200 | 53.0% | 66.5% | 0.0% | 0.0% | 1.699 | 6.22 | $0.252 | 1.03 | - |
| vote3_rdefault | 200 | 52.0% | 64.5% | 0.0% | 0.0% | 1.966 | 8.113 | $0.779 | 3.095 | - |
| route_big_u_rdefault | 200 | 50.5% | 65.0% | 0.5% | 0.0% | 2.329 | 21.105 | $2.324 | 3.44 | 32.5% |

Repeated runs (seed label only; the model is sampled fresh each run):

| config | runs | mean accuracy | range | mean lenient | mean error+empty | mean $/1k |
|---|---|---|---|---|---|---|
| repair1_rdefault | 3 | 53.3% | 53.0% to 54.0% | 66.2% | 0.3% | $0.263 |
| plain_rdefault | 3 | 53.0% | 52.5% to 54.0% | 65.2% | 2.2% | $0.240 |
| route_big | 4 | 51.9% | 50.0% to 55.0% | 65.1% | 0.1% | $0.874 |
| vote3 | 3 | 51.7% | 49.5% to 53.5% | 64.2% | 0.2% | $0.479 |

| config | easy | medium | hard |
|---|---|---|---|
| plain_rdefault | 47.1% | 56.3% | 53.5% |
| plain (low) | 42.9% | 54.0% | 44.2% |
| validate_only | 42.9% | 54.0% | 44.2% |
| repair1 | 42.9% | 57.5% | 46.5% |
| vote3 | 44.3% | 56.3% | 55.8% |
| route_big | 44.3% | 60.9% | 60.5% |
| prune_repair1 | 44.3% | 52.9% | 41.9% |
| repair1_fewshot | 42.9% | 60.9% | 48.8% |
| route_big_u | 42.9% | 56.3% | 51.2% |
| repair1_rdefault | 45.7% | 58.6% | 53.5% |
| vote3_rdefault | 41.4% | 57.5% | 58.1% |
| route_big_u_rdefault | 40.0% | 55.2% | 58.1% |

First-call prompt tokens: 168297 full vs 132784 pruned (21.1% saved over 200 rows; 158 rows pruned, the rest fell back to the full schema).
