"""Alert/event matching (§10). Pure, vectorised; shared by eval, threshold tuning and live replay.

Conventions (panel sorted by zone, date; contiguous daily rows per zone):
- raw level r[d] ∈ {0..3} computed from data ≤ d.
- hysteresis: escalate immediately, de-escalate only after 2 consecutive lower days
  ⇒ active[d] = max(r[d], r[d-1]) within zone.
- level active during day d from data ≤ d−1 = active[d−1].
- TP_before(d): active[d−1] ≥ L;  TP_at(d): active[d] ≥ L or active[d−1] ≥ L;  FN otherwise.
- Episode: maximal run of consecutive days with active ≥ L in a zone. TP if it contains d_e−1 or d_e
  for an exact event (or any day of a short-range window [Date_Min−1, Date_Max]); else FP.
- Day-level precision: alert zone-day a is a hit if an exact event is on a or a+1, or a lies in a
  short-range window.
- Short-range events: matched if active ≥ L on any day of [Date_Min−1, Date_Max]; TP_at only.
- Lead days (TP_at events) = d_e − start of the matched episode (0 = same-day only).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


def hysteresis(raw: np.ndarray, zone_start: np.ndarray) -> np.ndarray:
    """active[d] = max(raw[d], raw[d-1]) within zone. zone_start marks each zone's first row."""
    prev = np.roll(raw, 1)
    prev[zone_start] = 0
    return np.maximum(raw, prev)


def shift_in_zone(a: np.ndarray, zone_start: np.ndarray, k: int, fill=False) -> np.ndarray:
    """Shift by k rows (k=1 → previous day, k=-1 → next day) without crossing zone boundaries."""
    out = np.roll(a, k)
    if k == 1:
        out[zone_start] = fill
    elif k == -1:
        zone_end = np.roll(zone_start, -1)  # last row of each zone
        out[zone_end] = fill
    else:
        raise ValueError("k must be ±1")
    return out


@dataclass
class Frame:
    """Pre-indexed panel arrays for fast repeated matching (threshold sweeps)."""
    zone: np.ndarray            # int codes
    day: np.ndarray             # int days since epoch
    zone_start: np.ndarray      # bool
    in_period: np.ndarray       # bool
    y: np.ndarray               # bool exact event-day, restricted to period
    sr_window: np.ndarray       # bool row in any short-range window (period-restricted)
    sr_rows: list[np.ndarray] = field(default_factory=list)   # row indices per short-range event
    keys: pd.DataFrame | None = None  # zone_id, date (for exporting)
    zone_ids: np.ndarray | None = None
    event_meta: pd.DataFrame | None = None  # per exact event-day row: subset flags


def make_frame(panel: pd.DataFrame, period: tuple[str, str], short_events: pd.DataFrame | None = None,
               y_col: str = "y") -> Frame:
    """panel: zone_id, date, y (+ optional subset columns). Must have contiguous daily rows per zone."""
    p = panel.sort_values(["zone_id", "date"]).reset_index(drop=True)
    codes, zids = pd.factorize(p["zone_id"])
    day = (p["date"].values.astype("datetime64[D]").astype(np.int64))
    zs = np.r_[True, codes[1:] != codes[:-1]]
    gap = np.r_[1, np.diff(day)]
    if np.any(gap[~zs] != 1):
        raise ValueError("panel rows not contiguous daily within a zone")
    a, b = (np.datetime64(period[0], "D").astype(np.int64), np.datetime64(period[1], "D").astype(np.int64))
    inp = (day >= a) & (day <= b)
    y = (p[y_col].to_numpy() > 0) & inp
    srw = np.zeros(len(p), bool)
    sr_rows = []
    if short_events is not None and len(short_events):
        zmap = {z: i for i, z in enumerate(zids)}
        first = {}
        for i in np.flatnonzero(zs):
            first[codes[i]] = (i, day[i])
        for e in short_events.itertuples():
            if e.zone_id not in zmap:
                continue
            zc = zmap[e.zone_id]
            i0, d0 = first[zc]
            lo = np.datetime64(pd.Timestamp(e.date_min).date(), "D").astype(np.int64) - 1
            hi = np.datetime64(pd.Timestamp(e.date_max).date(), "D").astype(np.int64)
            if hi < a or lo > b:
                continue
            rows = np.arange(i0 + max(lo, a) - d0, i0 + min(hi, b) - d0 + 1)
            rows = rows[(rows >= 0) & (rows < len(p))]
            rows = rows[codes[rows] == zc]
            if len(rows):
                sr_rows.append(rows)
                srw[rows] = True
    meta_cols = [c for c in ("y_fall", "y_no_eq", "y_c5", "month") if c in p.columns]
    meta = p.loc[y, ["zone_id", "date"] + meta_cols].copy() if y.any() else None
    return Frame(codes, day, zs, inp, y, srw, sr_rows, p[["zone_id", "date"]], zids, meta)


def match(fr: Frame, raw_level: np.ndarray, level_min: int = 2, with_details: bool = False) -> dict[str, Any]:
    """Match alerts (raw per-row levels, same order as frame) against events. Returns counts (+details)."""
    act = hysteresis(raw_level.astype(np.int8), fr.zone_start)
    A = act >= level_min
    Ap = shift_in_zone(A, fr.zone_start, 1, False)
    tpb = fr.y & Ap
    tpa = fr.y & (A | Ap)
    y_next = shift_in_zone(fr.y, fr.zone_start, -1, False)
    hit = fr.y | y_next | fr.sr_window
    Ae = A & fr.in_period
    starts = A & ~Ap
    ep_id = np.cumsum(starts) - 1   # valid where A
    # episodes that touch the period
    ids_in = np.unique(ep_id[Ae])
    ep_hit = np.zeros(ep_id.max() + 1 if A.any() else 0, bool)
    if A.any():
        np.logical_or.at(ep_hit, ep_id[Ae], hit[Ae])
    n_ep = len(ids_in)
    n_ep_tp = int(ep_hit[ids_in].sum()) if n_ep else 0
    sr_matched = sum(bool(A[r].any()) for r in fr.sr_rows)
    n_ev = int(fr.y.sum())
    res = {
        "n_event_days": n_ev, "tp_before": int(tpb.sum()), "tp_at": int(tpa.sum()),
        "n_short_range": len(fr.sr_rows), "short_range_matched": int(sr_matched),
        "n_episodes": n_ep, "episodes_tp": n_ep_tp, "episodes_fp": n_ep - n_ep_tp,
        "alert_days": int(Ae.sum()), "alert_days_hit": int((Ae & hit).sum()),
        "zone_days": int(fr.in_period.sum()),
    }
    if with_details:
        # episode start day per row (forward fill of start days within A runs)
        sd = (pd.Series(np.where(starts, fr.day, np.nan)).groupby(fr.zone).ffill()
              .fillna(0).to_numpy().astype(np.int64))  # valid where A (runs contiguous, start first)
        sd_prev = shift_in_zone(sd, fr.zone_start, 1, 0)
        lead = np.where(Ap, fr.day - sd_prev, np.where(A, 0, -1))
        res["lead_days"] = lead[tpa].astype(int).tolist()
        res["event_rows"] = np.flatnonzero(fr.y)
        res["tp_before_mask"] = tpb[fr.y]
        res["tp_at_mask"] = tpa[fr.y]
        res["active"] = act
        res["alert_rows"] = np.flatnonzero(Ae)
        res["episode_start_rows"] = np.flatnonzero(starts & fr.in_period)
        res["episode_tp_by_start"] = ep_hit[ep_id[starts & fr.in_period]] if A.any() else np.array([], bool)
    return res
