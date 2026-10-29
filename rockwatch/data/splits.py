"""Chronological splits (§6.5) with gaps. Dates outside every split -> 'gap' or 'outside'."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SPLITS = ("train", "val", "test")


def split_ranges(region_cfg: dict[str, Any]) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    return {k: (pd.Timestamp(v[0]), pd.Timestamp(v[1])) for k, v in region_cfg["splits"].items()}


def validate(region_cfg: dict[str, Any], min_gap_days: int = 30) -> None:
    """Raise if splits overlap, are out of order, or gaps < min_gap_days."""
    r = split_ranges(region_cfg)
    for k in SPLITS:
        if r[k][0] > r[k][1]:
            raise ValueError(f"{k} start after end")
    for a, b in (("train", "val"), ("val", "test")):
        gap = (r[b][0] - r[a][1]).days - 1
        if gap < min_gap_days:
            raise ValueError(f"gap {a}->{b} = {gap} d < {min_gap_days}")


def assign_split(dates: pd.Series, region_cfg: dict[str, Any]) -> pd.Series:
    r = split_ranges(region_cfg)
    lab = np.full(len(dates), "outside", dtype=object)
    lo, hi = r["train"][0], r["test"][1]
    lab[((dates >= lo) & (dates <= hi)).to_numpy()] = "gap"
    for k in SPLITS:
        lab[((dates >= r[k][0]) & (dates <= r[k][1])).to_numpy()] = k
    return pd.Series(lab, index=dates.index, dtype="string")
