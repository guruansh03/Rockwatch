"""EvidenceSusceptibilityAgent: static prior (train + undated inventory features only) → constant contribution."""
from __future__ import annotations

import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.config import repo_path
from rockwatch.data.zones import assign_cells, build_grid
from rockwatch.features.susceptibility import susceptibility


class EvidenceSusceptibilityAgent(Agent):
    name = "evidence_susceptibility"
    group = "susceptibility"
    topics = ["sim.clock"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        rc = ctx.rc
        if "single_zone" in rc:
            prior = {ctx.zones["zone_id"].iloc[0]: 0.0}
        else:
            inv = pd.read_parquet(repo_path(ctx.cfg["paths"]["interim"]) / "inventory_clean.parquet",
                                  columns=["lat", "lon", "date_min", "date_max"])
            deg = ctx.cfg["zones"]["deg"]
            s = susceptibility(assign_cells(inv, rc["bbox"], deg), build_grid(rc["bbox"], deg), rc["splits"]["train"][1])
            prior = dict(zip(s["zone_id"], s["susc"]))
        self.contrib = {z: ctx.model.group_contribution(self.group, {"susc": prior[z]}) for z in ctx.zones["zone_id"]}
        self.prior = prior

    def handle(self, env):
        if env.topic != "sim.clock" or env.kind != "tick":
            return []
        return [self.msg("evidence.susceptibility", env.sim_date, {"features": {"susc": float(self.prior[z])}, "contribution": c,
                                                                   "group": self.group}, zone_id=z) for z, c in self.contrib.items()]
