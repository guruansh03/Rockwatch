# Ablations — region Y, split val

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.200 | 0.1175 | 0.375 | 0.512 | 0.490 | 0.280 | 0.501 | 11.617 | 0.272 |
| rain+susc | 0.200 | 0.1175 | 0.375 | 0.512 | 0.490 | 0.280 | 0.501 | 11.617 | 0.272 |
| rain+susc+thermal | 0.214 | 0.1337 | 0.275 | 0.400 | 0.450 | 0.305 | 0.424 | 10.223 | 0.192 |
| rain+susc+thermal+seismic | 0.216 | 0.1420 | 0.287 | 0.400 | 0.541 | 0.351 | 0.460 | 7.900 | 0.170 |
| full | 0.212 | 0.1375 | 0.325 | 0.475 | 0.575 | 0.329 | 0.520 | 7.900 | 0.209 |

LLM-Verifier off for this run (`--llm on` adds full ± verifier rows; same split, same cache).

