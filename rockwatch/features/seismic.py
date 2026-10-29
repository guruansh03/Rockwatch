"""Seismic features (§7): within R km over the 3-day window d-2..d (local dates)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from rockwatch.data.quakes import haversine_km

SEISMIC_COLS = ["eq_max_mag_3d", "eq_count_3d", "eq_min_dist_km_3d"]
NO_EQ_DIST = 200.0  # fill when no event within R


def seismic_features(zones: pd.DataFrame, dates: pd.DatetimeIndex, quakes: pd.DataFrame,
                     radius_km: float = 100.0, window_days: int = 3) -> pd.DataFrame:
    """Return (zone_id, date) rows for all zones × dates."""
    out = []
    for z in zones.itertuples():
        d = haversine_km(z.lat, z.lon, quakes["lat"].to_numpy(), quakes["lon"].to_numpy())
        q = quakes.loc[d <= radius_km, ["date_local", "mag"]].assign(dist=d[d <= radius_km])
        daily = q.groupby("date_local").agg(mx=("mag", "max"), n=("mag", "size"), dmin=("dist", "min"))
        daily = daily.reindex(dates)
        mx = daily["mx"].rolling(window_days, min_periods=1).max()
        n = daily["n"].fillna(0).rolling(window_days, min_periods=1).sum()
        dm = daily["dmin"].rolling(window_days, min_periods=1).min()
        out.append(pd.DataFrame({"zone_id": z.zone_id, "date": dates, "eq_max_mag_3d": mx.fillna(0.0).to_numpy(),
                                 "eq_count_3d": n.to_numpy(), "eq_min_dist_km_3d": dm.fillna(NO_EQ_DIST).to_numpy()}))
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------- streaming (agent) form
def seismic_step(state: list, quakes: list[dict], zlat: float, zlon: float, radius_km: float = 100.0,
                 window_days: int = 3) -> tuple[list, dict]:
    """state: last window_days-1 daily tuples (max_mag|nan, count, min_dist|nan). Returns (state', features)."""
    if quakes:
        lat = np.array([q["lat"] for q in quakes]); lon = np.array([q["lon"] for q in quakes]); mag = np.array([q["mag"] for q in quakes], float)
        d = haversine_km(zlat, zlon, lat, lon)
        m = d <= radius_km
        today = (float(np.nanmax(mag[m])) if m.any() and not np.isnan(mag[m]).all() else float("nan"), float(m.sum()),
                 float(d[m].min()) if m.any() else float("nan"))
    else:
        today = (float("nan"), 0.0, float("nan"))
    win = (state + [today])[-window_days:]
    mx = np.array([t[0] for t in win]); n = sum(t[1] for t in win); dm = np.array([t[2] for t in win])
    f = {"eq_max_mag_3d": 0.0 if np.isnan(mx).all() else float(np.nanmax(mx)), "eq_count_3d": float(n),
         "eq_min_dist_km_3d": NO_EQ_DIST if np.isnan(dm).all() else float(np.nanmin(dm))}
    return win[-(window_days - 1):], f
