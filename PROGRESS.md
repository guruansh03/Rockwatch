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

## Phase 4 — LLM agents — DONE with mock; real-provider smoke run PENDING (needs API key / Ollama)
### Done
- `llm/{provider,anthropic_provider,ollama_provider,mock_provider,cache,guardrails,runtime,evidence}.py`, `llm/prompts/*.md`.
- Agents: LLM-Verifier (tools; live BusStore / batch PanelStore), LLM-AlertComposer (own process), LLM-Analyst (`rockwatch ask`).
- `eval --llm on` (full ± verifier rows in ablation.md, llm_usage.json); `run-demo --llm on`; `llm-smoke --provider ...` writes reports/llm_smoke_*.json.
- Tests: 61 passing incl. `test_guardrails.py` (never-raise, forbidden downgrades ×3, numbers, ids, invalid JSON retry→fallback, L3 corroboration, cache, cap, composer actions/template, analyst refusals/citations).
- Mock runs: 20-day multi-process demo with verifier+composer (83 LLM calls, 23 messages); val eval with 500-call cap.
### Pending
- Real-provider smoke run: put ANTHROPIC_API_KEY in `.env` (or run Ollama natively) → `python -m rockwatch llm-smoke --provider anthropic`.

## Phase 5 — dashboard — DONE
- `dashboard/app.py` (+ `dashboard/data.py`): Map (pydeck levels + closed-day truth overlay), Zone detail (P1/P3/P15 vs Seattle line,
  contribution bars, p timeline with t1–t3), Alerts (composed message, verifier decision/rationale, Ack), Agents (heartbeats, stale, LLM log),
  Evaluation (reports + live), Ask Analyst; sidebar faults (kill/restart RainSensor, LLM offline, drop zone); footer citations/disclaimer.
- `run-demo` (non-headless) spawns the dashboard (http://localhost:8501). Manual runs recorded 2026-10-29: dev_val 25 d with `--llm on`
  (dashboard health ok after 14 s, 63 composed messages); dev_val_Y 30 d (`--llm on`, 34 LLM calls, 4 messages); dev_val 60 d kill test (P3).
- Tests: 63 passing incl. `test_dashboard.py` (AppTest render + helpers).

## Phase 6 — final evaluation — PREPARED, STOPPED AT CP2
- Region Y weather complete → built, trained, val report possible. Region A: 26/70 zones (Open-Meteo daily quota; resumes 00:05 UTC).
- `rockwatch cp2-packet` → `docs/cp2_packet_A.md`, `docs/cp2_packet_Y.md`: val metrics under both t2 rules + proposed test scenarios.
- Final run NOT executed (CP2 requires human approval).

## Phase 7 — polish — DONE except numbers
- README (setup per OS, pipeline, mermaid, limitations, mine path), docs/architecture.md, evaluation.md, demo_script.md, llm_guardrails.md.
- README results section waits for the final test run (numbers will be copied verbatim).

## Control room UI — DONE (2026-10-30)
- `rockwatch ui` / `run-demo` → http://localhost:8600: Overview (map, timeline, alerts), Zone detail, Alerts (ack), Agents (heartbeats,
  faults, LLM log), Evaluation (reports), Analyst. Light/dark, keyboard, reduced motion, offline-capable (vendored Leaflet + fonts).
- Verified with a headless browser on a live 60-day replay (pause/resume, kill/restart sensor, acknowledge, analyst) — no page errors.
- Report figures restyled to the UI palette; lead-days histogram capped at 30+ days.
- Tests: 65 + streamlit test (skips without streamlit) incl. `test_web_api.py`.

## CP2 (partial) — 2026-10-30
- t2_rule = f1_day approved (D-049); models retrained; val reports + CP2 packets regenerated
  (Y val: recall_at 0.475 [0.32–0.62], day precision 0.33, alert-day fraction 0.21 vs random 0.28 recall at the same rate).
- Pending: demo-scenario approval, final-run go/no-go, Alaska weather (31 zones) → rebuild/retrain before the final run.
- India track dropped (D-050).

## CP2 — APPROVED (2026-10-30)
- Demo scenarios approved (D-052); go for the final run. Final run waits for Alaska weather (31 zones) → `RUN_ALASKA_PIPELINE.bat`
  on the PC, then `FINAL_TEST_EVAL.bat`. Test scenarios locked until a final report exists (D-053).
- UI round 2 (D-054/D-055): keyless basemaps, replay track + day inspection, speed control, LLM pill, alert grouping, t2≈t3 note.
  Verified headless: day inspection (KPIs/map/truth switch to the day, ←/→/Esc), speed 2× → 0.75 s/day observed, pause/resume,
  kill → STALE banner, restart; 65 tests pass.

## Alaska data COMPLETE — 2026-10-31
- Weather 70/70 zones (finished in the cloud sandbox after the PC hit the Open-Meteo daily quota; D-057). build-data → train → val eval.
- A val (eval_20261031_002422_A_val, t2_rule f1_day): recall_at 0.429 [0.278–0.570], recall_before 0.406, day precision 0.047
  [0.031–0.063], episode precision 0.123, alert-day fraction 0.105, 1.87 false alarms / zone-year, 611 event-days.
  Baselines on val: B4 random at same rate recall_at 0.150; B5 rain-only 0.370 (alert 0.193); B1 daily rain 0.815 at 0.737 alert-days;
  B3 seasonal climatology recall_at 0.296 with day precision 0.303 at 0.011 alert-days (strong; reported as is).
- 12-day live check with all 70 zones: 840 fused messages, no degraded days, no supervisor flags.
- Next: FINAL_TEST_EVAL.bat (CP2 approved).

## Groq LLM — 2026-11-06
- `rockwatch/llm/groq_provider.py` + factory/runtime/UI support; 6 offline tests (request shape, 429 retry, param fallback, cap).
- `.env` on the PC: provider groq + key. `FINAL_TEST_EVAL.bat` detects the Groq key → smoke test → final eval with ± LLM.

## Phase 6 — FINAL TEST EVAL — DONE (2026-11-06, run once, git 28e2d92)
- A: recall_at 0.469 [0.372–0.557], day precision 0.035 [0.026–0.045], alert-day fraction 0.111 vs random 0.168 / 0.009.
- Y: recall_at 0.238 [0.118–0.352], day precision 0.231 [0.123–0.351] vs random 0.231 / 0.216 — no skill on test.
- LLM-Verifier (Groq, cap 80): no effect on A; slightly negative on Y; many fallbacks (guardrail, cap, free-tier token limit).
- README Results filled from the test reports. Test-period scenarios now replayable.

## Deviations
- DECISIONS.md D-001..D-019.
