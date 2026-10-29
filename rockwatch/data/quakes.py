"""USGS ComCat earthquakes (FDSN event service): region bbox + buffer, M>=min, chunked by year, cached."""
from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

log = logging.getLogger(__name__)
COLS = ["event_id", "time_utc", "lat", "lon", "depth_km", "mag", "mag_type", "place_type"]


def buffered_bbox(lat0: float, lat1: float, lon0: float, lon1: float, km: float) -> tuple[float, float, float, float]:
    """Expand bbox by km (lon buffer uses the higher-latitude cosine, i.e. widest)."""
    dlat = km / 111.0
    dlon = km / (111.0 * math.cos(math.radians(max(abs(lat0), abs(lat1)))))
    return lat0 - dlat, lat1 + dlat, lon0 - dlon, lon1 + dlon


def region_bbox(rc: dict[str, Any]) -> tuple[float, float, float, float]:
    """bbox for grid or single-zone regions (single zone -> point)."""
    if "single_zone" in rc:
        s = rc["single_zone"]
        return s["lat"], s["lat"], s["lon"], s["lon"]
    return tuple(rc["bbox"])  # type: ignore[return-value]


def fetch_year(base_url: str, bb: tuple[float, float, float, float], year_start: str, year_end: str,
               minmag: float, timeout: int = 60) -> pd.DataFrame:
    """One FDSN query (geojson). Raises on HTTP error or if result hits the server cap."""
    import requests

    params = dict(format="geojson", starttime=year_start, endtime=year_end, minlatitude=bb[0], maxlatitude=bb[1],
                  minlongitude=bb[2], maxlongitude=bb[3], minmagnitude=minmag, orderby="time-asc", limit=20000)
    r = requests.get(base_url, params=params, timeout=timeout)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if len(feats) >= 20000:
        raise RuntimeError(f"ComCat cap hit for {year_start}; split the query")
    rows = []
    for f in feats:
        p, g = f["properties"], f["geometry"]["coordinates"]
        rows.append(dict(event_id=f["id"], time_utc=pd.to_datetime(p["time"], unit="ms", utc=True), lon=g[0], lat=g[1],
                         depth_km=g[2], mag=p.get("mag"), mag_type=p.get("magType"), place_type=p.get("type")))
    return pd.DataFrame(rows, columns=COLS)


def fetch_region(cfg: dict[str, Any], region: str, start: str, end: str, cache_root: Path) -> pd.DataFrame:
    """All years [start, end]; per-year cache under data/cache/quakes/<region>/."""
    q = cfg["quakes"]
    rc = cfg["regions"][region]
    bb = buffered_bbox(*region_bbox(rc), q["buffer_km"])
    cdir = cache_root / "quakes" / region
    cdir.mkdir(parents=True, exist_ok=True)
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    parts = []
    for y in range(s.year, e.year + 1):
        p = cdir / f"{y}.parquet"
        if not p.exists():
            a = max(s, pd.Timestamp(f"{y}-01-01")).strftime("%Y-%m-%d")
            b = (min(e, pd.Timestamp(f"{y}-12-31")) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")  # endtime exclusive-ish
            df = fetch_year(q["base_url"], bb, a, b, q["min_magnitude"])
            df.to_parquet(p, index=False)
            (cdir / f"{y}.json").write_text(json.dumps(dict(bbox=bb, start=a, end=b, n=len(df))), encoding="utf-8")
            time.sleep(1.0)
        parts.append(pd.read_parquet(p))
    out = pd.concat(parts, ignore_index=True).drop_duplicates("event_id")
    out = out[out["place_type"].fillna("earthquake") == "earthquake"]
    tz = ZoneInfo(rc["tz"])
    out["date_local"] = pd.to_datetime(out["time_utc"], utc=True).dt.tz_convert(tz).dt.tz_localize(None).dt.normalize()
    return out[(out["date_local"] >= s) & (out["date_local"] <= e)].reset_index(drop=True)


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorised great-circle distance (km)."""
    import numpy as np

    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))
