# RockWatch evaluation — region A (Anchorage / Seward Highway, Alaska (AK DOT)), split **val**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2015-03-13 → 2018-03-15 · git `HEAD` · LLM verifier: off · alert level for P/R: L2+

_Validation split: thresholds and baseline cut-offs were tuned on this split, so these numbers are optimistic._

Event-days: 611 · short-range events: 0 · zone-days: 76930

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 78 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 0.406 [0.262, 0.549] | 0.429 [0.278, 0.570] | 0.123 [0.091, 0.145] | 0.047 [0.031, 0.063] | 0.191 [0.146, 0.220] | 0.085 [0.056, 0.112] | 1.866 [1.376, 2.289] | 0.105 [0.078, 0.129] | 448 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 0.751 [0.672, 0.844] | 0.815 [0.746, 0.897] | 0.033 [0.026, 0.038] | 0.013 [0.010, 0.015] | 0.063 [0.051, 0.073] | 0.026 [0.020, 0.030] | 28.615 [25.873, 31.257] | 0.737 [0.692, 0.777] | 6231 |
| B2_seattle_ct_designed_for_seattle | 0.088 [0.052, 0.139] | 0.101 [0.061, 0.156] | 0.035 [0.022, 0.048] | 0.004 [0.003, 0.006] | 0.052 [0.033, 0.072] | 0.008 [0.005, 0.012] | 4.947 [4.086, 5.772] | 0.279 [0.240, 0.316] | 1080 |
| B3_seasonal_climatology | 0.295 [0.151, 0.438] | 0.296 [0.151, 0.438] | 0.857 [0.500, 1.000] | 0.303 [0.159, 0.439] | 0.440 [0.242, 0.608] | 0.300 [0.155, 0.437] | 0.005 [0.000, 0.015] | 0.011 [0.008, 0.013] | 7 |
| B4_random_matched_rate | 0.105 | 0.150 | 0.017 | 0.012 | 0.030 | – | 17.481 | 0.106 | – |
| B5_rain_only | 0.350 | 0.370 | 0.045 | 0.022 | 0.079 | 0.041 | 5.602 | 0.193 | 1235 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0078 — max t: val recall_at>=0.9
- t2 (L2) = 0.0251 — argmax val f1_day (t2_rule=f1_day)
- t3 (L3) = 0.0288 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 51888, 'L1': 16930, 'L2': 2413, 'L3': 5699}; L1+ recall_at 0.908, alert-day fraction 0.326

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 571 | 0.392 | 0.415 |
| type_not_fall_only | 40 | 0.600 | 0.625 |
| confidence_ge5 | 611 | 0.406 | 0.429 |
| without_eq_triggered | 611 | 0.406 | 0.429 |
| eq_triggered_only | 0 | – | – |
| season_DJF | 65 | 0.169 | 0.185 |
| season_MAM | 226 | 0.473 | 0.500 |
| season_JJA | 175 | 0.594 | 0.611 |
| season_SON | 145 | 0.179 | 0.207 |

## Lead days (TP_at events)

n=262, median=28.000, mean=47.855; histogram {0: 14, 1: 12, 2: 18, 3: 11, 4: 9, 5: 6, 6: 8, 7: 3, 8: 3, 9: 4, 10: 1, 11: 2, 12: 5, 13: 3, 14: 3, 15: 2, 16: 2, 17: 2, 18: 2, 19: 2, 20: 2, 21: 4, 22: 1, 23: 2, 24: 3, 25: 1, 26: 2, 27: 3, 28: 2, 29: 3, 30: 2, 31: 1, 32: 1, 33: 2, 34: 1, 35: 2, 36: 1, 37: 2, 38: 1, 39: 1, 40: 1, 42: 1, 44: 2, 45: 1, 46: 4, 48: 2, 49: 1, 51: 1, 52: 2, 53: 2, 54: 1, 55: 1, 56: 1, 58: 2, 59: 1, 60: 1, 61: 1, 63: 1, 64: 2, 65: 1, 66: 1, 67: 1, 68: 1, 70: 2, 71: 1, 72: 2, 73: 3, 74: 1, 76: 1, 77: 2, 78: 1, 80: 1, 81: 1, 85: 1, 86: 2, 89: 2, 90: 1, 91: 1, 94: 1, 95: 1, 96: 1, 97: 1, 98: 1, 99: 1, 101: 1, 102: 2, 103: 2, 104: 1, 105: 1, 106: 1, 107: 1, 108: 1, 109: 1, 110: 1, 112: 1, 113: 1, 114: 2, 115: 1, 116: 3, 117: 1, 118: 2, 124: 1, 125: 1, 127: 1, 128: 1, 129: 1, 130: 1, 132: 1, 133: 1, 134: 1, 135: 1, 136: 1, 137: 1, 138: 1, 139: 1, 141: 1, 143: 1, 144: 1, 147: 1, 148: 1, 149: 1, 150: 2, 151: 1, 154: 1, 155: 1, 156: 2, 171: 1, 172: 1, 176: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=1892, negatives sampled=94600 (ratio 50.0:1 of 231068 available), val AP=0.053.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
