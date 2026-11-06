# Ablations — region Y, split val

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.200 | 0.0621 | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.000 | 1.000 |
| rain+susc | 0.200 | 0.0621 | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.000 | 1.000 |
| rain+susc+thermal | 0.214 | 0.0409 | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.000 | 1.000 |
| rain+susc+thermal+seismic | 0.216 | 0.0406 | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.000 | 1.000 |
| full | 0.212 | 0.0370 | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.000 | 1.000 |

LLM-Verifier off for this run (`--llm on` adds full ± verifier rows; same split, same cache).

