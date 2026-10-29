"""Block bootstrap by storm cluster (§10): region-wide event dates within `gap` days form one cluster;
blocks = cluster windows (±gap) and the quiet stretches between them. 1,000 resamples, 95% CI."""
from __future__ import annotations

from typing import Any

import numpy as np

from rockwatch.eval.matching import Frame, shift_in_zone
from rockwatch.eval.metrics import metrics

CI_KEYS = ["recall_before", "recall_at", "precision_episode", "precision_day", "f1_at", "f1_before", "f1_day",
           "false_alarms_per_zone_year", "alert_day_fraction"]


def day_blocks(fr: Frame, gap: int = 3) -> tuple[np.ndarray, int, int]:
    """Block id per period day (offset from period start). Returns (block_of_day, n_blocks, day0)."""
    d_in = fr.day[fr.in_period]
    d0, d1 = int(d_in.min()), int(d_in.max())
    tag = np.full(d1 - d0 + 1, -1, np.int64)
    ev = np.unique(fr.day[fr.y])
    if len(ev):
        cid = np.r_[0, np.cumsum(np.diff(ev) > gap)]
        for c in np.unique(cid):
            lo, hi = ev[cid == c].min() - gap, ev[cid == c].max() + gap
            tag[max(lo, d0) - d0: min(hi, d1) - d0 + 1] = c
    change = np.r_[True, tag[1:] != tag[:-1]]
    blk = np.cumsum(change) - 1
    return blk, int(blk.max()) + 1, d0


def tallies(fr: Frame, det: dict[str, Any], gap: int = 3) -> tuple[np.ndarray, list[str]]:
    """Per-block sums of every count metrics() needs."""
    blk, nb, d0 = day_blocks(fr, gap)
    keys = ["n_event_days", "tp_before", "tp_at", "alert_days", "alert_days_hit", "n_episodes", "episodes_tp", "zone_days"]
    T = np.zeros((nb, len(keys)))

    def add(col: str, rows: np.ndarray, w=None):
        b = blk[fr.day[rows] - d0]
        np.add.at(T[:, keys.index(col)], b, 1 if w is None else w)

    ev = det["event_rows"]
    add("n_event_days", ev)
    add("tp_before", ev, det["tp_before_mask"].astype(float))
    add("tp_at", ev, det["tp_at_mask"].astype(float))
    ar = det["alert_rows"]
    add("alert_days", ar)
    hit = (fr.y | shift_in_zone(fr.y, fr.zone_start, -1, False) | fr.sr_window)[ar]
    add("alert_days_hit", ar, hit.astype(float))
    es = det["episode_start_rows"]
    add("n_episodes", es)
    add("episodes_tp", es, det["episode_tp_by_start"].astype(float))
    add("zone_days", np.flatnonzero(fr.in_period))
    return T, keys


def bootstrap_ci(fr: Frame, det: dict[str, Any], n: int = 1000, seed: int = 0, gap: int = 3) -> dict[str, Any]:
    """Percentile 95% CIs for CI_KEYS."""
    T, keys = tallies(fr, det, gap)
    rng = np.random.default_rng(seed)
    nb = len(T)
    vals: dict[str, list[float]] = {k: [] for k in CI_KEYS}
    for _ in range(n):
        s = T[rng.integers(0, nb, nb)].sum(0)
        c = dict(zip(keys, s))
        c["episodes_fp"] = c["n_episodes"] - c["episodes_tp"]
        m = metrics(c)
        for k in CI_KEYS:
            if m[k] is not None:
                vals[k].append(m[k])
    out = {"n_resamples": n, "n_blocks": nb, "gap_days": gap}
    for k, v in vals.items():
        out[k] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None
    return out
