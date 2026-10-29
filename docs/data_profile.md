# Data profile — USGS Landslide Inventories across the US v3.0

Generated 2026-10-29 16:59 from `US_Landslide_v3_csv.zip` by `rockwatch profile`.  
Source: USGS, *Landslide Inventories across the United States* v3.0, DOI 10.5066/P14AJF8I (CC0).  
**US natural-slope data; not open-pit mine performance.** Unreported events exist, so any precision derived later is a lower bound.

## 1. Cleaning summary

| index | value |
|---|---|
| n_raw | 991271 |
| n_bad_coords | 0 |
| n_excluded_type | 8147 |
| lon_sign_flipped | False |
| n_lon_positive_after | 0 |
| n_unparsed_date_min | 0 |
| n_date_max_before_min | 7 |
| n_future_dates | 1 |
| n_same_day_range | 298 |
| n_kept | 983124 |

Excluded LS_Type values (top 30):

| index | n |
|---|---|
| snow avalanche field | 3195 |
| Manmade Fill | 1847 |
| snow avalanche chute | 1837 |
| Earth Gully | 259 |
| Gully Head | 241 |
| multiple debris flow, avalanche chute | 172 |
| High Hazard, Subsidence, Hydrocompaction, Landslide | 145 |
| Gully | 139 |
| avalanche chute | 46 |
| snow avalanche | 24 |
| multiple debris flow, alluvial cone, avalanche chute | 21 |
| rock slide, avalanche chute | 20 |
| Earth Landslide-Gully Complex | 19 |
| avalanche chute, debris flow | 17 |
| multiple debris flow, alluvial fan, avalanche chute | 17 |
| Debris Subsidence | 14 |
| Differential Erosion | 12 |
| avalanche chute, multiple debris flow | 11 |
| snow avalanche, debris avalanche | 11 |
| Subsidence in fan deltas | 10 |
| debris flow, avalanche chute | 10 |
| Earth Translational Slide Landslide-Gully Complex | 6 |
| multiple debris flow, Quaternary talus, avalanche chute | 5 |
| multiple flow, avalanche chute | 4 |
| Earth Translational Slide/Flow Landslide-Gully Complex | 4 |
| multiple rock slide, avalanche chute | 3 |
| Earth Translational Slide Gully | 3 |
| Earth Gully Head | 3 |
| multiple debris flow, avalanche chute, Quaternary alluvium | 3 |
| avalanche chute, slope wash | 2 |

## 2. Counts (all confidence levels)

### date_kind
| date_kind | count |
|---|---|
| undated | 787947 |
| long_range | 134603 |
| exact | 54810 |
| short_range | 5764 |

### type_family
| type_family | count |
|---|---|
| slide | 415724 |
| unknown | 309004 |
| flow | 150095 |
| other | 85603 |
| fall | 22698 |

### Confidence
| confidence | count |
|---|---|
| 1 | 24826 |
| 2 | 34874 |
| 3 | 351835 |
| 5 | 166471 |
| 8 | 405118 |

### Raw LS_Type (top 40) → type_family

| LS_Type | type_family | n |
|---|---|---|
| <empty> | unknown | 299239 |
| slide | slide | 104871 |
| rock slide | slide | 49077 |
| Older Landslide | slide | 33381 |
| Active Or Recently Active Landslide | slide | 31379 |
| debris slide | slide | 25787 |
| debris avalanche | flow | 24019 |
| Debris Flow | flow | 23401 |
| debris flow | flow | 23033 |
| Landslide | slide | 22061 |
| shallow landslide | slide | 20513 |
| fan | other | 16426 |
| Earth Flow | flow | 14404 |
| Shallow undifferentiated | other | 13816 |
| Complex | other | 12892 |
| Rock Slide-Rotational | slide | 11168 |
| deep or unclassified landslide | slide | 9939 |
| Active or Recently Active Landslide | slide | 9928 |
| Deep-seated undifferentiated | other | 8424 |
| earth flow | flow | 8273 |
| landslide deposits (late Holocene) | slide | 7914 |
| Unknown | unknown | 7503 |
| Fan | other | 6916 |
| deposits | other | 6818 |
| Earth or debris Complex | other | 6337 |
| Rockfalls | fall | 6308 |
| Rockfall | fall | 5161 |
| Recent Landslide | slide | 5024 |
| Rock Slide-Translational | slide | 4971 |
| Debris flow | flow | 4745 |
| Earth Slide-Rotational | slide | 4319 |
| Earth Slide-general | slide | 4278 |
| landslide undifferentiated from talus and/or colluvial deposits | slide | 4253 |
| multiple slump, multiple flow | flow | 4231 |
| earth or debris slide-rotational, earth or debris flow | flow | 4142 |
| shallow landslide source runout area | slide | 4025 |
| Debris Slide | slide | 3591 |
| Debris slide and avalanches | slide | 3516 |
| Rock Flow | flow | 3457 |
| Debris Slide-Translational | slide | 3231 |

