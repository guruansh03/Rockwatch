# Evaluation protocol (fixed; §10)

- Unit: positive event-day = (zone, d) with ≥1 exact-dated inventory event (C ≥ 3). Alert episode = consecutive days at ≥ L2.
- TP_before: L2+ from data ≤ d−1 active on d. TP_at: L2+ from data ≤ d (includes TP_before). FN otherwise.
- Episode TP: overlaps [d_e−1, d_e] (or a short-range window). Day-level precision: alert-day with an event that day or the next.
- Hysteresis: active[d] = max(raw[d], raw[d−1]) (escalate now, de-escalate after 2 lower days).
- Metrics: recall_before, recall_at, episode & day precision, F1 (episode / day), false alarms per zone-year, alert-day fraction, lead days.
- 95% CI: block bootstrap over storm clusters (events ≤3 d apart region-wide), 1,000 resamples.
- Baselines on the same split: B1 P1 ≥ q (val-tuned), B2 USGS Seattle cumulative threshold (designed for Seattle), B3 train
  zone×month climatology (val-tuned), B4 random alerts at RockWatch's alert-day fraction, B5 rain-only modality.
- Ablations: rain → +susceptibility → +thermal → +seismic → full (+context); full ± LLM-Verifier.
- Thresholds, calibration and baseline cut-offs use the validation split only. The test split is evaluated once with
  `eval --split test --final` after CP2; reruns require `--force-rerun-with-reason` (logged).
- Honesty: US natural-slope / road-cut data, not mine performance; precision is a lower bound (unreported events); lead time in days.

Implementation: `rockwatch/eval/{matching,metrics,bootstrap,baselines,runner,report}.py`; hand-built cases in `tests/test_matching.py`.
