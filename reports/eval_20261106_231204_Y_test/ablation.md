# Ablations — region Y, split test

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.200 | 0.1175 | 0.312 | 0.425 | 0.579 | 0.313 | 0.490 | 9.628 | 0.269 |
| rain+susc | 0.200 | 0.1175 | 0.312 | 0.425 | 0.579 | 0.313 | 0.490 | 9.628 | 0.269 |
| rain+susc+thermal | 0.214 | 0.1337 | 0.263 | 0.362 | 0.679 | 0.339 | 0.473 | 5.416 | 0.209 |
| rain+susc+thermal+seismic | 0.216 | 0.1420 | 0.237 | 0.338 | 0.680 | 0.345 | 0.451 | 4.814 | 0.186 |
| full | 0.212 | 0.1375 | 0.163 | 0.250 | 0.538 | 0.246 | 0.341 | 7.221 | 0.194 |
| full (LLM-Verifier off) | 0.212 | 0.1375 | 0.163 | 0.250 | 0.538 | 0.246 | 0.341 | 7.221 | 0.194 |
| full + LLM-Verifier | 0.212 | 0.1375 | 0.138 | 0.237 | 0.433 | 0.231 | 0.307 | 10.229 | 0.178 |

LLM-Verifier: provider groq / openai/gpt-oss-20b; candidates 83; provider calls 80 (cap 80); outcomes {'ok': 35, 'ok_after_retry': 1, 'fallback_error': 43, 'fallback_cap': 1}; decisions {'FALLBACK_CAP': 3, 'DOWNGRADE': 12, 'CONFIRM': 24, 'FALLBACK': 44}; levels changed 26.

