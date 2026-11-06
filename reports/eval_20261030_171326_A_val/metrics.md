# RockWatch evaluation — region A (Anchorage / Seward Highway, Alaska (AK DOT)), split **val**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2015-03-13 → 2018-03-15 · git `HEAD` · LLM verifier: off · alert level for P/R: L2+

**⚠ PARTIAL DATA: 44 of 70 zones lack weather. Smoke test only — not a result.**

_Validation split: thresholds and baseline cut-offs were tuned on this split, so these numbers are optimistic._

Event-days: 589 · short-range events: 0 · zone-days: 28574

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 75 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 0.244 [0.119, 0.378] | 0.260 [0.128, 0.394] | 0.182 [0.109, 0.254] | 0.122 [0.060, 0.186] | 0.214 [0.131, 0.268] | 0.166 [0.083, 0.248] | 1.381 [0.988, 1.759] | 0.058 [0.042, 0.074] | 132 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 0.545 [0.439, 0.681] | 0.625 [0.515, 0.776] | 0.061 [0.050, 0.070] | 0.036 [0.030, 0.043] | 0.111 [0.093, 0.128] | 0.069 [0.057, 0.080] | 34.130 [30.883, 37.555] | 0.495 [0.444, 0.548] | 2843 |
| B2_seattle_ct_designed_for_seattle | 0.081 [0.044, 0.126] | 0.093 [0.051, 0.145] | 0.117 [0.071, 0.163] | 0.022 [0.013, 0.031] | 0.104 [0.062, 0.147] | 0.035 [0.021, 0.050] | 2.978 [2.291, 3.783] | 0.132 [0.109, 0.157] | 264 |
| B3_seasonal_climatology | 0.326 [0.173, 0.486] | 0.328 [0.173, 0.488] | 0.857 [0.500, 1.000] | 0.293 [0.161, 0.409] | 0.474 [0.276, 0.649] | 0.310 [0.168, 0.440] | 0.013 [0.000, 0.039] | 0.032 [0.025, 0.039] | 7 |
| B4_random_matched_rate | 0.056 | 0.084 | 0.041 | 0.032 | 0.055 | – | 9.743 | 0.058 | – |
| B5_rain_only | 0.299 | 0.326 | 0.082 | 0.040 | 0.131 | 0.071 | 8.756 | 0.233 | 746 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0108 — max t: val recall_at>=0.9
- t2 (L2) = 0.0516 — argmax val f1_day (t2_rule=f1_day)
- t3 (L3) = 0.0541 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 6820, 'L1': 20092, 'L2': 492, 'L3': 1170}; L1+ recall_at 0.902, alert-day fraction 0.761

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 555 | 0.245 | 0.258 |
| type_not_fall_only | 34 | 0.235 | 0.294 |
| confidence_ge5 | 589 | 0.244 | 0.260 |
| without_eq_triggered | 589 | 0.244 | 0.260 |
| eq_triggered_only | 0 | – | – |
| season_DJF | 62 | 0.113 | 0.113 |
| season_MAM | 218 | 0.303 | 0.335 |
| season_JJA | 173 | 0.353 | 0.364 |
| season_SON | 136 | 0.074 | 0.074 |

## Lead days (TP_at events)

n=153, median=20.000, mean=37.614; histogram {0: 9, 1: 9, 2: 10, 3: 7, 4: 6, 5: 4, 6: 4, 7: 4, 8: 2, 9: 3, 10: 3, 11: 2, 12: 3, 13: 2, 14: 1, 15: 1, 16: 3, 17: 2, 19: 1, 20: 1, 21: 1, 22: 1, 23: 2, 24: 1, 26: 2, 27: 3, 28: 4, 29: 2, 31: 1, 33: 1, 34: 2, 35: 1, 36: 1, 37: 1, 38: 1, 39: 2, 41: 1, 42: 1, 47: 1, 48: 1, 50: 1, 55: 1, 56: 1, 57: 1, 58: 1, 59: 1, 63: 1, 64: 1, 67: 1, 68: 1, 69: 1, 71: 1, 74: 1, 75: 1, 77: 1, 79: 1, 85: 1, 86: 1, 88: 1, 89: 1, 90: 1, 91: 1, 93: 1, 94: 1, 95: 1, 96: 1, 97: 1, 98: 1, 99: 1, 100: 1, 102: 1, 104: 1, 105: 1, 108: 1, 109: 1, 110: 1, 111: 1, 112: 1, 115: 1, 116: 1, 117: 1, 145: 1, 151: 1, 166: 1, 167: 1, 171: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=1861, negatives sampled=84667 (ratio 45.5:1 of 84667 available), val AP=0.055.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
