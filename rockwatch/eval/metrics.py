"""Metrics from match() counts (§10)."""
from __future__ import annotations

from typing import Any

import numpy as np


def _div(a: float, b: float) -> float | None:
    return float(a) / float(b) if b else None


def f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None or (p + r) == 0:
        return None if p is None or r is None else 0.0
    return 2 * p * r / (p + r)


def metrics(c: dict[str, Any]) -> dict[str, Any]:
    """Recall over exact event-days (+short-range in TP_at), episode/day precision, F1, FA/zone-yr, alert fraction."""
    n_ev = c["n_event_days"]
    rec_b = _div(c["tp_before"], n_ev)
    rec_a = _div(c["tp_at"] + c.get("short_range_matched", 0), n_ev + c.get("n_short_range", 0))
    prec_ep = _div(c["episodes_tp"], c["n_episodes"])
    prec_day = _div(c["alert_days_hit"], c["alert_days"])
    zy = c["zone_days"] / 365.25
    out = {
        "n_event_days": n_ev, "n_short_range": c.get("n_short_range", 0),
        "recall_before": rec_b, "recall_at": rec_a,
        "precision_episode": prec_ep, "precision_day": prec_day,
        "f1_at": f1(prec_ep, rec_a), "f1_before": f1(prec_ep, rec_b), "f1_day": f1(prec_day, rec_a),
        "n_episodes": c["n_episodes"], "episodes_tp": c["episodes_tp"], "episodes_fp": c["episodes_fp"],
        "false_alarms_per_zone_year": _div(c["episodes_fp"], zy),
        "alert_day_fraction": _div(c["alert_days"], c["zone_days"]),
        "zone_days": c["zone_days"],
    }
    if "lead_days" in c:
        ld = np.asarray(c["lead_days"])
        out["lead_days"] = {"n": int(len(ld)), "median": float(np.median(ld)) if len(ld) else None,
                            "mean": float(ld.mean()) if len(ld) else None,
                            "hist": {int(k): int(v) for k, v in zip(*np.unique(ld, return_counts=True))} if len(ld) else {}}
    return out
