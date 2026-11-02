#!/bin/bash
# Offline: rebuild routing, variance, chart and tables from the clean (*_retry.json) files. No API calls.
cd "$(dirname "$0")"; R=results
python3 route.py --small $R/glm-5p3-flash_v1_plain_retry.json --large $R/glm-5p3_v1_plain_retry.json --signal verify
python3 route.py --small $R/glm-5p3-flash_v1_plain_conf_retry.json --large $R/glm-5p3_v1_plain_retry.json --signal self --thresholds 50,70,90,100
python3 route.py --small $R/glm-5p3-flash_v1_plain_retry.json --large $R/glm-5p3_v1_plain_retry.json --signal tokens --thresholds 300,600,1200
python3 variance.py $R/glm-5p3-flash_v1_plain_retry.json $R/glm-5p3-flash_v1_plain_seed1_retry.json $R/glm-5p3-flash_v1_plain_seed2_retry.json
python3 variance.py $R/glm-5p3-flash_v1_plain_5shot_retry.json $R/glm-5p3-flash_v1_plain_5shot_seed1_retry.json $R/glm-5p3-flash_v1_plain_5shot_seed2_retry.json
python3 chart.py $R/nemotron-lightning-3p5-30b-a3b_v1_plain_retry.json $R/glm-5p3-flash_v1_plain_retry_3seeds.json $R/gpt-oss-120b_v1_plain_retry.json $R/deepseek-v4p1-flash_v1_plain_retry.json $R/glm-5p3_v1_plain_retry.json $R/kimi-k3_v1_plain_n100_retry.json $R/glm-5p3-flash_v2_rubric_retry.json $R/glm-5p3-flash_v1_plain_5shot_retry_3seeds.json $R/glm-5p3-flash_v1_plain_json_rescored.json $R/glm-5p3-flash_v1_plain_conf_retry.json $R/ROUTE_glm-5p3-flash_to_glm-5p3_v1_plain_retry_route_verify.json $R/ROUTE_glm-5p3-flash_to_glm-5p3_v1_plain_retry_route_tokens_1200.json $R/ROUTE_glm-5p3-flash_to_glm-5p3_v1_plain_retry_route_tokens_600.json $R/ROUTE_glm-5p3-flash_to_glm-5p3_v1_plain_retry_route_tokens_300.json $R/ROUTE_glm-5p3-flash_to_glm-5p3_v1_plain_conf_retry_route_self_90.json
python3 compare.py --md $R/*_v1_plain_retry.json $R/kimi-k3_v1_plain_n100_retry.json $R/glm-5p3-flash_v1_plain_retry_3seeds.json $R/glm-5p3-flash_v2_rubric_retry.json $R/glm-5p3-flash_v1_plain_5shot_retry.json $R/glm-5p3-flash_v1_plain_5shot_retry_3seeds.json $R/glm-5p3-flash_v1_plain_json.json $R/glm-5p3-flash_v1_plain_json_rescored.json $R/glm-5p3-flash_v1_plain_conf_retry.json $R/ROUTE_*retry*.json > $R/table_clean.md
echo "ledger total: $(python3 -c "import run_eval; print(round(run_eval.ledger_total(),4))")"
