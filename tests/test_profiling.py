"""Profiling tests on SYNTHETIC data (test-only)."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from rockwatch.cli import build_parser
from rockwatch.config import load_config
from rockwatch.data.profiling import positive_zone_days, profile, propose_splits, rank_windows, storm_clusters
from rockwatch.data.usgs_inventory import EXPECTED_COLS, clean_inventory


def synth_inventory(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.Timestamp("1990-01-01") + pd.to_timedelta(rng.integers(0, 365 * 30, n), unit="D")
    lat = 47.0 + rng.random(n) * 1.5
    lon = 122.0 + rng.random(n) * 1.5  # positive -> must be flipped
    rows = {c: [""] * n for c in EXPECTED_COLS}
    rows.update(USGS_ID=[str(i) for i in range(n)], Date_Min=[d.strftime("%Y-%m-%d") for d in days],
                Confidence=["5"] * n, LS_Type=rng.choice(["rockfall", "slide", "debris flow"], n).tolist(),
                Inventory=["Synthetic"] * n, Lat_N=lat.astype(str).tolist(), Lon_W=lon.astype(str).tolist())
    far = pd.DataFrame({c: [""] * 5 for c in EXPECTED_COLS})
    far.update(pd.DataFrame(dict(USGS_ID=[f"f{i}" for i in range(5)], Date_Min=["2000-01-01"] * 5, Confidence=["5"] * 5,
                                 LS_Type=["slide"] * 5, Inventory=["Synthetic"] * 5, Lat_N=["35"] * 5, Lon_W=["90"] * 5)))
    return pd.concat([pd.DataFrame(rows), far], ignore_index=True).astype(str)


def test_rank_windows_finds_cluster():
    cfg = load_config()
    clean, _ = clean_inventory(synth_inventory(), cfg)
    pz = positive_zone_days(clean, 0.25)
    top = rank_windows(pz, 2.0, 0.5, 3)
    a0, a1, o0, o1, cnt = top[0]
    assert a0 <= 47.0 and a1 >= 48.5 and o0 <= -123.5 and o1 >= -122.0
    assert all(t[4] <= cnt for t in top)


def test_splits_chronological_with_gaps():
    dates = pd.date_range("1990-01-01", periods=300, freq="11D")
    pz = pd.DataFrame({"date": dates})
    sp = propose_splits(pz, (0.6, 0.2, 0.2), 30, dt.date(1950, 1, 1))
    tr_end = pd.Timestamp(sp.train[1]); va0 = pd.Timestamp(sp.val[0]); va1 = pd.Timestamp(sp.val[1]); te0 = pd.Timestamp(sp.test[0])
    assert (va0 - tr_end).days == 31 and (te0 - va1).days == 31
    assert tr_end < va0 <= va1 < te0
    assert sum(sp.counts.values()) + sp.lost_in_gaps == 300
    assert sp.counts["train"] == 180


def test_storm_clusters():
    assert storm_clusters(pd.Series(pd.to_datetime(["2000-01-01", "2000-01-03", "2000-01-10"]))) == 2


def test_profile_end_to_end():
    cfg = load_config()
    clean, rep = clean_inventory(synth_inventory(), cfg)
    md, summary = profile(clean, rep, cfg, "synthetic.csv")
    assert "Candidate regions" in md and "Splits" in md
    assert summary["proposal"]["splits"]["counts"]["test"] > 0


def test_cli_parser():
    a = build_parser().parse_args(["eval", "--split", "test", "--final"])
    assert a.final and a.split == "test"
