| config | model | accuracy | top-3 | invalid | p50 s | p95 s | $/1k | catalog % of cost | seeds |
|---|---|---|---|---|---|---|---|---|---|
| v1_plain | deepseek-v4p1-flash | 98.9% | 98.9% | 1.0 | 0.86 | 1.89 | 0.5893 | 87% | 1 |
| v1_plain | glm-5p3-flash | 98.3% ± 0.6% | 98.3% ± 0.6% | 0.0 | 0.81 | 2.29 | 0.2841 ± 0.0013 | 82% | 3 |
| route@-0.02 | route(glm-5p3-flash->glm-5p3) | 98.9% | - | 0.0 | 0.84 | 2.25 | 0.4544 | - | 1 |
| route@-0.05 | route(glm-5p3-flash->glm-5p3) | 98.9% | - | 0.0 | 0.83 | 2.25 | 0.3785 | - | 1 |
| route@-0.1 | route(glm-5p3-flash->glm-5p3) | 98.9% | - | 0.0 | 0.83 | 2.22 | 0.3369 | - | 1 |
| route@-0.2 | route(glm-5p3-flash->glm-5p3) | 98.9% | - | 0.0 | 0.83 | 2.10 | 0.2960 | - | 1 |
| route@-0.5 | route(glm-5p3-flash->glm-5p3) | 98.9% | - | 0.0 | 0.83 | 2.10 | 0.2960 | - | 1 |
| route@-1.0 | route(glm-5p3-flash->glm-5p3) | 98.9% | - | 0.0 | 0.83 | 2.10 | 0.2828 | - | 1 |
| route@-0.02 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3-flash) | 98.9% | - | 0.0 | 1.05 | 2.82 | 0.3155 | - | 1 |
| v1_plain+5shot | glm-5p3-flash | 98.3% | 98.3% | 0.0 | 0.76 | 1.87 | 0.3137 | 77% | 1 |
| v2_rubric+5shot | glm-5p3-flash | 98.1% ± 0.3% | 98.1% ± 0.3% | 0.0 | 0.80 | 1.89 | 0.3796 ± 0.0010 | 64% | 3 |
| v2_rubric | glm-5p3-flash | 98.3% | 98.3% | 0.0 | 0.88 | 2.34 | 0.3488 | 68% | 1 |
| route@-0.05 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3-flash) | 97.8% | - | 0.0 | 0.88 | 2.53 | 0.2336 | - | 1 |
| route@-0.1 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3-flash) | 97.2% | - | 0.0 | 0.33 | 2.31 | 0.1836 | - | 1 |
| v1_plain+rlow | glm-5p3-flash | 96.7% | 96.7% | 0.0 | 0.56 | 1.12 | 0.2526 | 92% | 1 |
| v4_json | glm-5p3-flash | 96.7% | 96.7% | 0.0 | 0.80 | 2.62 | 0.2953 | 79% | 1 |
| route@-0.02 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 96.1% ± 0.0% | - | 2.0 | 2.43 | 6.28 | 0.9037 ± 0.1592 | - | 2 |
| route@-0.05 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 96.1% ± 0.0% | - | 2.0 | 2.39 | 6.28 | 0.8678 ± 0.1232 | - | 2 |
| route@-0.1 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 96.1% ± 0.0% | - | 2.0 | 2.38 | 6.28 | 0.8602 ± 0.1157 | - | 2 |
| route@-0.2 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 96.1% ± 0.0% | - | 2.0 | 2.38 | 6.28 | 0.8526 ± 0.1233 | - | 2 |
| route@-0.5 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 96.1% ± 0.0% | - | 2.0 | 2.38 | 6.28 | 0.8526 ± 0.1233 | - | 2 |
| route@-1.0 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 96.1% ± 0.0% | - | 2.0 | 2.38 | 6.28 | 0.8526 ± 0.1233 | - | 2 |
| v1_plain | glm-5p3 | 95.6% | 95.6% | 3.0 | 0.92 | 3.68 | 2.7444 | 81% | 1 |
| v1_plain (n=100) | kimi-k3 | 95.0% | 95.0% | 0.0 | 1.52 | 4.02 | 6.1496 | 76% | 1 |
| route@-0.2 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3-flash) | 95.0% | - | 0.0 | 0.26 | 2.02 | 0.1335 | - | 1 |
| route@-0.02 (n=100) | route(nemotron-lightning-3p5-30b-a3b->kimi-k3) | 95.0% | - | 0.0 | 2.94 | 6.86 | 2.4340 | - | 1 |
| route@-0.05 (n=100) | route(nemotron-lightning-3p5-30b-a3b->kimi-k3) | 95.0% | - | 0.0 | 2.89 | 6.86 | 2.1964 | - | 1 |
| route@-0.1 (n=100) | route(nemotron-lightning-3p5-30b-a3b->kimi-k3) | 95.0% | - | 0.0 | 2.85 | 6.86 | 2.1353 | - | 1 |
| route@-0.2 (n=100) | route(nemotron-lightning-3p5-30b-a3b->kimi-k3) | 95.0% | - | 0.0 | 2.85 | 6.86 | 2.1353 | - | 1 |
| route@-0.5 (n=100) | route(nemotron-lightning-3p5-30b-a3b->kimi-k3) | 95.0% | - | 0.0 | 2.85 | 6.86 | 2.1353 | - | 1 |
| route@-1.0 (n=100) | route(nemotron-lightning-3p5-30b-a3b->kimi-k3) | 95.0% | - | 0.0 | 2.85 | 6.86 | 2.1353 | - | 1 |
| v1_plain | gpt-oss-120b | 92.8% | 92.8% | 0.0 | 0.42 | 0.81 | 0.2963 | 77% | 1 |
| route@-0.5 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3-flash) | 92.2% | - | 0.0 | 0.25 | 1.94 | 0.1130 | - | 1 |
| v3_top3 | glm-5p3-flash | 89.4% | 98.9% | 1.0 | 1.56 | 3.22 | 0.3574 | 65% | 1 |
| route@-1.0 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3-flash) | 88.3% | - | 0.0 | 0.24 | 1.53 | 0.0973 | - | 1 |
| v1_plain+5shot | nemotron-lightning-3p5-30b-a3b | 87.8% | 87.8% | 20.0 | 1.83 | 4.05 | 0.2114 | 39% | 1 |
| v2_rubric+rnone | nemotron-lightning-3p5-30b-a3b | 86.7% | 86.7% | 2.0 | 0.24 | 1.03 | 0.1110 | 75% | 1 |
| v1_plain+rnone | nemotron-lightning-3p5-30b-a3b | 86.1% | 86.1% | 0.0 | 0.24 | 1.30 | 0.0874 | 90% | 1 |
| v2_rubric+5shot | nemotron-lightning-3p5-30b-a3b | 83.3% | 83.3% | 27.0 | 2.63 | 5.18 | 0.2558 | 33% | 1 |
| v1_plain | nemotron-lightning-3p5-30b-a3b | 81.7% ± 1.4% | 81.7% ± 1.4% | 30.7 | 2.48 | 5.11 | 0.2164 ± 0.0001 | 34% | 3 |
| v1_plain+retr20 | nemotron-lightning-3p5-30b-a3b | 77.8% | 77.8% | 32.0 | 1.95 | 3.81 | 0.1344 | 12% | 1 |
| v2_rubric | nemotron-lightning-3p5-30b-a3b | 76.1% | 76.1% | 41.0 | 2.67 | 4.88 | 0.2517 | 33% | 1 |
| v1_plain+retr10 | glm-5p3-flash | 70.0% | 70.0% | 17.0 | 0.82 | 6.74 | 0.1295 | 20% | 1 |
| v1_plain+retr10 | nemotron-lightning-3p5-30b-a3b | 67.2% | 67.2% | 48.0 | 2.23 | 4.68 | 0.1347 | 6% | 1 |
| v4_json | nemotron-lightning-3p5-30b-a3b | 60.0% | 60.0% | 70.0 | 2.90 | 5.06 | 0.2497 | 32% | 1 |
| v3_top3 | nemotron-lightning-3p5-30b-a3b | 6.1% | 6.1% | 169.0 | 3.13 | 5.47 | 0.2909 | 28% | 1 |
