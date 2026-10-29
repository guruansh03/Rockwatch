"""Threshold selection on VALIDATION only (§8).
t1: largest t with val recall_at ≥ t1_recall.   t2: argmax val F1_at (episode precision × recall_at).
t3: among t ≥ t2, max L3 episode precision with recall_at ≥ t3_min_recall, L3 requiring corroboration
(≥2 dynamic modalities with positive contribution; LLM CONFIRM added in P4). Unattainable → L3 disabled."""
from __future__ import annotations

from typing import Any

import numpy as np

from rockwatch.eval.matching import Frame, match
from rockwatch.eval.metrics import metrics


def grid(p: np.ndarray, n: int) -> np.ndarray:
    q = np.unique(np.quantile(p, np.linspace(0.0, 0.9995, n)))
    return q


def sweep(fr: Frame, p: np.ndarray, ts: np.ndarray, gate: np.ndarray | None = None, level: int = 2) -> list[dict[str, Any]]:
    """Metrics for raw = level·(p ≥ t [& gate]) at each t."""
    out = []
    for t in ts:
        on = p >= t
        if gate is not None:
            on &= gate
        m = metrics(match(fr, on.astype(np.int8) * level, level))
        m["t"] = float(t)
        out.append(m)
    return out


def choose(fr: Frame, p: np.ndarray, n_dyn_pos: np.ndarray, cfg: dict[str, Any]) -> dict[str, Any]:
    """Return thresholds + the val sweep (for PR curves). fr/p/n_dyn_pos are val-period aligned arrays."""
    tc = cfg["thresholds"]
    ts = grid(p[fr.in_period], tc["n_grid"])
    sw = sweep(fr, p, ts)
    f1s = np.array([m["f1_at"] if m["f1_at"] is not None else -1 for m in sw])
    t2 = float(ts[int(f1s.argmax())])
    rec = np.array([m["recall_at"] or 0 for m in sw])
    ok1 = ts[rec >= tc["t1_recall"]]
    t1 = float(ok1.max()) if len(ok1) else float(ts.min())
    t1 = min(t1, t2)
    gate = n_dyn_pos >= tc["corroboration_min_dynamic"]
    sw3 = sweep(fr, p, ts[ts >= t2], gate=gate, level=3)
    cand = [m for m in sw3 if (m["recall_at"] or 0) >= tc["t3_min_recall"] and m["precision_episode"] is not None]
    if cand:
        best = max(cand, key=lambda m: (m["precision_episode"], m["recall_at"]))
        t3, l3 = best["t"], True
    else:
        t3, l3 = None, False
    return {"t1": t1, "t2": t2, "t3": t3, "l3_enabled": l3, "rule_t1": f"max t: val recall_at>={tc['t1_recall']}",
            "rule_t2": "argmax val F1_at", "rule_t3": f"max L3 precision s.t. recall_at>={tc['t3_min_recall']} & corroboration",
            "sweep": [{k: m[k] for k in ("t", "recall_at", "recall_before", "precision_episode", "precision_day", "f1_at", "alert_day_fraction")} for m in sw]}


def raw_levels(p: np.ndarray, n_dyn_pos: np.ndarray, th: dict[str, Any], min_dyn: int = 2,
               confirm: np.ndarray | None = None) -> np.ndarray:
    """Deterministic provisional level per row (before hysteresis)."""
    lv = np.zeros(len(p), np.int8)
    lv[p >= th["t1"]] = 1
    lv[p >= th["t2"]] = 2
    if th.get("l3_enabled") and th.get("t3") is not None:
        corr = n_dyn_pos >= min_dyn
        if confirm is not None:
            corr = corr | confirm
        lv[(p >= th["t3"]) & corr] = 3
    return lv
