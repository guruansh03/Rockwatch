"""Rain-group features (§7). Input: one zone's daily weather sorted by date, contiguous days.
Every feature at day d uses only rows ≤ d."""
from __future__ import annotations

import numpy as np
import pandas as pd

MM_PER_IN = 25.4
RAIN_COLS = ["P1", "P3", "P15", "P30", "API", "precip_hours", "intensity", "seattle_ct_margin_in", "rain_on_snow"]


def antecedent_index(p: pd.Series, k: float = 0.9) -> pd.Series:
    """API_d = k·API_{d-1} + P_d (NaN days contribute 0 but are flagged by quality)."""
    out = np.empty(len(p))
    acc = 0.0
    for i, v in enumerate(p.fillna(0.0).to_numpy()):
        acc = k * acc + v
        out[i] = acc
    return pd.Series(out, index=p.index)


def seattle_margin_in(p3_mm: pd.Series, p15_mm: pd.Series) -> pd.Series:
    """USGS Seattle cumulative threshold margin: P3_in − (3.5 − 0.67·P15_in). >0 ⇒ above threshold."""
    return p3_mm / MM_PER_IN - (3.5 - 0.67 * (p15_mm / MM_PER_IN))


def rain_features(w: pd.DataFrame, api_k: float = 0.9) -> pd.DataFrame:
    """w columns: date, precipitation_sum, rain_sum, snowfall_sum, precipitation_hours, temperature_2m_max."""
    p = w["precipitation_sum"]
    f = pd.DataFrame({"date": w["date"].values}, index=w.index)
    f["P1"] = p
    f["P3"] = p.rolling(3, min_periods=3).sum()
    f["P15"] = p.shift(3).rolling(15, min_periods=15).sum()      # d-17 .. d-3
    f["P30"] = p.rolling(30, min_periods=30).sum()
    f["API"] = antecedent_index(p, api_k)
    f["precip_hours"] = w["precipitation_hours"]
    f["intensity"] = p / np.maximum(w["precipitation_hours"].fillna(0), 1.0)
    f["seattle_ct_margin_in"] = seattle_margin_in(f["P3"], f["P15"])
    snow7 = w["snowfall_sum"].rolling(7, min_periods=1).sum()
    f["rain_on_snow"] = ((w["rain_sum"] > 0) & (snow7 > 0) & (w["temperature_2m_max"] > 0)).astype(float)
    return f
