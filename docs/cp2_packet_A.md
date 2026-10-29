# CP2 decision packet — region A

Generated 2026-10-29 18:52. **No test-split labels were read to produce this page.**

Data coverage: 26/70 zones with weather — **PARTIAL: complete the weather fetch before the final run.**

## Decision 1 — L2 threshold rule (validation split; optimistic because thresholds are tuned here)

| t2 rule | t2 | recall_before | recall_at | precision_episode | precision_day | F1_at | F1_day | alert-day frac | FA/zone-yr | B4 random recall_at @ same frac |
|---|---|---|---|---|---|---|---|---|---|---|
| f1_episode | 0.0031 | 1.000 | 1.000 | 0.538 | 0.032 | 0.700 | 0.063 | 1.000 | 0.153 | 1.000 |
| f1_day | 0.0516 | 0.244 | 0.260 | 0.182 | 0.122 | 0.214 | 0.166 | 0.058 | 1.381 | 0.084 |

- `f1_episode` = spec §8 as written. Episode precision counts a long episode as one hit, so it can favour near-always-on alerting.
- `f1_day` = day-level precision: every alert-day costs. Recommended if `f1_episode` gives an alert-day fraction near 1.

## Decision 2 — demo scenarios (test period; chosen from weather + quakes only)

| name | start | days | why |
|---|---|---|---|
| test_storm | 2018-10-12 | 45 | wettest 45-day window of region-mean precipitation in test period (8.0 mm/day) |
| test_quiet | 2022-05-15 | 45 | driest 45-day window (1.14 mm/day) |
| test_earthquake | 2018-11-20 | 45 | largest quake ≤100 km of a zone in test period: M7.1 on 2018-11-30 |

## Decision 3 — run the final evaluation

`python -m rockwatch eval --split test --final --regions A Y` then `--llm on` (same split, same cache).
Test metrics can be produced once; reruns need `--force-rerun-with-reason`.

Reply at CP2 with: t2 rule, scenario OK/changes, go/no-go for the final run.
