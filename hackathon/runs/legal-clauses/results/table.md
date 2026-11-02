| config | model | n | accuracy | macro-F1 | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|---|
| v1_plain nothink80 | kimi-k3 | 80 | 73.8% | 68.5% | 0 | 1.03 | 3.58 | 7.244 | 1 |
| routing t0.95 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 69.3% | 64.9% | 1 | 0.82 | 1.55 | 0.606 | 1 |
| v4_json nothink | glm-5p3-flash | 199 | 68.8% ± 0.5% | 64.6% ± 0.6% | 0 | 0.58 ± 0.01 | 1.05 ± 0.13 | 0.363 | 3 |
| v1_plain nothink | deepseek-v4p1-flash | 199 | 68.8% | 64.5% | 1 | 0.66 | 1.20 | 0.704 | 1 |
| v5_short sft | muse-glimmer-30b-lora | 199 | 68.8% | 64.7% | 0 | 0.66 | 2.37 | 0.959 | 1 |
| routing t0.7 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 68.8% | 65.0% | 1 | 0.93 | 1.87 | 0.702 | 1 |
| routing t0.99 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 68.8% | 64.5% | 1 | 1.28 | 2.10 | 1.045 | 1 |
| routing t0.95 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 68.3% | 63.9% | 1 | 1.22 | 2.00 | 0.956 | 1 |
| routing t0.9 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 68.3% | 63.7% | 1 | 0.79 | 1.48 | 0.546 | 1 |
| routing t0.99 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 68.3% | 63.7% | 1 | 0.92 | 1.90 | 0.772 | 1 |
| routing t0.5 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 67.8% | 63.7% | 0 | 0.62 | 1.75 | 0.517 | 1 |
| routing t0.9 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 67.8% | 63.4% | 1 | 1.18 | 2.00 | 0.889 | 1 |
| routing t0.5 | route(glm-5p3-flash->glm-5p3) | 199 | 67.3% | 63.2% | 0 | 0.62 | 1.51 | 1.108 | 1 |
| v1_plain | glm-5p3-flash | 199 | 66.8% ± 0.5% | 63.2% ± 0.6% | 0 | 0.54 ± 0.04 | 1.05 ± 0.05 | 0.358 | 3 |
| v3_fewshot nothink | glm-5p3-flash | 199 | 66.8% | 62.9% | 0 | 0.56 | 0.98 | 0.426 | 1 |
| routing t0.7 | route(glm-5p3-flash->glm-5p3) | 199 | 66.8% | 62.0% | 0 | 0.94 | 1.64 | 1.974 | 1 |
| v1_plain nothink | glm-5p3 | 199 | 66.3% | 61.2% | 0 | 0.55 | 0.88 | 3.315 | 1 |
| routing t0.9 | route(glm-5p3-flash->glm-5p3) | 199 | 66.3% | 61.2% | 0 | 1.11 | 1.66 | 2.857 | 1 |
| routing t0.95 | route(glm-5p3-flash->glm-5p3) | 199 | 66.3% | 61.2% | 0 | 1.15 | 1.74 | 3.174 | 1 |
| routing t0.99 | route(glm-5p3-flash->glm-5p3) | 199 | 66.3% | 61.2% | 0 | 1.18 | 1.74 | 3.590 | 1 |
| routing t0.9 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 65.8% | 60.7% | 0 | 0.74 | 1.24 | 2.107 | 1 |
| routing t0.95 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 65.8% | 60.6% | 0 | 0.76 | 1.39 | 2.390 | 1 |
| routing t0.99 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 65.8% | 60.7% | 0 | 0.80 | 1.54 | 3.173 | 1 |
| routing t0.7 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 63.8% | 58.5% | 1 | 0.37 | 1.41 | 0.386 | 1 |
| v2_rubric nothink | glm-5p3-flash | 199 | 63.3% | 59.6% | 0 | 0.61 | 1.21 | 0.536 | 1 |
| routing t0.7 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 62.8% | 57.3% | 0 | 0.37 | 1.22 | 1.357 | 1 |
| routing t0.5 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 61.3% | 55.4% | 1 | 0.29 | 1.26 | 0.241 | 1 |
| routing t0.5 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 60.8% | 54.9% | 0 | 0.29 | 1.11 | 0.674 | 1 |
| v3_fewshot nothink | nemotron-lightning-3p5-30b-a3b | 199 | 59.8% | 54.3% | 0 | 0.29 | 1.74 | 0.149 | 1 |
| v1_plain | gpt-oss-120b | 199 | 57.8% | 52.3% | 0 | 0.36 | 0.69 | 0.378 | 1 |
| v1_plain nothink | nemotron-lightning-3p5-30b-a3b | 199 | 56.8% | 51.1% | 1 | 0.24 | 0.90 | 0.125 | 1 |
| v2_rubric nothink | nemotron-lightning-3p5-30b-a3b | 199 | 56.3% | 51.8% | 5 | 0.28 | 1.51 | 0.187 | 1 |
| v4_json nothink | nemotron-lightning-3p5-30b-a3b | 199 | 55.8% | 50.0% | 1 | 0.31 | 1.65 | 0.126 | 1 |
| v1_plain | nemotron-lightning-3p5-30b-a3b | 199 | 33.2% | 33.1% | 104 | 4.97 | 7.08 | 0.458 | 1 |

Spend: $2.32 inference, $0.00 training (free promotion), $0.19 tuned-model sampling (from ledger.csv, 3697 calls)

## Misses of glm-5p3-flash_v4_json_nothink_s7 (61 of 199)
- 2x gold **Assigns** -> predicted **Successors**: "This Agreement shall be binding upon and shall inure to the benefit of the Company and Employee and their resp..."
- 2x gold **Consent To Jurisdiction** -> predicted **Submission To Jurisdiction**: "EACH ORIGINATOR HEREBY IRREVOCABLY SUBMITS TO THE NON-EXCLUSIVE JURISDICTION OF ANY UNITED STATES FEDERAL OR I..."
- 2x gold **Applicable Laws** -> predicted **Governing Laws**: "The terms and conditions of this Agreement will be interpreted under the laws of the state of Minnesota, exclu..."
- 2x gold **Authorizations** -> predicted **Authority**: "Borrower shall have taken all appropriate corporate action to authorize, and its directors, if and as required..."
- 1x gold **Costs** -> predicted **Expenses**: "The Company shall bear all expenses associated with administering the Plan, including expenses of issuing Comm..."
- 1x gold **Jurisdictions** -> predicted **Consent To Jurisdiction**: "Subject to the proviso below, the parties agree that the Bankruptcy Court shall have exclusive and continuing ..."
- 1x gold **Qualifications** -> predicted **Existence**: "The Company is a corporation duly organized, validly existing and in good standing under the laws of the State..."
- 1x gold **Expenses** -> predicted **Death**: "Notwithstanding the provisions of Section 7.4 hereof, the personal representative of Grantee may, within two (..."
- 1x gold **Insurances** -> predicted **Closings**: "The Administrative Agent shall have received insurance certificates and endorsements satisfying the requiremen..."
- 1x gold **Binding Effects** -> predicted **Effectiveness**: "This Amendment shall not be valid and binding on Landlord and Tenant unless and until it has been completely e..."
- 1x gold **Agreements** -> predicted **Entire Agreements**: "This Agreement embodies the complete agreement and understanding among the parties hereto and supersedes and p..."
- 1x gold **Litigations** -> predicted **Notices**: "As soon as possible and in any event within five (5) Business Days after an Authorized Officer of any Credit P..."
