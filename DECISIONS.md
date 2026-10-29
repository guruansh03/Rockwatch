# DECISIONS

- **D-001 (P0)** Exact-day event = `Date_Min` set and (`Date_Max` empty **or `Date_Max == Date_Min`**). Same-day range carries no extra uncertainty; simplest valid reading. Folded into `exact`; revisit at CP1.
- **D-002 (P0)** `Date_Max < Date_Min` rows: swap; count reported in profile.
- **D-003 (P0)** `Lon_W` sign: if >50% of values positive, negate whole column; residual positive count reported.
- **D-004 (P0)** Type family: lowercase substring match, priority fall > flow > slide > unknown; nonempty unmatched → `other`, empty → `unknown`. "debris avalanche" → flow. Exclusions (gully, avalanche chute, snow avalanche, sinkhole, subsidence, erosion) checked first. Table in `config/default.yaml`; top-40 raw LS_Type→family mapping printed in profile for CP1 review.
- **D-005 (P0)** Region unit = square bbox (2° / 3°, 0.5° step) over 0.25° zone centres, greedy non-overlapping, ranked by C≥C_min exact-dated positive zone-days since 1950. No state polygons (no geopandas). Inventory names shown for state context.
- **D-006 (P0)** Split proposal: boundaries at 60/20/20 cumulative positive-zone-day quantiles, 30-day gap after train and val; start 1950-01-01; end = last event date in region. Heuristic thresholds ≥150 total / ≥30 test (enough for bootstrap CIs with ~dozens of storm clusters); storm-cluster counts also reported since effective sample size = clusters, not zone-days.
- **D-007 (P0)** Sandbox egress blocks data hosts → stopped per §1/§3 rather than substituting any other source.
