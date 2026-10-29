"""Labels (§6.4). y[zone, d] = 1 if ≥1 exact-dated event (C≥C_min) in zone on day d.
Short-range events kept separately for range-aware matching. Long-range/undated never positive.
Ground truth only — never a model input."""
from __future__ import annotations

from typing import Any

import pandas as pd

from rockwatch.data.profiling import EQ_INVENTORIES
from rockwatch.data.zones import assign_cells

YOSE_FAMILY = {"RF": "fall", "RS": "slide", "DF": "flow", "DS": "slide", "SA": "other"}


def usgs_events(inv: pd.DataFrame, region_cfg: dict[str, Any], deg: float, c_min: int) -> pd.DataFrame:
    """Exact + short-range events in region bbox, C≥c_min, with zone_id. Columns standardised."""
    ev = assign_cells(inv, region_cfg["bbox"], deg)
    ev = ev[ev["date_kind"].isin(["exact", "short_range"]) & (ev["confidence"].fillna(-1) >= c_min)]
    return pd.DataFrame({
        "event_id": ev["USGS_ID"].values, "zone_id": ev["zone_id"].values, "date_min": ev["date_min"].values,
        "date_max": ev["date_max"].fillna(ev["date_min"]).values, "date_kind": ev["date_kind"].values,
        "type_family": ev["type_family"].values, "confidence": ev["confidence"].values,
        "eq_inventory": ev["Inventory"].isin(EQ_INVENTORIES).values, "inventory": ev["Inventory"].values,
    })


def yosemite_events(y: pd.DataFrame, zone_id: str) -> pd.DataFrame:
    """DS746 exact-dated events → same schema (confidence n/a = 5; date-only exact)."""
    ex = y[y["date_kind"] == "exact"]
    typ = ex["Type of slope movement"].astype(str).str.split("/").str[0].str.strip()
    trig = ex["Triggering condition(s)"].astype(str)
    return pd.DataFrame({
        "event_id": "yose_" + ex["ID 2011"].astype(str).values, "zone_id": zone_id, "date_min": ex["date"].values,
        "date_max": ex["date"].values, "date_kind": "exact", "type_family": typ.map(YOSE_FAMILY).fillna("other").values,
        "confidence": 5, "eq_inventory": trig.str.contains(r"\bEQ\b").values, "inventory": "USGS DS746 Yosemite",
    })


def label_panel(keys: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """keys: zone_id, date. Adds y, y_fall, y_no_eq, y_c5, n_events (exact events only)."""
    ex = events[events["date_kind"] == "exact"]
    g = ex.assign(date=ex["date_min"]).groupby(["zone_id", "date"]).agg(
        n_events=("event_id", "size"),
        y_fall=("type_family", lambda s: (s == "fall").any()),
        y_no_eq=("eq_inventory", lambda s: (~s).any()),
        y_c5=("confidence", lambda s: (pd.to_numeric(s) >= 5).any()),
    ).reset_index()
    out = keys.merge(g, on=["zone_id", "date"], how="left")
    out["n_events"] = out["n_events"].fillna(0).astype(int)
    out["y"] = (out["n_events"] > 0).astype(int)
    for c in ("y_fall", "y_no_eq", "y_c5"):
        out[c] = out[c].astype("float").fillna(0).astype(int)
    return out
