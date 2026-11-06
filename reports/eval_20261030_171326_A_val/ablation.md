# Ablations — region A, split val

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.023 | 0.0242 | 0.299 | 0.326 | 0.082 | 0.040 | 0.131 | 8.756 | 0.233 |
| rain+susc | 0.050 | 0.0473 | 0.250 | 0.260 | 0.167 | 0.119 | 0.203 | 1.790 | 0.059 |
| rain+susc+thermal | 0.050 | 0.0473 | 0.250 | 0.263 | 0.176 | 0.119 | 0.211 | 1.790 | 0.059 |
| rain+susc+thermal+seismic | 0.052 | 0.0471 | 0.248 | 0.273 | 0.177 | 0.119 | 0.215 | 1.956 | 0.060 |
| full | 0.055 | 0.0516 | 0.244 | 0.260 | 0.182 | 0.122 | 0.214 | 1.381 | 0.058 |

LLM-Verifier off for this run (`--llm on` adds full ± verifier rows; same split, same cache).

