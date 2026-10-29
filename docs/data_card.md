# Data card — RockWatch-FuseGuard

> US natural-slope and road-cut data; **not open-pit mine performance**. Reported precision is a **lower bound** (unreported events). Lead time in **days** (daily inputs).

## Sources

- Ground truth: USGS, *Landslide Inventories across the United States* v3.0, DOI 10.5066/P14AJF8I (CC0). Point + polygon CSVs. Training labels / evaluation only — never a live input.
- Rockfall track: USGS Data Series 746, Yosemite rock falls 1857–2011 (Stock et al.). No coordinates; one valley zone.
- Weather: Open-Meteo historical archive (ERA5-family reanalysis), daily, `timezone=auto`. **Weather data by Open-Meteo.com** (CC BY 4.0). One request per zone centre.
- Earthquakes: USGS ComCat FDSN, region bbox + 200 km, M≥3.

## Construction

- Zones: 0.25° cells. Kept = cells with ≥1 undated or train-period inventory feature, + random sample of zero-feature 8-neighbour cells (ratio 0.25, seed 25071).
- Labels: exact-dated events, Confidence ≥ 3; y_fall, y_no_eq, y_c5 subsets. Short-range events stored for range-aware matching only. Long-range/undated never positive.
- Splits: chronological with ≥30-day gaps (config `regions.*.splits`, frozen at CP1).
- Features (≤ day d only): rain (P1, P3, P15, P30, API k=0.9, hours, intensity, Seattle CT margin, rain-on-snow), thermal (freeze–thaw 7 d, Tmax anomaly vs train-only DOY climatology), seismic (100 km / 3 d: max M, count, min dist), susceptibility (log1p prior count, neighbour-smoothed; train+undated only), context (month sin/cos, regional extent).

## Region A: Anchorage / Seward Highway, Alaska (AK DOT)

- Zones: 70 {'feature': 56, 'zero': 14}; missing weather: 44.
- Panel: 156650 zone-days, 2006-01-01 → 2022-06-30; rows with any missing weather var: 0.
- Quakes M≥3 in buffer: 4561 (max M7.1).
- Exact events: 3376; in unselected zones (dropped, leakage-safe selection): 87; in gaps/outside splits: 68; short-range events: 0.

| split | zone_days | pos_zone_days | pos_fall | pos_no_eq | pos_rate | events |
|---|---|---|---|---|---|---|
| train | 86528 | 1861 | 1754 | 1861 | 0.02151 | 1995 |
| val | 28574 | 589 | 555 | 589 | 0.02061 | 622 |
| test | 39988 | 584 | 567 | 584 | 0.0146 | 613 |

## Region Y: Yosemite Valley, California (USGS DS746 rockfall track)

- Zones: 1 {'single': 1}; missing weather: 0.
- Panel: 22280 zone-days, 1951-01-01 → 2011-12-31; rows with any missing weather var: 0.
- Quakes M≥3 in buffer: 9595 (max M7.1).
- Exact events: 627; in unselected zones (dropped, leakage-safe selection): 0; in gaps/outside splits: 90; short-range events: 0.

| split | zone_days | pos_zone_days | pos_fall | pos_no_eq | pos_rate | events |
|---|---|---|---|---|---|---|
| train | 20827 | 253 | 177 | 247 | 0.01215 | 322 |
| val | 786 | 80 | 73 | 80 | 0.10178 | 111 |
| test | 607 | 80 | 72 | 80 | 0.1318 | 104 |

## Known biases

- Region A truth = one agency log (AK DOT) along highways: road-cut slopes, maintenance-reporting bias, reporting declines 2021–22 (test FP inflated).
- Yosemite: eyewitness bias (visitor-dense areas), reporting intensity rises after ~2000.
- Reanalysis precipitation underestimates local convective/orographic extremes.
