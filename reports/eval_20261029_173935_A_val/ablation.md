# Ablations — region A, split val

> US natural-slope data; not mine performance; precision is a lower bound (unreported events).

Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.

| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |
|---|---|---|---|---|---|---|---|---|---|
| rain | 0.027 | 0.0252 | 0.655 | 0.719 | 0.100 | 0.045 | 0.176 | 20.012 | 0.588 |
| rain+susc | 0.068 | 0.0298 | 0.685 | 0.693 | 0.351 | 0.086 | 0.466 | 1.496 | 0.305 |
| rain+susc+thermal | 0.068 | 0.0290 | 0.691 | 0.701 | 0.354 | 0.085 | 0.470 | 1.519 | 0.309 |
| rain+susc+thermal+seismic | 0.069 | 0.0291 | 0.688 | 0.698 | 0.362 | 0.085 | 0.477 | 1.591 | 0.306 |
| full | 0.076 | 0.0373 | 0.588 | 0.614 | 0.254 | 0.101 | 0.359 | 2.231 | 0.219 |

Full ± LLM-Verifier: added in Phase 4/6 (same split, same cache).

