"""SeismicSensorAgent: publishes ComCat M≥3 events (region buffer) bucketed by local day."""
from __future__ import annotations

import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.config import repo_path


class SeismicSensorAgent(Agent):
    name = "sensor_seismic"
    topics = ["sim.clock"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        q = pd.read_parquet(repo_path(ctx.cfg["paths"]["processed"]) / ctx.region / "quakes.parquet")
        self.by_day = {d.strftime("%Y-%m-%d"): g for d, g in q.groupby("date_local")}

    def handle(self, env):
        if env.topic != "sim.clock" or env.kind != "tick":
            return []
        g = self.by_day.get(env.sim_date)
        qs = [] if g is None else [{"id": r.event_id, "lat": float(r.lat), "lon": float(r.lon), "mag": None if pd.isna(r.mag) else float(r.mag),
                                    "depth_km": float(r.depth_km)} for r in g.itertuples()]
        return [self.msg("sensor.seismic", env.sim_date, {"quakes": qs}, kind="reading")]
