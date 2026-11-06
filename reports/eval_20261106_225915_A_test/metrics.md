# RockWatch evaluation — region A (Anchorage / Seward Highway, Alaska (AK DOT)), split **test**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2018-04-15 → 2022-06-30 · git `28e2d92a23` · LLM verifier: on · alert level for P/R: L2+

Event-days: 606 · short-range events: 0 · zone-days: 107660

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 120 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 0.447 [0.349, 0.538] | 0.469 [0.372, 0.557] | 0.092 [0.050, 0.123] | 0.035 [0.026, 0.045] | 0.154 [0.091, 0.193] | 0.066 [0.050, 0.082] | 2.137 [1.640, 2.590] | 0.111 [0.085, 0.136] | 694 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 0.776 [0.724, 0.842] | 0.855 [0.806, 0.909] | 0.026 [0.019, 0.033] | 0.009 [0.006, 0.012] | 0.051 [0.038, 0.064] | 0.018 [0.013, 0.023] | 27.545 [24.748, 30.262] | 0.778 [0.744, 0.810] | 8339 |
| B2_seattle_ct_designed_for_seattle | 0.091 [0.048, 0.158] | 0.097 [0.049, 0.169] | 0.025 [0.015, 0.035] | 0.003 [0.002, 0.005] | 0.040 [0.023, 0.055] | 0.006 [0.003, 0.009] | 4.655 [4.030, 5.252] | 0.295 [0.258, 0.333] | 1407 |
| B3_seasonal_climatology | 0.236 [0.163, 0.311] | 0.239 [0.165, 0.313] | 0.800 [0.333, 1.000] | 0.181 [0.122, 0.234] | 0.368 [0.248, 0.447] | 0.206 [0.142, 0.262] | 0.007 [0.000, 0.016] | 0.011 [0.009, 0.014] | 10 |
| B4_random_matched_rate | 0.118 | 0.168 | 0.013 | 0.009 | 0.024 | – | 18.360 | 0.111 | – |
| B5_rain_only | 0.318 | 0.363 | 0.035 | 0.014 | 0.064 | 0.028 | 6.616 | 0.188 | 2021 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0078 — max t: val recall_at>=0.9
- t2 (L2) = 0.0251 — argmax val f1_day (t2_rule=f1_day)
- t3 (L3) = 0.0288 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 72737, 'L1': 23004, 'L2': 3544, 'L3': 8375}; L1+ recall_at 0.919, alert-day fraction 0.324

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 581 | 0.451 | 0.472 |
| type_not_fall_only | 25 | 0.360 | 0.400 |
| confidence_ge5 | 606 | 0.447 | 0.469 |
| without_eq_triggered | 602 | 0.450 | 0.472 |
| eq_triggered_only | 4 | 0.000 | 0.000 |
| season_DJF | 39 | 0.026 | 0.051 |
| season_MAM | 303 | 0.548 | 0.571 |
| season_JJA | 132 | 0.674 | 0.705 |
| season_SON | 132 | 0.114 | 0.121 |

## Lead days (TP_at events)

n=284, median=30.000, mean=42.046; histogram {0: 13, 1: 15, 2: 12, 3: 13, 4: 12, 5: 4, 6: 3, 7: 5, 8: 6, 9: 3, 10: 3, 11: 3, 12: 2, 13: 3, 14: 3, 15: 6, 16: 2, 17: 2, 18: 1, 19: 4, 20: 3, 21: 2, 22: 3, 23: 2, 24: 3, 25: 2, 26: 5, 27: 2, 28: 2, 29: 1, 30: 3, 31: 2, 32: 3, 33: 3, 34: 2, 35: 1, 36: 1, 37: 1, 38: 1, 39: 1, 40: 2, 41: 2, 42: 1, 43: 2, 44: 1, 46: 1, 47: 1, 48: 2, 49: 3, 50: 3, 51: 3, 52: 1, 53: 4, 54: 1, 55: 2, 56: 5, 57: 3, 58: 2, 59: 2, 60: 3, 61: 4, 62: 2, 63: 2, 64: 2, 66: 4, 67: 3, 69: 1, 70: 1, 71: 2, 72: 2, 73: 1, 74: 2, 75: 1, 77: 2, 78: 1, 79: 2, 80: 1, 81: 3, 82: 1, 84: 2, 85: 1, 86: 1, 87: 2, 88: 1, 89: 2, 90: 2, 91: 1, 92: 2, 93: 1, 94: 1, 96: 1, 99: 1, 102: 1, 103: 1, 104: 1, 110: 1, 112: 1, 115: 1, 116: 1, 118: 1, 119: 1, 126: 1, 128: 1, 129: 1, 133: 2, 135: 1, 138: 2, 140: 1, 146: 1, 147: 2, 150: 1, 153: 1, 154: 3, 155: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=1892, negatives sampled=94600 (ratio 50.0:1 of 231068 available), val AP=0.053.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
