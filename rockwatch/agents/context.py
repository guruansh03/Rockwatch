"""ContextAgent: season + regional extent (fraction of zones with P3 above their validation-median P3)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.features.rainfall import rain_features


def context_features(d: pd.Timestamp, p3: dict[str, float], med: dict[str, float]) -> dict[str, float]:
    """Pure. Matches features.context (season, regional_extent)."""
    m = d.month
    vals = [float(round(p3[z], 6) > round(med[z], 6)) for z in p3 if p3[z] is not None and not np.isnan(p3[z]) and z in med]
    return {"month_sin": float(np.sin(2 * np.pi * (m - 1) / 12)), "month_cos": float(np.cos(2 * np.pi * (m - 1) / 12)),
            "regional_extent": float(np.mean(vals)) if vals else float("nan")}


class ContextAgent(Agent):
    name = "context"
    group = "context"
    topics = ["sim.clock", "evidence.rain"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        va = ctx.rc["splits"]["val"]
        self.med = {}
        for z in ctx.zones["zone_id"]:
            f = rain_features(ctx.weather[z].rename_axis("date").reset_index())
            m = (f["date"] >= va[0]) & (f["date"] <= va[1])
            self.med[z] = float(f.loc[m, "P3"].median())
        self.n = len(self.med)
        self.p3: dict[str, dict[str, float]] = {}
        self.src: dict[str, list[str]] = {}
        self.open_days: list[str] = []
        self.model = ctx.model

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
            self.p3.setdefault(env.sim_date, {})
        elif env.topic == "evidence.rain":
            p3 = env.payload["features"].get("P3") if env.quality == "ok" else None   # missing/degraded zones excluded
            self.p3.setdefault(env.sim_date, {})[env.zone_id] = float("nan") if p3 is None else p3
            self.src.setdefault(env.sim_date, []).append(env.msg_id)
        return self._emit(False, None)

    def tick(self, now, force=False):
        return self._emit(force, now)

    def _emit(self, force, now):
        out = []
        for d in list(self.open_days):
            got = self.p3.get(d, {})
            due = force or (now is not None and now - self.tick_wall.get(d, now) >= self.ctx.watermark("context"))
            if len(got) < self.n and not due:
                continue
            f = context_features(pd.Timestamp(d), got, self.med)
            valid = sum(1 for v in got.values() if v == v)
            q = "ok" if valid == self.n else ("degraded" if valid else "missing")
            c = self.model.group_contribution(self.group, f)
            out.append(self.msg("evidence.context", d, {"features": f, "contribution": c, "group": self.group, "n_zones": len(got)},
                                quality=q, evidence_ids=self.src.pop(d, [])[:20]))
            self.open_days.remove(d)
            self.p3.pop(d, None)
        return out
