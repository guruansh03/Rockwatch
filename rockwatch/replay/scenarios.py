"""Scenario lookup (config `scenarios`). Test-period scenarios are added only at CP2."""
from __future__ import annotations

from typing import Any

import pandas as pd


def resolve(cfg: dict[str, Any], name: str, days: int | None = None) -> tuple[str, str, str]:
    """→ (region, start, end)."""
    s = cfg["scenarios"][name]
    n = days or s["days"]
    end = (pd.Timestamp(s["start"]) + pd.Timedelta(days=n - 1)).strftime("%Y-%m-%d")
    rc = cfg["regions"][s["region"]]
    if pd.Timestamp(end) > pd.Timestamp(rc["splits"]["test"][1]) or pd.Timestamp(s["start"]) < pd.Timestamp(rc["splits"]["train"][0]):
        raise ValueError("scenario outside region data range")
    t0 = pd.Timestamp(rc["splits"]["test"][0])
    if pd.Timestamp(end) >= t0:
        # the sealed test period is evaluated once (eval --split test --final) BEFORE any replay of it
        from rockwatch.config import repo_path
        done = [p for p in repo_path(cfg["paths"]["reports"]).glob(f"eval_*_{s['region']}_test") if (p / "metrics.json").exists()]
        if not done:
            raise ValueError(f"scenario {name} replays the sealed TEST period of region {s['region']}; "
                             "run the final evaluation first (FINAL_TEST_EVAL.bat / eval --split test --final)")
    return s["region"], s["start"], end
