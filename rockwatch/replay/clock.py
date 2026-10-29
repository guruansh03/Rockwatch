"""Simulation clock: sim days at `speed` wall-seconds per day."""
from __future__ import annotations

import pandas as pd


def sim_days(start: str, end: str) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, freq="D")]