### Inventory (top 40)
| Inventory | count |
|---|---|
| WV GS | 196240 |
| CA GS | 140558 |
| OR DOGAMI | 115345 |
| WA WGS | 97803 |
| USGS PR Hurricane Maria (Hughes and others, 2019) | 71431 |
| ND GS | 59718 |
| WY WSGS | 33387 |
| USDA-FS AK Tongass | 29673 |
| USGS Earthquake-Triggered Ground Failure | 28922 |
| CO GS | 28372 |
| UT GRC | 27970 |
| KY GS | 22886 |
| NC GS | 22252 |
| USGS CA East SF Bay 2016-2017 | 21881 |
| USGS MN | 15486 |
| AZ GS | 8406 |
| AK DOT | 6408 |
| USGS Conterminous | 6297 |
| USGS PA (Pomeroy, 1974) | 5395 |
| ID GS | 4614 |
| USGS CA Crow Creek 1998 | 4059 |
| NASA | 3975 |
| USGS PR Hurricane Maria (Einbund and others, 2021a) | 3762 |
| USGS PR Hurricane Maria (Einbund and others, 2021b) | 3491 |
| USGS PR Hurricane Maria (Baxstrom and others, 2021) | 3472 |
| USGS PR Hurricane Maria (Bessette-Kirton and others, 2019) | 2805 |
| WA SDIC | 2724 |
| VT GS | 2368 |
| Santa Catalina Island CA (Regmi and others, 2019) | 1795 |
| USGS CO Front Range Sept 2013 | 1350 |
| USGS AK 2018 Ground Failure | 1047 |
| USGS CO Front Range July 1999 | 806 |
| ME GS | 770 |
| Western CO (Regmi and others, 2010) | 734 |
| West Coast Slow Moving (Yuankun and others, 2021) | 705 |
| NV NBMG | 694 |
| USGS PR Hurricane Maria (Baxstrom and others, 2024) | 650 |
| USGS OR Southern Coast Range Nov 1996 | 609 |
| USGS CA Walpert Ridge 1998 | 565 |
| USGS WA Puget Sound | 454 |

### Decade of Date_Min (dated rows)
| date_min | count |
|---|---|
| 1780 | 1 |
| 1810 | 2 |
| 1820 | 1 |
| 1830 | 3 |
| 1840 | 2 |
| 1850 | 1 |
| 1860 | 3 |
| 1870 | 4 |
| 1880 | 2 |
| 1890 | 12 |
| 1900 | 20 |
| 1910 | 89 |
| 1920 | 90 |
| 1930 | 638 |
| 1940 | 3736 |
| 1950 | 1821 |
| 1960 | 777 |
| 1970 | 3407 |
| 1980 | 12469 |
| 1990 | 33858 |
| 2000 | 13649 |
| 2010 | 122205 |
| 2020 | 2387 |

### date_kind × Confidence
| date_kind | 1 | 2 | 3 | 5 | 8 |
|---|---|---|---|---|---|
| exact | 110 | 6149 | 21832 | 13426 | 13293 |
| long_range | 21 | 0 | 5670 | 9419 | 119493 |
| short_range | 0 | 0 | 206 | 4172 | 1386 |
| undated | 24695 | 28725 | 324127 | 139454 | 270946 |

