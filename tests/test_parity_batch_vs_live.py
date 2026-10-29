"""§9.1 parity: the live agent pipeline (same code, in-process deterministic runner) reproduces batch
features → p → provisional level → hysteresis over a 30-day validation window."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rockwatch.config import load_config, repo_path

CFG = load_config()
REGION, START, END = "A", "2017-08-20", "2017-09-18"   # validation period (no test data touched)
NEEDED = [repo_path("data/processed/A/features.parquet"), repo_path("data/processed/A/models/full.json")]


@pytest.fixture(scope="module")
def live_and_batch():
    if not all(p.exists() for p in NEEDED):
        pytest.skip("processed data/models not built")
    from rockwatch.agents.base import AgentContext
    from rockwatch.agents.run import build
    from rockwatch.bus.memory import MemoryBus
    from rockwatch.eval.runner import n_dynamic_positive
    from rockwatch.fusion.thresholds import raw_levels
    from rockwatch.replay.engine import run_local

    ctx = AgentContext(CFG, REGION, START, END, 0.1)
    bus = MemoryBus()
    run_local(ctx, bus, build(ctx, bus))
    live = pd.DataFrame([{"zone_id": e.zone_id, "date": pd.Timestamp(e.sim_date), "p_live": e.payload["p"],
                          "lvl_live": e.payload["level"], **{f"c_{k}": v for k, v in e.payload["contributions"].items()}}
                         for e in bus.log if e.topic == "risk.fused"])
    states = {e.sim_date: e.payload["levels"] for e in bus.log if e.topic == "alerts.active" and e.kind == "daily_state"}
    P = pd.read_parquet(NEEDED[0])
    m = ctx.model
    P = P[P["zone_id"].isin(ctx.zones["zone_id"])].sort_values(["zone_id", "date"]).reset_index(drop=True)
    pred = m.predict(P)
    P["p_batch"] = pred["p"].to_numpy()
    for g in m.groups:
        P[f"b_{g}"] = pred[f"c_{g}"].to_numpy()
    th = {k: v for k, v in m.thresholds.items() if k != "sweep"}
    P["lvl_batch"] = raw_levels(P["p_batch"].to_numpy(), n_dynamic_positive(pred, CFG), th, CFG["thresholds"]["corroboration_min_dynamic"])
    P["active_batch"] = np.maximum(P["lvl_batch"], P.groupby("zone_id")["lvl_batch"].shift(1).fillna(0).astype(int))
    W = P[(P["date"] >= START) & (P["date"] <= END)]
    j = W.merge(live, on=["zone_id", "date"], how="outer", indicator=True)
    return j, states, list(m.groups)


def test_every_zone_day_fused(live_and_batch):
    j, _, _ = live_and_batch
    assert (j["_merge"] == "both").all()
    assert len(j) == 30 * j["zone_id"].nunique()


def test_contributions_and_p_match(live_and_batch):
    j, _, groups = live_and_batch
    for g in groups:
        np.testing.assert_allclose(j[f"c_{g}"], j[f"b_{g}"], rtol=0, atol=1e-9, err_msg=g)
    np.testing.assert_allclose(j["p_live"], j["p_batch"], rtol=0, atol=1e-9)


def test_levels_match(live_and_batch):
    j, states, _ = live_and_batch
    assert (j["lvl_live"] == j["lvl_batch"]).all()
    j = j[j["date"] > pd.Timestamp(START)]           # live hysteresis starts cold on day 1
    for r in j.itertuples():
        assert states[r.date.strftime("%Y-%m-%d")][r.zone_id] == r.active_batch
