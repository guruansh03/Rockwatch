# CP2 decision packet — region Y

Generated 2026-10-29 18:52. **No test-split labels were read to produce this page.**

Data coverage: 1/1 zones with weather

## Decision 1 — L2 threshold rule (validation split; optimistic because thresholds are tuned here)

| t2 rule | t2 | recall_before | recall_at | precision_episode | precision_day | F1_at | F1_day | alert-day frac | FA/zone-yr | B4 random recall_at @ same frac |
|---|---|---|---|---|---|---|---|---|---|---|
| f1_episode | 0.0370 | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.321 | 1.000 | 0.000 | 1.000 |
| f1_day | 0.1375 | 0.325 | 0.475 | 0.575 | 0.329 | 0.520 | 0.389 | 0.209 | 7.900 | 0.279 |

- `f1_episode` = spec §8 as written. Episode precision counts a long episode as one hit, so it can favour near-always-on alerting.
- `f1_day` = day-level precision: every alert-day costs. Recommended if `f1_episode` gives an alert-day fraction near 1.

## Decision 2 — demo scenarios (test period; chosen from weather + quakes only)

| name | start | days | why |
|---|---|---|---|
| test_storm | 2010-11-19 | 45 | wettest 45-day window of region-mean precipitation in test period (13.3 mm/day) |
| test_quiet | 2010-05-29 | 45 | driest 45-day window (0.08 mm/day) |
| test_earthquake | 2011-08-14 | 45 | largest quake ≤100 km of a zone in test period: M4.23 on 2011-08-24 |

## Decision 3 — run the final evaluation

`python -m rockwatch eval --split test --final --regions A Y` then `--llm on` (same split, same cache).
Test metrics can be produced once; reruns need `--force-rerun-with-reason`.

Reply at CP2 with: t2 rule, scenario OK/changes, go/no-go for the final run.