## 3. Exact-dated events since 1950

- C≥3: **48093** events; C≥5: **26322** events.
- C≥3 by type_family:

| type_family | count |
|---|---|
| unknown | 31975 |
| flow | 6175 |
| fall | 5323 |
| slide | 3616 |
| other | 1004 |

- C≥3 by Inventory (EQ-triggered marked *):

| Inventory | count |
|---|---|
| USGS Earthquake-Triggered Ground Failure * | 28922 |
| AK DOT | 6408 |
| WA WGS | 3414 |
| AZ GS | 1833 |
| OR DOGAMI | 1559 |
| WA SDIC | 1289 |
| ID GS | 1053 |
| NC GS | 882 |
| USDA-FS AK Tongass | 835 |
| USGS CO Front Range July 1999 | 806 |
| USGS MN | 482 |
| USGS Seismogenic Mass Movements * | 155 |
| NJ GS | 145 |
| USGS Post-Fire Debris Flows | 124 |
| NASA | 87 |
| NE Univ of NE Lincoln | 49 |
| CA GS | 18 |
| USGS CA Montecito Jan 2018 | 15 |
| MO DNR | 8 |
| USGS AK St Elias | 6 |
| KY GS | 3 |

- C≥3 raw LS_Type (top 30) → family:

| LS_Type | type_family | n |
|---|---|---|
| <empty> | unknown | 31925 |
| Rockfall | fall | 5061 |
| Debris Flow | flow | 2527 |
| Debris slide and avalanches | slide | 1615 |
| Debris flow | flow | 1354 |
| debris flow | flow | 1317 |
| Landslide/Embankment Failure | slide | 962 |
| debris avalanche | flow | 655 |
| Shallow undifferentiated | other | 478 |
| Complex or Combinations of two or more types | other | 468 |
| slide affected property | slide | 351 |
| Debris Slide | slide | 304 |
| Rockfalls, soil falls, or topples | fall | 104 |
| combination debris avalanche and debris torrent | flow | 99 |
| debris torrent | flow | 78 |
| Hyperconcentrated flows | flow | 61 |
|   | unknown | 50 |
| Slide | slide | 50 |
| Weathered rock Slide | slide | 38 |
| landslide | slide | 38 |
| Rock Slide | slide | 32 |
| rock fall | fall | 31 |
| rock_fall | fall | 31 |
| Debris Slide - translational | slide | 30 |
| rock avalanche | fall | 30 |
| Rock Slide - translational | slide | 23 |
| Bedrock Rotational Slide | slide | 21 |
| mudslide | flow | 21 |
| Earth Rotational Slide | slide | 21 |
| Rockslide | slide | 18 |

- C≥3 by year (last 30 years with data):

| date_min | count |
|---|---|
| 1995 | 42 |
| 1996 | 856 |
| 1997 | 1361 |
| 1998 | 41 |
| 1999 | 849 |
| 2000 | 27 |
| 2001 | 61 |
| 2002 | 1627 |
| 2003 | 21 |
| 2004 | 106 |
| 2005 | 296 |
| 2006 | 1915 |
| 2007 | 2099 |
| 2008 | 649 |
| 2009 | 2001 |
| 2010 | 425 |
| 2011 | 519 |
| 2012 | 820 |
| 2013 | 382 |
| 2014 | 1306 |
| 2015 | 695 |
| 2016 | 438 |
| 2017 | 528 |
| 2018 | 907 |
| 2019 | 605 |
| 2020 | 1173 |
| 2021 | 350 |
| 2022 | 159 |
| 2023 | 13 |
| 2024 | 1 |

- Positive zone-days (0.25° cells, C≥3): **8211**; distinct dates: **4918**; storm clusters (≤3 d): **944**.

## 4. Candidate regions

Square windows of [2.0, 3.0]° slid in 0.5° steps over 0.25° zone centres; greedy non-overlapping top windows per size. No state polygons (no geopandas); bbox is the region unit.

Ranked by `pos_zone_days_no_eq`.

