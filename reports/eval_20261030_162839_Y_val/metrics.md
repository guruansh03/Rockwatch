# RockWatch evaluation — region Y (Yosemite Valley, California (USGS DS746 rockfall track)), split **val**

> **US natural-slope data; not mine performance; precision is a lower bound (unreported events).** Lead time in days (daily inputs); no time-of-failure prediction.

Period 2008-02-08 → 2010-04-03 · git `HEAD` · LLM verifier: off · alert level for P/R: L2+

_Validation split: thresholds and baseline cut-offs were tuned on this split, so these numbers are optimistic._

Event-days: 80 · short-range events: 0 · zone-days: 786

## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, 1000 resamples, 88 blocks)

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| RockWatch (full fusion) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 | 0.191 [0.143, 0.245] | 1.000 | 0.321 [0.250, 0.393] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 1 |

| system | recall_before | recall_at | precision_episode | precision_day | f1_at | f1_day | false_alarms_per_zone_year | alert_day_fraction | episodes |
|---|---|---|---|---|---|---|---|---|---|
| B1_P1_threshold | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 | 0.191 [0.143, 0.245] | 1.000 | 0.321 [0.250, 0.393] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 1 |
| B2_seattle_ct_designed_for_seattle | 0.175 [0.077, 0.294] | 0.200 [0.083, 0.333] | 0.727 [0.571, 1.000] | 0.200 [0.097, 0.326] | 0.314 [0.150, 0.476] | 0.200 [0.094, 0.306] | 1.394 [0.000, 2.419] | 0.172 [0.104, 0.254] | 11 |
| B3_seasonal_climatology | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 | 0.191 [0.143, 0.245] | 1.000 | 0.321 [0.250, 0.393] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 1 |
| B4_random_matched_rate | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | – | 0.000 | 1.000 | – |
| B5_rain_only | 1.000 | 1.000 | 1.000 | 0.191 | 1.000 | 0.321 | 0.000 | 1.000 | 1 |

B4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.

## Thresholds (validation-only rules)

- t1 (L1) = 0.0370 — max t: val recall_at>=0.9
- t2 (L2) = 0.0370 — argmax val f1_at (t2_rule=f1_episode)
- t3 (L3) = 0.1204 — max L3 precision s.t. recall_at>=0.2 & corroboration; L3 enabled: True

- Active zone-days by level: {'L0': 0, 'L1': 0, 'L2': 695, 'L3': 91}; L1+ recall_at 1.000, alert-day fraction 1.000

## Breakdowns (recall over event-days)

| subset | n | recall_before | recall_at |
|---|---|---|---|
| type_fall | 73 | 1.000 | 1.000 |
| type_not_fall_only | 7 | 1.000 | 1.000 |
| confidence_ge5 | 80 | 1.000 | 1.000 |
| without_eq_triggered | 80 | 1.000 | 1.000 |
| eq_triggered_only | 0 | – | – |
| season_DJF | 19 | 1.000 | 1.000 |
| season_MAM | 26 | 1.000 | 1.000 |
| season_JJA | 16 | 1.000 | 1.000 |
| season_SON | 19 | 1.000 | 1.000 |

## Lead days (TP_at events)

n=80, median=803.500, mean=783.850; histogram {401: 1, 403: 1, 406: 1, 409: 1, 423: 1, 445: 1, 451: 1, 460: 1, 470: 1, 472: 1, 498: 1, 502: 1, 505: 1, 539: 1, 540: 1, 568: 1, 576: 1, 582: 1, 589: 1, 614: 1, 616: 1, 625: 1, 631: 1, 632: 1, 655: 1, 656: 1, 657: 1, 659: 1, 692: 1, 719: 1, 732: 1, 733: 1, 738: 1, 745: 1, 752: 1, 769: 1, 779: 1, 801: 1, 802: 1, 803: 1, 804: 1, 808: 1, 824: 1, 830: 1, 833: 1, 837: 1, 839: 1, 845: 1, 853: 1, 863: 1, 866: 1, 897: 1, 904: 1, 907: 1, 915: 1, 917: 1, 920: 1, 934: 1, 951: 1, 954: 1, 973: 1, 988: 1, 994: 1, 1002: 1, 1003: 1, 1004: 1, 1006: 1, 1017: 1, 1026: 1, 1030: 1, 1061: 1, 1073: 1, 1075: 1, 1077: 1, 1099: 1, 1102: 1, 1130: 1, 1154: 1, 1170: 1, 1174: 1} (0 = same-day nowcast only).

## Model

C=1.0, positives=253, negatives sampled=12650 (ratio 50.0:1 of 20574 available), val AP=0.212.

See `ablation.md`, `pr_curve.png`, `lead_days.png`.

---
Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).
