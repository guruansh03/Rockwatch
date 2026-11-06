# RockWatch evaluation — region Y (Yosemite Valley, California (USGS DS746 rockfall track)), split **val**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2008-02-08 → 2010-04-03 · git `HEAD` · LLM verifier: off · alert level for P/R: L2+

_Validation split: thresholds and baseline cut-offs were tuned on this split, so these numbers are optimistic._

Event-days: 80 · short-range events: 0 · zone-days: 786

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 88 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 0.325 [0.209, 0.433] | 0.475 [0.324, 0.620] | 0.575 [0.412, 0.744] | 0.329 [0.218, 0.438] | 0.520 [0.374, 0.646] | 0.389 [0.267, 0.498] | 7.900 [4.209, 11.430] | 0.209 [0.154, 0.263] | 40 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 0.200 [0.101, 0.309] | 0.338 [0.206, 0.480] | 0.500 [0.316, 0.706] | 0.311 [0.181, 0.460] | 0.403 [0.259, 0.538] | 0.324 [0.199, 0.444] | 7.900 [4.139, 11.902] | 0.155 [0.104, 0.216] | 34 |
| B2_seattle_ct_designed_for_seattle | 0.175 [0.077, 0.294] | 0.200 [0.083, 0.333] | 0.727 [0.571, 1.000] | 0.200 [0.097, 0.326] | 0.314 [0.150, 0.476] | 0.200 [0.094, 0.306] | 1.394 [0.000, 2.419] | 0.172 [0.104, 0.254] | 11 |
| B3_seasonal_climatology | 0.838 [0.727, 0.933] | 0.850 [0.739, 0.939] | 1.000 [1.000, 1.000] | 0.204 [0.148, 0.264] | 0.919 [0.850, 0.969] | 0.329 [0.251, 0.405] | 0.000 [0.000, 0.000] | 0.774 [0.667, 0.876] | 5 |
| B4_random_matched_rate | 0.194 | 0.279 | 0.279 | 0.184 | 0.278 | – | 23.328 | 0.212 | – |
| B5_rain_only | 0.375 | 0.512 | 0.490 | 0.280 | 0.501 | 0.362 | 11.617 | 0.272 | 49 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0784 — max t: val recall_at>=0.9
- t2 (L2) = 0.1375 — argmax val f1_day (t2_rule=f1_day)
- t3 (L3) = 0.1375 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 178, 'L1': 444, 'L2': 82, 'L3': 82}; L1+ recall_at 0.900, alert-day fraction 0.774

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 73 | 0.315 | 0.452 |
| type_not_fall_only | 7 | 0.429 | 0.714 |
| confidence_ge5 | 80 | 0.325 | 0.475 |
| without_eq_triggered | 80 | 0.325 | 0.475 |
| eq_triggered_only | 0 | – | – |
| season_DJF | 19 | 0.211 | 0.368 |
| season_MAM | 26 | 0.308 | 0.423 |
| season_JJA | 16 | 0.438 | 0.688 |
| season_SON | 19 | 0.368 | 0.474 |

## Lead days (TP_at events)

n=38, median=2.000, mean=1.763; histogram {0: 12, 1: 6, 2: 8, 3: 5, 4: 6, 6: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=253, negatives sampled=12650 (ratio 50.0:1 of 20574 available), val AP=0.212.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
