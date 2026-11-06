# Ablations — region A, split test

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.012 | 0.0118 | 0.318 | 0.363 | 0.035 | 0.014 | 0.064 | 6.616 | 0.188 |
| rain+susc | 0.048 | 0.0306 | 0.257 | 0.285 | 0.064 | 0.035 | 0.104 | 3.298 | 0.061 |
| rain+susc+thermal | 0.048 | 0.0311 | 0.241 | 0.276 | 0.064 | 0.036 | 0.104 | 3.172 | 0.056 |
| rain+susc+thermal+seismic | 0.050 | 0.0275 | 0.399 | 0.434 | 0.064 | 0.037 | 0.112 | 4.583 | 0.094 |
| full | 0.053 | 0.0251 | 0.447 | 0.469 | 0.092 | 0.035 | 0.154 | 2.137 | 0.111 |
| full (LLM-Verifier off) | 0.053 | 0.0251 | 0.447 | 0.469 | 0.092 | 0.035 | 0.154 | 2.137 | 0.111 |
| full + LLM-Verifier | 0.053 | 0.0251 | 0.447 | 0.469 | 0.092 | 0.035 | 0.154 | 2.137 | 0.111 |

LLM-Verifier: provider groq / openai/gpt-oss-20b; candidates 10806; provider calls 80 (cap 80); outcomes {'fallback_guardrail': 14, 'ok': 25, 'ok_after_retry': 13, 'fallback_cap': 28}; decisions {'FALLBACK_CAP': 10726, 'FALLBACK': 42, 'CONFIRM': 37, 'DOWNGRADE': 1}; levels changed 3.

