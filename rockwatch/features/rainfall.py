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


# ---------------------------------------------------------------- streaming (agent) form; parity-tested vs rain_features
HIST = 40


def rain_state_init(w: pd.DataFrame, upto: pd.Timestamp, api_k: float = 0.9) -> dict:
    """Warm state from history strictly before `upto`: last HIST days + API recursion over all history."""
    h = w[w.index < upto]
    p = h["precipitation_sum"]
    api = float(antecedent_index(p, api_k).iloc[-1]) if len(p) else 0.0
    t = h.tail(HIST)
    return {"p": t["precipitation_sum"].tolist(), "snow": t["snowfall_sum"].tolist(), "api": api, "k": api_k}


def _nan(x) -> float:
    return float("nan") if x is None else float(x)


def rain_step(state: dict, r: dict) -> tuple[dict, dict]:
    """Pure step: state + today's reading (precip, rain, snow, hours, tmax) → (state', features). NaN semantics match batch."""
    p_today = _nan(r.get("precipitation_sum"))
    p = (state["p"] + [p_today])[-HIST:]
    snow = (state["snow"] + [_nan(r.get("snowfall_sum"))])[-HIST:]
    api = state["k"] * state["api"] + (0.0 if np.isnan(p_today) else p_today)
    arr = np.array(p, float)

    def wsum(a: np.ndarray) -> float:
        return float(a.sum()) if len(a) and not np.isnan(a).any() else float("nan")
    P3 = wsum(arr[-3:]) if len(arr) >= 3 else float("nan")
    P15 = wsum(arr[-18:-3]) if len(arr) >= 18 else float("nan")
    P30 = wsum(arr[-30:]) if len(arr) >= 30 else float("nan")
    hours = _nan(r.get("precipitation_hours"))
    hrs0 = 0.0 if np.isnan(hours) else hours
    s7 = np.nansum(np.array(snow[-7:], float))
    rain = _nan(r.get("rain_sum"))
    tmax = _nan(r.get("temperature_2m_max"))
    f = {"P1": p_today, "P3": P3, "P15": P15, "P30": P30, "API": api, "precip_hours": hours,
         "intensity": p_today / max(hrs0, 1.0),
         "seattle_ct_margin_in": (P3 / MM_PER_IN - (3.5 - 0.67 * (P15 / MM_PER_IN))),
         "rain_on_snow": float(bool(rain > 0) and bool(s7 > 0) and bool(tmax > 0))}
    return {"p": p, "snow": snow, "api": api, "k": state["k"]}, f
