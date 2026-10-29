"""Baselines (§10), evaluated on the same split as RockWatch. Tunable thresholds use VALIDATION only.
B1 P1 ≥ q (q tuned on val) · B2 USGS Seattle cumulative threshold (fixed; designed for Seattle)
B3 seasonal climatology (train zone×month rate, threshold tuned on val) · B4 random alerts at the same
alert-day fraction as RockWatch · B5 rain-only modality (= ablation 'rain')."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from rockwatch.eval.matching import Frame, match
from rockwatch.eval.metrics import metrics
from rockwatch.fusion.thresholds import grid, sweep


def tune_threshold(fr_val: Frame, score: np.ndarray, n: int) -> float:
    """argmax val F1_at over score quantiles."""
    ts = grid(score[fr_val.in_period], n)
    sw = sweep(fr_val, score, ts)
    f1s = np.array([m["f1_at"] if m["f1_at"] is not None else -1 for m in sw])
    return float(ts[int(f1s.argmax())])


def climatology_score(panel: pd.DataFrame, k: float, y_col: str = "y") -> np.ndarray:
    """Train-period zone×month positive rate, shrunk toward region×month rate with weight k."""
    tr = panel[panel["split"] == "train"]
    mo_all = panel["date"].dt.month
    mo_tr = tr["date"].dt.month
    reg = tr.groupby(mo_tr)[y_col].mean()
    zm = tr.groupby([tr["zone_id"], mo_tr])[y_col].agg(["sum", "size"])
    key = pd.MultiIndex.from_arrays([panel["zone_id"], mo_all])
    s = zm.reindex(key)
    r = mo_all.map(reg).to_numpy()
    return ((s["sum"].fillna(0).to_numpy() + k * r) / (s["size"].fillna(0).to_numpy() + k))


def random_alerts(fr: Frame, alert_frac: float, draws: int, seed: int, bootstrap: Any = None) -> dict[str, Any]:
    """Random raw alerts with rate f' so that post-hysteresis active fraction ≈ alert_frac."""
    rng = np.random.default_rng(seed)
    fprime = 1 - np.sqrt(max(0.0, 1 - alert_frac))
    ms = []
    for _ in range(draws):
        raw = (rng.random(len(fr.day)) < fprime).astype(np.int8) * 2
        ms.append(metrics(match(fr, raw, 2)))
    keys = ["recall_before", "recall_at", "precision_episode", "precision_day", "f1_at", "false_alarms_per_zone_year", "alert_day_fraction"]
    out: dict[str, Any] = {"draws": draws, "target_alert_day_fraction": alert_frac}
    for k in keys:
        v = np.array([m[k] for m in ms if m[k] is not None], float)
        out[k] = float(v.mean()) if len(v) else None
        out[k + "_range95"] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else None
    return out
