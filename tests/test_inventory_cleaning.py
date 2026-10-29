"""Cleaning tests on a tiny SYNTHETIC frame (test-only; not real inventory data)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from rockwatch.config import load_config
from rockwatch.data.usgs_inventory import (
    EXPECTED_COLS, apply_confidence, clean_inventory, find_raw_file, load_raw, pick_csv_url,
)


def synth(rows: list[dict]) -> pd.DataFrame:
    base = {c: "" for c in EXPECTED_COLS}
    return pd.DataFrame([{**base, **r} for r in rows]).astype(str)


@pytest.fixture
def cfg():
    return load_config()


def test_date_kinds_and_lon_flip(cfg):
    df = synth([
        dict(USGS_ID="1", Date_Min="2010-01-05", Date_Max="", Confidence="5", LS_Type="Rockfall", Lat_N="47.6", Lon_W="122.3"),
        dict(USGS_ID="2", Date_Min="2010-01-05", Date_Max="2010-01-07", Confidence="3", LS_Type="debris flow", Lat_N="47.6", Lon_W="122.3"),
        dict(USGS_ID="3", Date_Min="2010-01-05", Date_Max="2010-03-01", Confidence="8", LS_Type="slide", Lat_N="47.6", Lon_W="122.3"),
        dict(USGS_ID="4", Date_Min="", Date_Max="", Confidence="1", LS_Type="", Lat_N="47.6", Lon_W="122.3"),
        dict(USGS_ID="5", Date_Min="2010-01-05", Date_Max="2010-01-05", Confidence="3", LS_Type="Topple", Lat_N="47.6", Lon_W="122.3"),
    ])
    out, rep = clean_inventory(df, cfg)
    assert rep.lon_sign_flipped and (out["lon"] < 0).all()
    k = dict(zip(out["USGS_ID"], out["date_kind"]))
    assert k == {"1": "exact", "2": "short_range", "3": "long_range", "4": "undated", "5": "exact"}
    f = dict(zip(out["USGS_ID"], out["type_family"]))
    assert f == {"1": "fall", "2": "flow", "3": "slide", "4": "unknown", "5": "fall"}


def test_negative_lon_kept(cfg):
    df = synth([dict(USGS_ID="1", Date_Min="2000-01-01", Confidence="3", LS_Type="slide", Lat_N="40", Lon_W="-105")])
    out, rep = clean_inventory(df, cfg)
    assert not rep.lon_sign_flipped and out["lon"].iloc[0] == -105


def test_exclusions_and_other(cfg):
    df = synth([
        dict(USGS_ID="1", LS_Type="Gully", Lat_N="40", Lon_W="105", Confidence="3"),
        dict(USGS_ID="2", LS_Type="Avalanche chute", Lat_N="40", Lon_W="105", Confidence="3"),
        dict(USGS_ID="3", LS_Type="Lateral spread", Lat_N="40", Lon_W="105", Confidence="3"),
        dict(USGS_ID="4", LS_Type="Debris avalanche", Lat_N="40", Lon_W="105", Confidence="3"),
    ])
    out, rep = clean_inventory(df, cfg)
    assert rep.n_excluded_type == 2
    assert dict(zip(out["USGS_ID"], out["type_family"])) == {"3": "other", "4": "flow"}


def test_bad_coords_and_reversed_dates(cfg):
    df = synth([
        dict(USGS_ID="1", Lat_N="abc", Lon_W="105", Confidence="3"),
        dict(USGS_ID="2", Date_Min="2001-02-03", Date_Max="2001-02-01", Lat_N="40", Lon_W="105", Confidence="3"),
    ])
    out, rep = clean_inventory(df, cfg)
    assert rep.n_bad_coords == 1 and rep.n_date_max_before_min == 1
    assert out["date_kind"].iloc[0] == "short_range"


def test_confidence_filter(cfg):
    df = synth([dict(USGS_ID=str(i), Confidence=c, Lat_N="40", Lon_W="105") for i, c in enumerate(["1", "2", "3", "5", "8", ""])])
    out, _ = clean_inventory(df, cfg)
    assert len(apply_confidence(out, 3)) == 3 and len(apply_confidence(out, 5)) == 2


def test_load_zip_and_find(tmp_path: Path):
    df = synth([dict(USGS_ID="1", Lat_N="40", Lon_W="105")])
    zp = tmp_path / "US_Landslide_v3_csv.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("x/US_Landslide_v3.csv", df.to_csv(index=False))
    assert find_raw_file(tmp_path) == zp
    assert list(load_raw(zp)["USGS_ID"]) == ["1"]


def test_load_rejects_missing_cols(tmp_path: Path):
    p = tmp_path / "a.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        load_raw(p)


def test_pick_csv_url():
    c = [("US_Landslide_v3_gdb.zip", "u1"), ("US_Landslide_v3_csv.zip", "u2"), ("metadata.xml", "u3")]
    assert pick_csv_url(c)[1] == "u2"
    assert pick_csv_url([("metadata.xml", "u3")]) is None
