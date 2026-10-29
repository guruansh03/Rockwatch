"""Static susceptibility prior (§7): log1p(train-period + undated feature count), neighbour-smoothed.
Uses only features allowed by zones.train_or_undated_mask (never val/test events)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from rockwatch.data.zones import train_or_undated_mask


def susceptibility(inv_cells: pd.DataFrame, grid: pd.DataFrame, train_end: str, self_weight: float = 0.5) -> pd.DataFrame:
    """Return zone_id, n_prior, susc = w·log1p(n) + (1-w)·mean_8nbrs(log1p(n)) over the full grid."""
    ok = inv_cells[train_or_undated_mask(inv_cells, train_end)]
    cnt = ok.groupby("zone_id").size()
    g = grid[["zone_id", "row", "col"]].copy()
    g["n_prior"] = g["zone_id"].map(cnt).fillna(0).astype(int)
    g["l"] = np.log1p(g["n_prior"])
    lut = {(r, c): v for r, c, v in zip(g["row"], g["col"], g["l"])}
    nb = []
    for r, c in zip(g["row"], g["col"]):
        vals = [lut[(r + dr, c + dc)] for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr or dc) and (r + dr, c + dc) in lut]
        nb.append(np.mean(vals) if vals else 0.0)
    g["susc"] = self_weight * g["l"] + (1 - self_weight) * np.array(nb)
    return g[["zone_id", "n_prior", "susc"]]
