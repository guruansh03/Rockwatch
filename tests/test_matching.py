"""Hand-built matching cases (§10): TP_before, TP_at, FP, FN, short-range, multi-event days, hysteresis."""
import numpy as np
import pandas as pd

from rockwatch.eval.matching import hysteresis, make_frame, match
from rockwatch.eval.metrics import metrics


def panel(zone_days: dict[str, int], start="2020-01-01"):
    rows = []
    for z, n in zone_days.items():
        for i, d in enumerate(pd.date_range(start, periods=n)):
            rows.append((z, d, 0))
    return pd.DataFrame(rows, columns=["zone_id", "date", "y"])


def run(p, raw, short=None, period=("2020-01-01", "2020-12-31"), details=True):
    fr = make_frame(p, period, short)
    return match(fr, np.asarray(raw), 2, with_details=details)


def test_hysteresis_rolling_max():
    zs = np.array([True, False, False, False, False, True, False])
    raw = np.array([3, 1, 1, 2, 0, 0, 2])
    assert hysteresis(raw, zs).tolist() == [3, 3, 1, 2, 2, 0, 2]


def test_tp_before_at_fn():
    p = panel({"a": 10})
    p.loc[[3, 6, 9], "y"] = 1          # events days 3, 6, 9
    raw = np.zeros(10, int)
    raw[1] = 2                          # active days 1–2 → covers day 3 from d−1 → TP_before
    raw[6] = 2                          # same-day only → TP_at, not before
    r = run(p, raw)                     # day 9: nothing → FN
    assert (r["n_event_days"], r["tp_before"], r["tp_at"]) == (3, 1, 2)
    m = metrics(r)
    assert m["recall_before"] == 1 / 3 and m["recall_at"] == 2 / 3


def test_episodes_tp_fp_and_day_precision():
    p = panel({"a": 20})
    p.loc[5, "y"] = 1
    raw = np.zeros(20, int)
    raw[4] = 2          # episode days 4–5: contains d_e−1 → TP
    raw[12] = 3         # episode days 12–13: no event → FP
    r = run(p, raw)
    assert (r["n_episodes"], r["episodes_tp"], r["episodes_fp"]) == (2, 1, 1)
    # alert days 4,5,12,13; hits: day4 (event next day), day5 (event day)
    assert (r["alert_days"], r["alert_days_hit"]) == (4, 2)
    m = metrics(r)
    assert m["precision_episode"] == 0.5 and m["precision_day"] == 0.5
    assert r["lead_days"] == [1]       # episode starts day 4, event day 5


def test_episode_touching_only_after_event_is_fp():
    p = panel({"a": 10})
    p.loc[3, "y"] = 1
    raw = np.zeros(10, int)
    raw[4] = 2                          # starts day after event → FP, event FN
    r = run(p, raw)
    assert (r["tp_at"], r["episodes_fp"]) == (0, 1)


def test_multi_event_day_and_multi_zone():
    p = panel({"a": 5, "b": 5})
    p.loc[2, "y"] = 1                   # zone a day 2 (2 events same day are one event-day in y)
    p.loc[7, "y"] = 1                   # zone b day 2
    raw = np.zeros(10, int)
    raw[1] = 2                          # zone a only
    r = run(p, raw)
    assert (r["n_event_days"], r["tp_before"]) == (2, 1)
    # alert in zone a must not leak into zone b (zone boundary)
    raw2 = np.zeros(10, int); raw2[4] = 2   # last day of zone a
    r2 = run(p, raw2)
    assert r2["tp_at"] == 0 and r2["alert_days"] == 1


def test_short_range_matching():
    p = panel({"a": 15})
    short = pd.DataFrame({"zone_id": ["a", "a"], "date_min": pd.to_datetime(["2020-01-06", "2020-01-12"]),
                          "date_max": pd.to_datetime(["2020-01-08", "2020-01-13"])})
    raw = np.zeros(15, int)
    raw[4] = 2                          # day 4 = Date_Min−1 of first → matched
    r = run(p, raw, short)
    assert (r["n_short_range"], r["short_range_matched"]) == (2, 1)
    assert r["episodes_tp"] == 1        # episode overlapping window counts TP
    m = metrics(r)
    assert m["recall_at"] == 0.5 and m["recall_before"] is None   # no exact event-days


def test_period_restriction():
    p = panel({"a": 40})
    p.loc[[5, 35], "y"] = 1
    raw = np.zeros(40, int); raw[4] = 2; raw[34] = 2
    r = run(p, raw, period=("2020-01-01", "2020-01-20"))
    assert (r["n_event_days"], r["tp_before"], r["n_episodes"]) == (1, 1, 1)


def test_bootstrap_runs_and_brackets_point():
    from rockwatch.eval.bootstrap import bootstrap_ci, day_blocks
    rng = np.random.default_rng(1)
    p = panel({"a": 300, "b": 300})
    p.loc[rng.choice(600, 30, replace=False), "y"] = 1
    raw = (rng.random(600) < 0.1).astype(int) * 2
    fr = make_frame(p, ("2020-01-01", "2020-12-31"))
    det = match(fr, raw, 2, with_details=True)
    m = metrics(det)
    ci = bootstrap_ci(fr, det, n=200, seed=0)
    lo, hi = ci["recall_at"]
    assert lo <= m["recall_at"] <= hi
    blk, nb, _ = day_blocks(fr)
    assert nb >= 2 and blk.min() == 0


def test_cli_refuses_test_without_final():
    from rockwatch.cli import main
    assert main(["eval", "--split", "test", "--regions", "A"]) == 4
