# 5-minute demo script

Pre-flight: weather + models built (`build-data`, `train`); `.env` with `ROCKWATCH_LLM_PROVIDER` (mock works offline).

1. **(0:00) Launch** — `python -m rockwatch run-demo --scenario test_storm --llm on` (after CP2; `dev_val` before).
   Browser opens http://localhost:8501. Point at the banner: sim day, zones at L2+, unacked alerts, degraded count.
2. **(0:40) Map** — zones turn yellow/orange/red as the storm arrives. Toggle ground truth: blue dots appear only after a day closes
   (the system never sees them).
3. **(1:30) Zone detail** — pick an orange zone: P1/P3/P15 bars vs the Seattle threshold line (designed for Seattle);
   contribution bars explain *why* (rain vs susceptibility vs thermal vs seismic); p timeline with t1/t2/t3.
4. **(2:15) Alerts** — composed message (headline, body, allowed actions only), verifier decision + rationale with evidence ids.
   Press **Ack**; unacked alerts re-notify after 2 sim-days.
5. **(3:00) Fault injection** (sidebar) — *Kill RainSensor*: Agents tab shows STALE, banner turns red, fused risks degraded.
   *Restart it*. *LLM offline*: verifier → fallback, messages → template. *Drop a zone's data*: QualityAgent flags it missing.
6. **(3:50) Evaluation tab** — final test report: RockWatch vs B1–B5 with CIs, ablations, ± LLM-Verifier, PR curve, lead-days.
   Say the banner out loud: US natural slopes, not mine performance; precision is a lower bound; lead time in days.
7. **(4:30) Ask Analyst** — "Which alerts were raised in r9c8?" (cited record ids). "When will r9c8 fail?" → refusal.
