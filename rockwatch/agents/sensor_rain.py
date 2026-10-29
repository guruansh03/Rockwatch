"""RainSensorAgent ×zone-group: on each sim-day tick, publish that day's cached Open-Meteo rain readings."""
from __future__ import annotations

import math

from rockwatch.agents.base import Agent

RAIN_FIELDS = ["precipitation_sum", "rain_sum", "snowfall_sum", "precipitation_hours"]


def clean(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def readings(w_by_zone, zones, d, fields):
    """Pure: (zone, payload, quality) for day d."""
    out = []
    for z in zones:
        row = w_by_zone[z].loc[d] if d in w_by_zone[z].index else None
        pl = {f: (clean(row[f]) if row is not None else None) for f in fields}
        q = "missing" if all(v is None for v in pl.values()) else ("degraded" if any(v is None for v in pl.values()) else "ok")
        out.append((z, pl, q))
    return out


class RainSensorAgent(Agent):
    name = "sensor_rain"
    topics = ["sim.clock"]
    topic_out = "sensor.rain"
    fields = RAIN_FIELDS

    def __init__(self, ctx, agent_id=None, group: int = 0, n_groups: int = 1, **kw):
        super().__init__(ctx, agent_id or f"{self.name}_{group}", **kw)
        zs = list(ctx.zones["zone_id"])
        self.my_zones = zs[group::n_groups]

    def handle(self, env):
        if env.topic != "sim.clock" or env.kind != "tick":
            return []
        import pandas as pd
        d = pd.Timestamp(env.sim_date)
        return [self.msg(self.topic_out, env.sim_date, pl, zone_id=z, quality=q, kind="reading")
                for z, pl, q in readings(self.ctx.weather, self.my_zones, d, self.fields)]
