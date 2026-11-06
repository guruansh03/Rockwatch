# RockWatch evaluation — region Y (Yosemite Valley, California (USGS DS746 rockfall track)), split **test**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2010-05-04 → 2011-12-31 · git `28e2d92a23` · LLM verifier: on · alert level for P/R: L2+

Event-days: 80 · short-range events: 0 · zone-days: 607

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 79 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 0.138 [0.052, 0.227] | 0.237 [0.118, 0.352] | 0.433 [0.250, 0.630] | 0.231 [0.123, 0.351] | 0.307 [0.165, 0.427] | 0.234 [0.126, 0.331] | 10.229 [5.662, 14.934] | 0.178 [0.129, 0.227] | 30 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 0.175 [0.072, 0.279] | 0.250 [0.130, 0.372] | 0.467 [0.294, 0.645] | 0.289 [0.176, 0.407] | 0.326 [0.186, 0.446] | 0.268 [0.152, 0.367] | 9.628 [5.254, 14.611] | 0.160 [0.106, 0.222] | 30 |
| B2_seattle_ct_designed_for_seattle | 0.150 [0.035, 0.288] | 0.150 [0.035, 0.288] | 1.000 [1.000, 1.000] | 0.212 [0.074, 0.355] | 0.261 [0.067, 0.449] | 0.176 [0.047, 0.293] | 0.000 [0.000, 0.000] | 0.163 [0.080, 0.251] | 4 |
| B3_seasonal_climatology | 0.600 [0.443, 0.757] | 0.613 [0.452, 0.765] | 1.000 [1.000, 1.000] | 0.207 [0.144, 0.284] | 0.760 [0.627, 0.867] | 0.310 [0.225, 0.399] | 0.000 [0.000, 0.000] | 0.707 [0.586, 0.805] | 4 |
| B4_random_matched_rate | 0.168 | 0.231 | 0.323 | 0.216 | 0.268 | – | 18.864 | 0.174 | – |
| B5_rain_only | 0.312 | 0.425 | 0.579 | 0.313 | 0.490 | 0.360 | 9.628 | 0.269 | 38 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0784 — max t: val recall_at>=0.9
- t2 (L2) = 0.1375 — argmax val f1_day (t2_rule=f1_day)
- t3 (L3) = 0.1375 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 152, 'L1': 347, 'L2': 38, 'L3': 70}; L1+ recall_at 0.775, alert-day fraction 0.750

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 72 | 0.125 | 0.208 |
| type_not_fall_only | 8 | 0.250 | 0.500 |
| confidence_ge5 | 80 | 0.138 | 0.237 |
| without_eq_triggered | 80 | 0.138 | 0.237 |
| eq_triggered_only | 0 | – | – |
| season_DJF | 15 | 0.400 | 0.600 |
| season_MAM | 9 | 0.111 | 0.111 |
| season_JJA | 20 | 0.200 | 0.350 |
| season_SON | 36 | 0.000 | 0.056 |

## Lead days (TP_at events)

n=19, median=1.000, mean=1.211; histogram {0: 8, 1: 4, 2: 4, 3: 2, 5: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=253, negatives sampled=12650 (ratio 50.0:1 of 20574 available), val AP=0.212.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
