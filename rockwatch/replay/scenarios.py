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
    return s["region"], s["start"], end
