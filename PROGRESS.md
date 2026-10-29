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

## Phase 2 — fusion + baselines + eval harness (val only) — CODE DONE, full-data rerun pending
### Done
- `fusion/{model,thresholds}.py`: L2-LR with per-modality contributions (clip ±3), quality weights, Platt on val, t1/t2/t3 rules (L3 corroborated).
- `eval/{matching,metrics,bootstrap,baselines,runner,report}.py`; CLI `train`, `eval --split val` (test guarded).
- Report folder: metrics.json/.md, pr_curve.png, lead_days.png, ablation.md, llm_usage.json, frozen config + git hash, banner.
- Tests: 33 passing (8 matching cases incl. short-range, multi-event, zone boundaries, period clipping, bootstrap; CLI test guard).
- Smoke run on PARTIAL data (14/70 A zones): val recall_at 0.61, episode precision 0.25, alert-day fraction 0.22.
  Observation: B3 seasonal climatology strong on val (zone×month prior). Re-check on full data.
### Pending
- Full A (70 zones) + Yosemite weather → rebuild → train → val report.

## Deviations
- DECISIONS.md D-001..D-019.
