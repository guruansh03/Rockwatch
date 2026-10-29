# Ablations — region A, split val

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.030 | 0.0112 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |
| rain+susc | 0.052 | 0.0082 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |
| rain+susc+thermal | 0.052 | 0.0082 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |
| rain+susc+thermal+seismic | 0.053 | 0.0074 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |
| full | 0.057 | 0.0053 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |
| full (LLM-Verifier off) | 0.057 | 0.0053 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |
| full + LLM-Verifier | 0.057 | 0.0053 | 1.000 | 1.000 | 0.600 | 0.040 | 0.750 | 0.133 | 1.000 |

LLM-Verifier: provider mock / mock-rules-v1; candidates 21980; provider calls 500 (cap 500); outcomes {'ok': 500}; decisions {'FALLBACK_CAP': 21480, 'CONFIRM': 499, 'DOWNGRADE': 1}; levels changed 66.

