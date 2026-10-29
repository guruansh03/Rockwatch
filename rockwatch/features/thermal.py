"""Thermal features (§7): freeze–thaw cycles in 7 d; Tmax anomaly vs zone day-of-year climatology
fitted on TRAIN years only."""
from __future__ import annotations

import numpy as np
import pandas as pd

THERMAL_COLS = ["ft_cycles_7d", "tmax_anom"]


def doy_climatology(w: pd.DataFrame, train_start: str, train_end: str, half_window: int = 7) -> pd.Series:
    """Mean Tmax per day-of-year (1..366) over train dates, circular ±half_window smoothing."""
    m = (w["date"] >= train_start) & (w["date"] <= train_end)
    t = w.loc[m]
    doy = t["date"].dt.dayofyear.clip(upper=365)
    raw = t.groupby(doy)["temperature_2m_max"].mean().reindex(range(1, 366))
    arr = raw.to_numpy()
    ext = np.concatenate([arr[-half_window:], arr, arr[:half_window]])
    sm = pd.Series(ext).rolling(2 * half_window + 1, center=True, min_periods=1).mean().to_numpy()[half_window:-half_window]
    clim = pd.Series(sm, index=range(1, 366))
    clim.loc[366] = clim.loc[365]
    return clim


def thermal_features(w: pd.DataFrame, clim: pd.Series) -> pd.DataFrame:
    f = pd.DataFrame({"date": w["date"].values}, index=w.index)
    ft = ((w["temperature_2m_min"] < 0) & (w["temperature_2m_max"] > 0)).astype(float)
    ft[w["temperature_2m_min"].isna() | w["temperature_2m_max"].isna()] = np.nan
    f["ft_cycles_7d"] = ft.rolling(7, min_periods=7).sum()
    f["tmax_anom"] = w["temperature_2m_max"].to_numpy() - clim.reindex(w["date"].dt.dayofyear).to_numpy()
    return f


# ---------------------------------------------------------------- streaming (agent) form; parity-tested vs thermal_features
def thermal_state_init(w: pd.DataFrame, upto: pd.Timestamp, clim: pd.Series) -> dict:
    h = w[w.index < upto].tail(7)
    ft = []
    for tmin, tmax in zip(h["temperature_2m_min"], h["temperature_2m_max"]):
        ft.append(float("nan") if (pd.isna(tmin) or pd.isna(tmax)) else float(tmin < 0 < tmax))
    return {"ft": ft[-6:], "clim": {int(k): float(v) for k, v in clim.items()}}


def thermal_step(state: dict, r: dict, date: pd.Timestamp) -> tuple[dict, dict]:
    tmax = r.get("temperature_2m_max")
    tmin = r.get("temperature_2m_min")
    tmax = float("nan") if tmax is None else float(tmax)
    tmin = float("nan") if tmin is None else float(tmin)
    flag = float("nan") if (np.isnan(tmin) or np.isnan(tmax)) else float(tmin < 0 and tmax > 0)
    ft = (state["ft"] + [flag])[-7:]
    a = np.array(ft, float)
    ft7 = float(a.sum()) if len(a) == 7 and not np.isnan(a).any() else float("nan")
    anom = tmax - state["clim"][int(date.dayofyear)]
    return {"ft": ft[-6:], "clim": state["clim"]}, {"ft_cycles_7d": ft7, "tmax_anom": anom}
