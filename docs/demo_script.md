# 5-minute demo script

Pre-flight: weather + models built (`build-data`, `train`); `.env` with `ROCKWATCH_LLM_PROVIDER` (mock works offline).

1. **(0:00) Launch** — `START_LIVE_DEMO.bat storm_A` (or `quake_A`, `storm_Y`; replayable after `FINAL_TEST_EVAL.bat`;
   `dev_val` / `dev_val_Y` before). The control room opens at http://localhost:8600. Point at the top bar (sim day, LIVE status,
   **LLM pill** — say "CLAUDE" = real model, "MOCK" = rule stand-in) and the KPI strip.
   `Space` pauses/resumes; `1`–`6` switch views; the **replay track** speed buttons slow the replay down for narration (0.5×).
2. **(0:40) Map** — zones turn yellow/orange/red as the storm arrives. Blue ◆ reported events appear only after a day closes
   (the system never sees them). Pause, then click a red segment on the replay track: the map, KPIs and alerts jump to that day;
   `←`/`→` step, `Esc` returns to the latest day.
3. **(1:30) Zone detail** — pick an orange zone: P1/P3/P15 bars vs the Seattle threshold line (designed for Seattle);
   contribution bars explain *why* (rain vs susceptibility vs thermal vs seismic); p timeline with t1/t2/t3.
4. **(2:15) Alerts** — composed message (headline, body, allowed actions only), verifier decision + rationale with evidence ids.
   Press **Ack**; unacked alerts re-notify after 2 sim-days.
5. **(3:00) Fault injection** (Agents view) — *Kill*: the rain-sensor card turns red (STALE), the red banner appears, degraded count rises.
   *Restart it*. *LLM offline*: verifier → fallback, messages → template. *Drop a zone's data*: QualityAgent flags it missing.
6. **(3:50) Evaluation tab** — final test report: RockWatch vs B1–B5 with CIs, ablations, ± LLM-Verifier, PR curve, lead-days.
   Say the banner out loud: US natural slopes, not mine performance; precision is a lower bound; lead time in days.
7. **(4:30) Ask Analyst** — "Which alerts were raised in r9c8?" (cited record ids). "When will r9c8 fail?" → refusal.