| lat0 | lat1 | lon0 | lon1 | window_deg | pos_zone_days | fall_zone_days | distinct_days | storm_clusters | pos_zone_days_c5 | pos_zone_days_no_eq | n_zones_with_pos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 59.5 | 62.5 | -150.5 | -147.5 | 3.0 | 3175 | 2982 | 2664 | 302 | 3175 | 3170 | 31 |
| 60.0 | 62.0 | -150.0 | -148.0 | 2.0 | 2949 | 2763 | 2511 | 316 | 2949 | 2946 | 25 |
| 57.0 | 60.0 | -137.0 | -134.0 | 3.0 | 1765 | 1210 | 1440 | 472 | 1765 | 1761 | 25 |
| 58.0 | 60.0 | -136.0 | -134.0 | 2.0 | 1685 | 1175 | 1406 | 465 | 1685 | 1684 | 12 |
| 45.0 | 48.0 | -124.0 | -121.0 | 3.0 | 1293 | 27 | 1075 | 683 | 1032 | 1260 | 69 |
| 46.0 | 48.0 | -123.5 | -121.5 | 2.0 | 668 | 18 | 628 | 450 | 607 | 641 | 39 |
| 44.0 | 46.0 | -124.0 | -122.0 | 2.0 | 633 | 3 | 503 | 322 | 431 | 627 | 36 |
| 54.0 | 57.0 | -134.0 | -131.0 | 3.0 | 376 | 162 | 330 | 171 | 376 | 376 | 26 |
| 55.0 | 57.0 | -133.5 | -131.5 | 2.0 | 373 | 162 | 329 | 171 | 373 | 373 | 23 |
| 60.5 | 63.5 | -146.5 | -143.5 | 3.0 | 318 | 163 | 287 | 171 | 301 | 301 | 36 |
| 60.5 | 62.5 | -148.0 | -146.0 | 2.0 | 255 | 249 | 250 | 144 | 255 | 253 | 5 |
| 57.0 | 60.0 | -153.5 | -150.5 | 3.0 | 206 | 133 | 181 | 97 | 206 | 205 | 9 |
| 61.5 | 63.5 | -146.0 | -144.0 | 2.0 | 206 | 93 | 188 | 114 | 195 | 195 | 19 |
| 35.0 | 38.0 | -84.0 | -81.0 | 3.0 | 195 | 11 | 140 | 120 | 190 | 195 | 41 |
| 57.5 | 59.5 | -153.0 | -151.0 | 2.0 | 194 | 132 | 172 | 90 | 194 | 194 | 6 |
| 34.5 | 36.5 | -83.5 | -81.5 | 2.0 | 179 | 9 | 131 | 111 | 174 | 179 | 33 |
| 63.0 | 66.0 | -149.5 | -146.5 | 3.0 | 164 | 113 | 146 | 69 | 152 | 152 | 23 |
| 62.5 | 64.5 | -150.0 | -148.0 | 2.0 | 145 | 111 | 139 | 67 | 145 | 145 | 9 |
| 39.0 | 42.0 | -76.5 | -73.5 | 3.0 | 101 | 9 | 74 | 68 | 101 | 101 | 25 |
| 42.0 | 45.0 | -124.5 | -121.5 | 3.0 | 90 | 1 | 66 | 49 | 63 | 84 | 38 |

## 5. Proposal (for CP1 confirmation)

- Inventories in region positives: {'AK DOT': 3371}; families: {'fall': 3156, 'slide': 208, 'flow': 7}.
- **Region bbox**: lat [59.5, 62.5), lon [-150.5, -147.5) (3.0° window).
- Positive zone-days C≥3: 3175 (C≥5: 3175; excl. EQ-triggered inventories: 3170); fall-family zone-days: 2982; storm clusters: 302.
- Meets heuristic (≥150 total, ≥30 test): **yes**.
- **Splits** (chronological, 30-day gaps, ~[0.6, 0.2, 0.2] of positive zone-days):

