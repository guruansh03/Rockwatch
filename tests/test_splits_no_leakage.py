"""Leakage guards (§6.5): split order/gaps; zone selection + susceptibility ignore val/test events;
features causal (data after d never changes features at d); climatology train-only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rockwatch.config import load_config
from rockwatch.data.splits import assign_split, split_ranges, validate
from rockwatch.data.zones import build_grid, select_zones, train_or_undated_mask
from rockwatch.features.rainfall import rain_features
from rockwatch.features.susceptibility import susceptibility
from rockwatch.features.thermal import doy_climatology, thermal_features

CFG = load_config()


@pytest.mark.parametrize("region", list(CFG["regions"]))
def test_frozen_splits_valid(region):
    rc = CFG["regions"][region]
    validate(rc, 30)
    r = split_ranges(rc)
    assert r["train"][1] < r["val"][0] and r["val"][1] < r["test"][0]


def test_assign_split_no_overlap():
    rc = CFG["regions"]["A"]
    d = pd.Series(pd.date_range("2005-01-01", "2023-01-01"))
    s = assign_split(d, rc)
    r = split_ranges(rc)
    for k in ("train", "val", "test"):
        assert d[s == k].min() >= r[k][0] and d[s == k].max() <= r[k][1]
    assert (s == "gap").sum() >= 60


def synth_cells(train_end="2015-02-10"):
    # SYNTHETIC test-only inventory: cell r0c0 has only a TEST-period event; r1c1 a train event; r2c2 undated.
    te = pd.Timestamp(train_end)
    return pd.DataFrame({
        "zone_id": ["r0c0", "r1c1", "r2c2", "r3c3"], "row": [0, 1, 2, 3], "col": [0, 1, 2, 3],
        "date_min": [te + pd.Timedelta(days=500), te - pd.Timedelta(days=5), pd.NaT, te - pd.Timedelta(days=10)],
        "date_max": [pd.NaT, pd.NaT, pd.NaT, te + pd.Timedelta(days=5)],  # r3c3 range crosses train end -> excluded
    })


def test_zone_selection_ignores_val_test_events():
    cells = synth_cells()
    m = train_or_undated_mask(cells, "2015-02-10")
    assert list(m) == [False, True, True, False]
    grid = build_grid([0, 1, 0, 1], 0.25)
    z = select_zones(cells, grid, "2015-02-10", {"zero_feature_ratio": 0, "seed": 0, "zero_feature_neighbor_only": True})
    assert set(z["zone_id"]) == {"r1c1", "r2c2"}


def test_susceptibility_ignores_val_test_events():
    cells = synth_cells()
    grid = build_grid([0, 1, 0, 1], 0.25)
    s = susceptibility(cells, grid, "2015-02-10").set_index("zone_id")
    assert s.loc["r0c0", "n_prior"] == 0 and s.loc["r1c1", "n_prior"] == 1


def synth_weather(n=400, seed=0):
    rng = np.random.default_rng(seed)
    d = pd.date_range("2014-01-01", periods=n)
    return pd.DataFrame({"date": d, "precipitation_sum": rng.gamma(0.5, 4, n), "rain_sum": rng.gamma(0.5, 3, n),
                         "snowfall_sum": rng.gamma(0.2, 2, n), "precipitation_hours": rng.integers(0, 24, n).astype(float),
                         "temperature_2m_max": rng.normal(5, 8, n), "temperature_2m_min": rng.normal(-3, 8, n)})


def test_features_causal():
    w = synth_weather()
    cut = 300
    w2 = w.copy()
    w2.loc[cut:, ["precipitation_sum", "rain_sum", "snowfall_sum", "temperature_2m_max", "temperature_2m_min"]] *= 7.0
    clim = doy_climatology(w, "2014-01-01", "2014-06-30")
    for fn in (rain_features, lambda x: thermal_features(x, clim)):
        a, b = fn(w), fn(w2)
        pd.testing.assert_frame_equal(a.iloc[:cut], b.iloc[:cut])


def test_climatology_train_only():
    w = synth_weather()
    w2 = w.copy()
    w2.loc[w2["date"] > "2014-06-30", "temperature_2m_max"] += 50
    c1 = doy_climatology(w, "2014-01-01", "2014-06-30")
    c2 = doy_climatology(w2, "2014-01-01", "2014-06-30")
    pd.testing.assert_series_equal(c1, c2)


def test_rain_windows():
    w = synth_weather(60)
    f = rain_features(w)
    p = w["precipitation_sum"]
    d = 40
    assert np.isclose(f.loc[d, "P3"], p[d - 2:d + 1].sum())
    assert np.isclose(f.loc[d, "P15"], p[d - 17:d - 2].sum())
    assert np.isclose(f.loc[d, "P30"], p[d - 29:d + 1].sum())
