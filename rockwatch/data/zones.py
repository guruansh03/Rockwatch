"""Zones (§6.3): 0.25° grid over the region bbox; keep feature cells + a sample of zero-feature cells.

Feature cells use ONLY undated or train-period-dated inventory features (never val/test events).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def build_grid(bbox: list[float], deg: float) -> pd.DataFrame:
    """All cells of a half-open bbox. zone_id = r{row}c{col}, row from south, col from west."""
    lat0, lat1, lon0, lon1 = bbox
    nr, nc = int(round((lat1 - lat0) / deg)), int(round((lon1 - lon0) / deg))
    rows, cols = np.meshgrid(np.arange(nr), np.arange(nc), indexing="ij")
    g = pd.DataFrame({"row": rows.ravel(), "col": cols.ravel()})
    g["zone_id"] = "r" + g["row"].astype(str) + "c" + g["col"].astype(str)
    g["lat"] = lat0 + (g["row"] + 0.5) * deg
    g["lon"] = lon0 + (g["col"] + 0.5) * deg
    return g


def assign_cells(df: pd.DataFrame, bbox: list[float], deg: float) -> pd.DataFrame:
    """Add row/col/zone_id to inventory rows inside bbox (rows outside dropped)."""
    lat0, lat1, lon0, lon1 = bbox
    m = (df["lat"] >= lat0) & (df["lat"] < lat1) & (df["lon"] >= lon0) & (df["lon"] < lon1)
    out = df[m].copy()
    out["row"] = np.floor((out["lat"] - lat0) / deg).astype(int)
    out["col"] = np.floor((out["lon"] - lon0) / deg).astype(int)
    out["zone_id"] = "r" + out["row"].astype(str) + "c" + out["col"].astype(str)
    return out


def train_or_undated_mask(inv: pd.DataFrame, train_end: str) -> pd.Series:
    """Features allowed for zone selection / susceptibility prior: undated, or fully dated ≤ train_end."""
    te = pd.Timestamp(train_end)
    undated = inv["date_min"].isna()
    dated_train = inv["date_min"].notna() & (inv["date_min"] <= te) & (inv["date_max"].isna() | (inv["date_max"] <= te))
    return undated | dated_train


def select_zones(inv_cells: pd.DataFrame, grid: pd.DataFrame, train_end: str, cfg_z: dict[str, Any]) -> pd.DataFrame:
    """Return selected zones with columns zone_id,row,col,lat,lon,n_prior_features,kind(feature|zero)."""
    ok = inv_cells[train_or_undated_mask(inv_cells, train_end)]
    cnt = ok.groupby("zone_id").size().rename("n_prior_features")
    g = grid.merge(cnt, left_on="zone_id", right_index=True, how="left").fillna({"n_prior_features": 0})
    g["n_prior_features"] = g["n_prior_features"].astype(int)
    feat = g[g["n_prior_features"] > 0].copy()
    feat["kind"] = "feature"
    zero = g[g["n_prior_features"] == 0]
    if cfg_z.get("zero_feature_neighbor_only", True) and len(feat):
        fr = set(zip(feat["row"], feat["col"]))
        nb = zero.apply(lambda r: any((r["row"] + dr, r["col"] + dc) in fr for dr in (-1, 0, 1) for dc in (-1, 0, 1)), axis=1)
        zero = zero[nb]
    n_zero = min(len(zero), int(round(cfg_z["zero_feature_ratio"] * len(feat))))
    zs = zero.sample(n=n_zero, random_state=cfg_z["seed"]).copy() if n_zero else zero.iloc[:0].copy()
    zs["kind"] = "zero"
    out = pd.concat([feat, zs]).sort_values(["kind", "n_prior_features"], ascending=[True, False])
    return out.reset_index(drop=True)


def weather_range(region_cfg: dict[str, Any], antecedent_days: int) -> tuple[str, str]:
    """[train_start - antecedent, test_end] inclusive."""
    s = pd.Timestamp(region_cfg["splits"]["train"][0]) - pd.Timedelta(days=antecedent_days)
    return s.strftime("%Y-%m-%d"), region_cfg["splits"]["test"][1]


def build_region_zones(cfg: dict[str, Any], region: str, inv: pd.DataFrame | None) -> pd.DataFrame:
    """Zones table for a region (grid regions use inventory; single-zone regions are fixed)."""
    rc = cfg["regions"][region]
    if "single_zone" in rc:
        sz = rc["single_zone"]
        return pd.DataFrame([{"zone_id": sz["zone_id"], "row": 0, "col": 0, "lat": sz["lat"], "lon": sz["lon"],
                              "n_prior_features": -1, "kind": "single"}])
    deg = cfg["zones"]["deg"]
    cells = assign_cells(inv, rc["bbox"], deg)
    return select_zones(cells, build_grid(rc["bbox"], deg), rc["splits"]["train"][1], cfg["zones"])
