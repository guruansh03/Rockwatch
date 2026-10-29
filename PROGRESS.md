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

## Phase 3 — agents + bus + replay — DONE (on partial data)
### Done
- `schemas.py` (Envelope), `bus/{base,memory,sqlite_bus}.py` (+ redis stub), runtime truth access control.
- Agents (one OS process each): sensor_rain ×2 groups, sensor_thermal, sensor_seismic, quality, evidence_{rain,thermal,seismic,susceptibility},
  context, fusion, verifier (pass-through until P4), alert (hysteresis, dedupe, ack, re-notify, restore), supervisor (stale/recovered/restart), evaluator (live + offline recompute).
- `replay/{clock,engine,scenarios,launcher}.py`; CLI `run-demo --headless [--kill-agent X --kill-at-day N] [--auto-restart ...]`, `agents status|kill`.
- Headless multi-process run: 60 sim-days, 15 processes, 60/60 daily states, 1,200 fused zone-days; killing sensor_rain_0 at day 20 →
  supervisor `agent_stale`, its 10 zones' rain evidence `missing`, fusion degraded, `agents status` shows stale.
- Tests: 47 passing incl. `test_parity_batch_vs_live.py` (30 d, atol 1e-9) and `test_truth_isolation.py` (static + runtime, memory + sqlite).
### Known issue (needs decision)
- On the 20-zone partial data the val rule "t2 = argmax F1_at (episode precision)" picks the lowest threshold → near always-on alerts
  (alert-day fraction ≈0.8–1.0 in the dev replay). Episode precision is inflated by long episodes. Options: F1 with day-level precision, or an alert-day-fraction cap.
### Pending
- Weather for remaining A zones (20/70 cached).

## Deviations
- DECISIONS.md D-001..D-019.
