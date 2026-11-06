# Ablations — region A, split val

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.012 | 0.0118 | 0.350 | 0.370 | 0.045 | 0.022 | 0.079 | 5.602 | 0.193 |
| rain+susc | 0.048 | 0.0306 | 0.264 | 0.300 | 0.085 | 0.050 | 0.132 | 2.877 | 0.063 |
| rain+susc+thermal | 0.048 | 0.0311 | 0.239 | 0.275 | 0.089 | 0.050 | 0.135 | 2.754 | 0.057 |
| rain+susc+thermal+seismic | 0.050 | 0.0275 | 0.368 | 0.429 | 0.090 | 0.044 | 0.149 | 4.344 | 0.104 |
| full | 0.053 | 0.0251 | 0.406 | 0.429 | 0.123 | 0.047 | 0.191 | 1.866 | 0.105 |

LLM-Verifier off for this run (`--llm on` adds full ± verifier rows; same split, same cache).

