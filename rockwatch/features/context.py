"""Context features (§7): season (month sin/cos) and regional extent.

Regional extent (D-015): fraction of region zones whose P3 exceeds that zone's VALIDATION-period
median P3 on day d. P3 stands in for "rain-group evidence" to avoid a circular dependency on the
fitted rain coefficients (weather only; no labels)."""
from __future__ import annotations

import numpy as np
import pandas as pd

CONTEXT_COLS = ["month_sin", "month_cos", "regional_extent"]


def season(dates: pd.Series) -> pd.DataFrame:
    m = dates.dt.month
    return pd.DataFrame({"month_sin": np.sin(2 * np.pi * (m - 1) / 12), "month_cos": np.cos(2 * np.pi * (m - 1) / 12)}, index=dates.index)


def regional_extent(panel: pd.DataFrame, val_range: tuple[str, str]) -> pd.Series:
    """panel: zone_id, date, P3. Returns extent per row (same index)."""
    v = panel[(panel["date"] >= val_range[0]) & (panel["date"] <= val_range[1])]
    med = v.groupby("zone_id")["P3"].median()
    # round to 1e-6 mm so batch (pandas rolling) and streaming (numpy) sums compare identically at ties (D-028)
    above = (panel["P3"].round(6) > panel["zone_id"].map(med).round(6)).astype(float)
    above[panel["P3"].isna()] = np.nan
    frac = above.groupby(panel["date"]).mean()
    return panel["date"].map(frac)
