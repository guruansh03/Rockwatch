"""USGS Landslide Inventories across the United States v3.0 (DOI 10.5066/P14AJF8I, CC0).

fetch: ScienceBase JSON -> CSV/zip URL -> data/raw/usgs_ls_v3/. On failure raise (never fabricate).
load:  read CSV (plain or inside zip) from raw_dir.
clean: dates, date_kind, non-landslide drop, type_family, Lon_W sign fix.
Ground truth only: never a live input.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

EXPECTED_COLS = [
    "USGS_ID", "Date_Min", "Date_Max", "Fatalities", "Confidence", "LS_Type",
    "Inventory", "Inv_URL", "Info_Source", "Notes", "Lat_N", "Lon_W",
]
DATE_KINDS = ("exact", "short_range", "long_range", "undated")


class InventoryFetchError(RuntimeError):
    """Raised when the inventory cannot be obtained. Caller must stop and ask the user."""


# --------------------------------------------------------------------------- fetch
def _find_file_urls(item: dict[str, Any]) -> list[tuple[str, str]]:
    """Collect (name, url) candidates from a ScienceBase item JSON."""
    out: list[tuple[str, str]] = []
    for f in item.get("files", []) or []:
        if f.get("url"):
            out.append((f.get("name", ""), f["url"]))
    for d in item.get("distributionLinks", []) or []:
        if d.get("uri"):
            out.append((d.get("name", d.get("title", "")), d["uri"]))
    for w in item.get("webLinks", []) or []:
        if w.get("uri"):
            out.append((w.get("title", ""), w["uri"]))
    return out


def pick_csv_url(cands: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Prefer names containing 'csv' (e.g. US_Landslide_v3_csv.zip); else any .csv/.zip."""
    def score(nu: tuple[str, str]) -> int:
        n = (nu[0] + " " + nu[1]).lower()
        s = 0
        if "csv" in n:
            s += 4
        if "landslide" in n:
            s += 2
        if n.endswith(".zip") or ".zip" in n:
            s += 1
        if any(x in n for x in ("gdb", "shp", "xml", "gpkg")):
            s -= 5
        return s
    ranked = sorted(cands, key=score, reverse=True)
    return ranked[0] if ranked and score(ranked[0]) > 0 else None


