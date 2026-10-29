# RockWatch evaluation — region A (Anchorage / Seward Highway, Alaska (AK DOT)), split **val**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2015-03-13 → 2018-03-15 · git `562fa5c7bf` · LLM verifier: off · alert level for P/R: L2+

**⚠ PARTIAL DATA: 56 of 70 zones lack weather. Smoke test only — not a result.**

_Validation split: thresholds and baseline cut-offs were tuned on this split, so these numbers are optimistic._

Event-days: 391 · short-range events: 0 · zone-days: 15386

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 88 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 0.588 [0.434, 0.713] | 0.614 [0.458, 0.741] | 0.254 [0.131, 0.392] | 0.101 [0.062, 0.140] | 0.359 [0.209, 0.503] | 0.173 [0.109, 0.233] | 2.231 [1.598, 2.751] | 0.219 [0.186, 0.253] | 126 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.571 | 0.040 [0.027, 0.055] | 0.727 | 0.077 [0.052, 0.105] | 0.142 [0.000, 0.000] | 1.000 [1.000, 1.000] | 14 |
| B2_seattle_ct_designed_for_seattle | 0.066 [0.032, 0.117] | 0.074 [0.035, 0.134] | 0.140 [0.082, 0.203] | 0.032 [0.015, 0.048] | 0.097 [0.052, 0.148] | 0.044 [0.022, 0.068] | 2.326 [1.734, 3.115] | 0.091 [0.074, 0.108] | 114 |
| B3_seasonal_climatology | 0.795 [0.687, 0.873] | 0.801 [0.693, 0.880] | 0.677 [0.429, 0.870] | 0.122 [0.083, 0.159] | 0.734 [0.552, 0.839] | 0.212 [0.150, 0.268] | 0.237 [0.066, 0.381] | 0.252 [0.209, 0.295] | 31 |
| B4_random_matched_rate | 0.216 | 0.305 | 0.055 | 0.039 | 0.093 | – | 31.526 | 0.220 | – |
| B5_rain_only | 0.655 | 0.719 | 0.100 | 0.045 | 0.176 | 0.084 | 20.012 | 0.588 | 937 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0168 — max t: val recall_at>=0.9
- t2 (L2) = 0.0373 — argmax val F1_at
- t3 (L3) = 0.0655 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 7298, 'L1': 4711, 'L2': 2194, 'L3': 1183}; L1+ recall_at 0.793, alert-day fraction 0.526

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 362 | 0.583 | 0.605 |
| type_not_fall_only | 29 | 0.655 | 0.724 |
| confidence_ge5 | 391 | 0.588 | 0.614 |
| without_eq_triggered | 391 | 0.588 | 0.614 |
| eq_triggered_only | 0 | – | – |
| season_DJF | 43 | 0.326 | 0.326 |
| season_MAM | 141 | 0.688 | 0.716 |
| season_JJA | 120 | 0.642 | 0.667 |
| season_SON | 87 | 0.483 | 0.517 |

## Lead days (TP_at events)

n=240, median=79.500, mean=101.717; histogram {0: 10, 1: 6, 2: 6, 3: 2, 5: 3, 6: 5, 7: 2, 8: 1, 9: 1, 10: 2, 11: 1, 12: 1, 13: 2, 14: 3, 15: 1, 16: 1, 17: 1, 20: 1, 21: 1, 22: 1, 28: 1, 29: 1, 33: 1, 34: 1, 36: 1, 38: 1, 39: 2, 40: 2, 41: 2, 42: 2, 43: 2, 44: 1, 45: 1, 46: 1, 47: 2, 48: 2, 49: 2, 50: 2, 51: 2, 52: 2, 53: 3, 54: 2, 55: 2, 56: 2, 57: 1, 58: 2, 59: 2, 60: 2, 61: 2, 62: 2, 63: 1, 64: 2, 65: 2, 66: 2, 67: 1, 68: 1, 69: 1, 71: 1, 72: 2, 73: 1, 74: 2, 76: 1, 79: 1, 80: 1, 81: 1, 82: 1, 83: 1, 84: 1, 86: 1, 88: 1, 90: 1, 91: 1, 92: 1, 93: 1, 95: 1, 96: 1, 99: 2, 100: 2, 101: 1, 105: 1, 107: 1, 109: 2, 111: 2, 112: 1, 114: 1, 116: 2, 117: 2, 120: 1, 121: 1, 122: 1, 124: 1, 125: 1, 130: 1, 132: 1, 133: 2, 138: 1, 139: 1, 140: 1, 141: 1, 142: 1, 144: 1, 146: 1, 147: 1, 150: 1, 151: 1, 152: 1, 153: 1, 154: 1, 157: 1, 158: 1, 160: 1, 162: 1, 168: 1, 169: 1, 171: 1, 172: 1, 173: 1, 174: 1, 176: 1, 177: 1, 178: 1, 179: 1, 180: 1, 181: 1, 182: 1, 183: 1, 184: 1, 185: 1, 187: 1, 188: 1, 190: 1, 191: 1, 192: 1, 193: 1, 194: 1, 195: 1, 198: 1, 199: 1, 200: 1, 205: 1, 206: 1, 207: 1, 208: 1, 210: 2, 217: 1, 223: 1, 228: 1, 229: 1, 231: 1, 234: 1, 235: 2, 236: 1, 237: 2, 238: 1, 239: 1, 240: 1, 241: 1, 242: 2, 243: 2, 244: 2, 246: 1, 248: 2, 249: 1, 250: 1, 251: 1, 252: 1, 259: 1, 267: 1, 268: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=1769, negatives sampled=44823 (ratio 25.34:1 of 44823 available), val AP=0.076.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
