# PROGRESS

## Phase 0 — DONE. CP1 passed 2026-10-29 (D-013).

## Phase 1 — ingestion + features + labels + splits — IN PROGRESS
### Done
- `data/zones.py` (grid, leakage-safe selection), `data/weather.py` (Open-Meteo, cached, budgeted, 429-aware),
  `data/quakes.py` (ComCat by year, cached), `data/labels.py`, `data/splits.py`, `data/build.py`.
- `features/{rainfall,thermal,seismic,susceptibility,context}.py` per §7.
- CLI: `build-zones`, `fetch-weather`, `build-data [--allow-partial]`; data card writer.
- Quakes cached: A 4,561 (max M7.1, incl. 2018-11-30 Anchorage), Y 9,595.
- Tests: 24 passing incl. `test_splits_no_leakage.py` (split gaps, zone/prior selection, feature causality, train-only climatology).
### Pending
- Weather: 14/70 A zones cached; 56 A zones + 4 Yosemite chunks remaining (quota-bound, ~1.5–2 days).
- Full `build-data` + final data card once weather complete.
- CLAUDE.md copy into repo root.

## Deviations
- DECISIONS.md D-001..D-019.