| split | start | end | pos_zone_days | storm_clusters |
|---|---|---|---|---|
| train | 2006-01-01 | 2015-02-10 | 1892 | 143 |
| val | 2015-03-13 | 2018-03-15 | 611 | 62 |
| test | 2018-04-15 | 2022-06-30 | 602 | 88 |

  Positive zone-days lost in gaps: 48. Split counts use `pos_zone_days_no_eq` positives.
  EQ-triggered zone-days in region (extra, per split): {'train': 0, 'val': 0, 'test': 4}; dates: ['2020-10-05', '2020-10-17', '2021-08-09', '2022-05-08', '2022-09-15']
  Fall-family zone-days per split: {'train': 1775, 'val': 571, 'test': 578}

  Region positive zone-days by year:

| date | count |
|---|---|
| 2004 | 1 |
| 2005 | 16 |
| 2006 | 268 |
| 2007 | 231 |
| 2008 | 220 |
| 2009 | 226 |
| 2010 | 175 |
| 2011 | 231 |
| 2012 | 175 |
| 2013 | 143 |
| 2014 | 217 |
| 2015 | 236 |
| 2016 | 215 |
| 2017 | 162 |
| 2018 | 175 |
| 2019 | 207 |
| 2020 | 143 |
| 2021 | 90 |
| 2022 | 39 |

### Other top candidates' split check

| bbox | rank_val | fall_zd | main_inventory | train | val | test | test_pos | test_clusters | ok |
|---|---|---|---|---|---|---|---|---|---|
| [59.5,62.5)×[-150.5,-147.5) | 3170 | 2982 | AK DOT | 2006-01-01–2015-02-10 | 2015-03-13–2018-03-15 | 2018-04-15–2022-06-30 | 602 | 88 | True |
| [60.0,62.0)×[-150.0,-148.0) | 2946 | 2763 | AK DOT | 2006-01-01–2015-04-01 | 2015-05-02–2018-03-28 | 2018-04-28–2022-05-19 | 557 | 84 | True |
| [57.0,60.0)×[-137.0,-134.0) | 1761 | 1210 | AK DOT | 2004-01-01–2016-10-07 | 2016-11-07–2019-03-28 | 2019-04-28–2022-10-29 | 337 | 102 | True |
| [58.0,60.0)×[-136.0,-134.0) | 1684 | 1175 | AK DOT | 2004-01-01–2016-10-06 | 2016-11-06–2019-03-31 | 2019-05-01–2022-06-28 | 322 | 98 | True |
| [45.0,48.0)×[-124.0,-121.0) | 1260 | 27 | WA WGS | 1950-01-01–1997-01-24 | 1997-02-24–2009-01-02 | 2009-02-02–2023-04-10 | 220 | 103 | True |

## 6. Caveats

- Dates are local time except EQ inventories (UTC); day-level matching tolerates ±1 d.
- Reporting density changes over decades (more recent events reported) → split counts not stationary.
- Inventory `Notes` are untrusted free text; never used in prompts.

## 7. Yosemite DS746 (rockfall track candidate)

- Rows: 948; exact-dated (Y/M/D): 627; exact since 1950: **550**; distinct dates since 1950: **423**.
- No coordinates in sheet (named locations only) → whole valley ≈ 1–2 zones (0.25°). Eyewitness/reporting bias.

- Exact since 1950 by 5-yr bin:

|   date |   n |
|-------:|----:|
|   1950 |   6 |
|   1955 |  15 |
|   1960 |   6 |
|   1970 |   2 |
|   1975 |   1 |
|   1980 |  34 |
|   1985 |  33 |
|   1990 |   8 |
|   1995 |  30 |
|   2000 |  85 |
|   2005 | 213 |
|   2010 | 117 |

- `Type of slope movement` (exact since 1950): {'RF': 419, 'RS': 85, 'DF': 23, 'DS': 14, 'RS/RF': 5, 'RF/DS': 2, 'RF/RS': 1, 'SA': 1}
- `Triggering condition(s)` (exact since 1950, top 12): {'UNR': 183, 'P': 155, 'UKN': 69, 'SM': 24, 'P, F/T': 22, 'EQ': 16, 'CP': 14, 'F/T': 13, 'R/S': 13, 'TS': 10, 'SM, F/T': 4, 'B': 4}