def fetch_inventory(item_url: str, raw_dir: Path, timeout: int = 60) -> Path:
    """Download the CSV (or zip) via the ScienceBase item JSON. Caches; no re-download."""
    import requests  # local import: keep module importable offline

    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = find_raw_file(raw_dir)
    if existing:
        log.info("inventory cached: %s", existing)
        return existing
    try:
        r = requests.get(item_url, timeout=timeout)
        r.raise_for_status()
        item = r.json()
    except Exception as e:  # noqa: BLE001
        raise InventoryFetchError(f"ScienceBase JSON fetch failed: {e!r}") from e
    (raw_dir / "sciencebase_item.json").write_text(json.dumps(item, indent=1), encoding="utf-8")
    choice = pick_csv_url(_find_file_urls(item))
    if not choice:
        raise InventoryFetchError("No CSV/zip link found in ScienceBase item JSON.")
    name, url = choice
    fname = name if name and "." in name else url.rstrip("/").split("/")[-1].split("?")[0]
    dest = raw_dir / fname
    try:
        with requests.get(url, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise InventoryFetchError(f"Download failed for {url}: {e!r}") from e
    return dest


# --------------------------------------------------------------------------- load
def find_raw_file(raw_dir: Path) -> Path | None:
    """First CSV, else first zip, in raw_dir (recursive)."""
    if not raw_dir.exists():
        return None
    csvs = sorted(p for p in raw_dir.rglob("*.csv"))
    if csvs:
        return max(csvs, key=lambda p: p.stat().st_size)
    zips = sorted(raw_dir.rglob("*.zip"))
    return zips[0] if zips else None


def _read_csv_bytes(b: bytes) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(b), dtype=str, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError("cannot decode CSV")


def load_raw(path: Path) -> pd.DataFrame:
    """Read inventory CSV (direct or the largest CSV inside a zip). All columns as str."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not names:
                raise ValueError(f"no CSV inside {path}")
            name = max(names, key=lambda n: z.getinfo(n).file_size)
            df = _read_csv_bytes(z.read(name))
    else:
        df = _read_csv_bytes(path.read_bytes())
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"inventory missing expected columns {missing}; got {list(df.columns)}")
    return df


# --------------------------------------------------------------------------- clean
@dataclass
class CleanReport:
    """Bookkeeping from clean_inventory, copied into the profile."""
    n_raw: int = 0
    n_bad_coords: int = 0
    n_excluded_type: int = 0
    excluded_type_counts: dict[str, int] = field(default_factory=dict)
    lon_sign_flipped: bool = False
    n_lon_positive_after: int = 0
    n_unparsed_date_min: int = 0
    n_date_max_before_min: int = 0
    n_kept: int = 0


def _parse_date(s: pd.Series) -> pd.Series:
    """Parse to naive normalized datetime (date only). Unparseable -> NaT."""
    s = s.astype("string").str.strip().replace({"": pd.NA})
    d = pd.to_datetime(s, errors="coerce", format="mixed")
    try:
        if getattr(d.dt, "tz", None) is not None:
            d = d.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return d.dt.normalize()


def date_kind(dmin: pd.Series, dmax: pd.Series, short_max_days: int) -> pd.Series:
    """exact: Date_Min set & (Date_Max empty or == Date_Min); short_range: span<=N d; long_range; undated."""
    span = (dmax - dmin).dt.days
    kind = np.select(
        [dmin.isna(), dmax.isna() | (span == 0), (span > 0) & (span <= short_max_days)],
        ["undated", "exact", "short_range"],
        default="long_range",
    )
    return pd.Series(kind, index=dmin.index, dtype="string")


def map_type_family(ls_type: pd.Series, family_map: list, other: str, empty: str) -> pd.Series:
    """Lowercase substring match; first family in config order wins."""
    low = ls_type.astype("string").str.lower().str.strip().fillna("")
    out = pd.Series(other, index=ls_type.index, dtype="string")
    out[low == ""] = empty
    assigned = low == ""
    for fam, subs in family_map:
        hit = ~assigned & low.apply(lambda t, subs=subs: any(x in t for x in subs))
        out[hit] = fam
        assigned |= hit
    return out


def exclusion_mask(ls_type: pd.Series, subs: list[str]) -> pd.Series:
    """True where LS_Type indicates a non-landslide feature."""
    low = ls_type.astype("string").str.lower().fillna("")
    return low.apply(lambda t: any(x in t for x in subs)).astype(bool)


def clean_inventory(df: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, CleanReport]:
    """Apply §6.1 cleaning. Does NOT apply the confidence filter (profiling reports all C)."""
    inv = cfg["inventory"]
    rep = CleanReport(n_raw=len(df))
    out = df.copy()

    out["lat"] = pd.to_numeric(out["Lat_N"], errors="coerce")
    lon = pd.to_numeric(out["Lon_W"], errors="coerce")
    if (lon > 0).mean() > 0.5:  # stored as degrees west positive
        lon = -lon
        rep.lon_sign_flipped = True
    out["lon"] = lon
    rep.n_lon_positive_after = int((out["lon"] > 0).sum())
    bad = out["lat"].isna() | out["lon"].isna() | ~out["lat"].between(-90, 90) | ~out["lon"].between(-180, 180)
    rep.n_bad_coords = int(bad.sum())
    out = out[~bad]

    out["confidence"] = pd.to_numeric(out["Confidence"], errors="coerce").astype("Int64")
    out["fatalities"] = pd.to_numeric(out["Fatalities"], errors="coerce")

    dmin_raw = out["Date_Min"].astype("string").str.strip().replace({"": pd.NA})
    out["date_min"] = _parse_date(out["Date_Min"])
    out["date_max"] = _parse_date(out["Date_Max"])
    rep.n_unparsed_date_min = int((dmin_raw.notna() & out["date_min"].isna()).sum())
    rev = out["date_max"].notna() & out["date_min"].notna() & (out["date_max"] < out["date_min"])
    rep.n_date_max_before_min = int(rev.sum())
    out.loc[rev, ["date_min", "date_max"]] = out.loc[rev, ["date_max", "date_min"]].values
    out["date_kind"] = date_kind(out["date_min"], out["date_max"], inv["short_range_max_days"])
    out["date_tz"] = np.where(out["Inventory"].isin(inv["utc_inventories"]), "UTC", "local")

    excl = exclusion_mask(out["LS_Type"], inv["exclude_type_substrings"])
    rep.n_excluded_type = int(excl.sum())
    rep.excluded_type_counts = (
        out.loc[excl, "LS_Type"].astype("string").str.strip().value_counts().head(30).to_dict()
    )
    out = out[~excl].copy()
    out["type_family"] = map_type_family(
        out["LS_Type"], inv["type_family_map"], inv["other_family"], inv["empty_family"]
    )
    rep.n_kept = len(out)
    return out.reset_index(drop=True), rep


def apply_confidence(df: pd.DataFrame, c_min: int) -> pd.DataFrame:
    """Keep rows with Confidence >= c_min (missing confidence dropped)."""
    return df[df["confidence"].fillna(-1) >= c_min]
