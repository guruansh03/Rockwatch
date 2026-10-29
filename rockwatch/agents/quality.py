"""QualityAgent: per day, flags gaps, stuck values and outliers vs neighbour zones → quality.flags (daily summary)."""
from __future__ import annotations

import time
from collections import defaultdict

import numpy as np

from rockwatch.agents.base import Agent


def day_flags(rain: dict, thermal: dict, zones: list[str], nbrs: dict[str, list[str]], stuck_hist: dict, stuck_days: int,
              outlier_mm: float) -> tuple[dict, dict]:
    """Pure. rain/thermal: zone → payload for one day. Returns (flags {zone:{rain,thermal}} non-ok only, stuck_hist')."""
    flags: dict[str, dict[str, str]] = {}
    for z in zones:
        r, t = rain.get(z), thermal.get(z)
        fr = "missing" if r is None or r.get("precipitation_sum") is None else "ok"
        ft = "missing" if t is None or t.get("temperature_2m_max") is None or t.get("temperature_2m_min") is None else "ok"
        if fr == "ok":
            nb = [rain[n]["precipitation_sum"] for n in nbrs.get(z, []) if n in rain and rain[n].get("precipitation_sum") is not None]
            if nb and r["precipitation_sum"] > max(outlier_mm, 6 * float(np.median(nb))):
                fr = "degraded"
        h = stuck_hist.get(z, [])
        if ft == "ok":
            h = (h + [(t["temperature_2m_max"], t["temperature_2m_min"])])[-stuck_days:]
            if len(h) == stuck_days and len(set(h)) == 1:
                ft = "degraded"
        stuck_hist[z] = h
        if fr != "ok" or ft != "ok":
            flags[z] = {"rain": fr, "thermal": ft}
    return flags, stuck_hist


class QualityAgent(Agent):
    name = "quality"
    topics = ["sim.clock", "sensor.rain", "sensor.thermal"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        z = ctx.zones
        self.zones = list(z["zone_id"])
        rc = {r.zone_id: (r.row, r.col) for r in z.itertuples()}
        self.nbrs = {a: [b for b in rc if b != a and abs(rc[a][0] - rc[b][0]) <= 1 and abs(rc[a][1] - rc[b][1]) <= 1] for a in rc}
        self.rain: dict[str, dict] = defaultdict(dict)
        self.thermal: dict[str, dict] = defaultdict(dict)
        self.open_days: list[str] = []
        self.stuck: dict = {}

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
        elif env.topic == "sensor.rain":
            self.rain[env.sim_date][env.zone_id] = env.payload
        elif env.topic == "sensor.thermal":
            self.thermal[env.sim_date][env.zone_id] = env.payload
        return []

    def tick(self, now, force=False):
        out = []
        for d in list(self.open_days):
            complete = len(self.rain[d]) >= len(self.zones) and len(self.thermal[d]) >= len(self.zones)
            due = now - self.tick_wall.get(d, now) >= self.ctx.watermark("quality")
            if not (force or complete or due):
                continue
            flags, self.stuck = day_flags(self.rain.pop(d, {}), self.thermal.pop(d, {}), self.zones, self.nbrs, self.stuck,
                                          self.ctx.cfg["agents"]["stuck_days"], self.ctx.cfg["agents"]["outlier_mm"])
            self.open_days.remove(d)
            out.append(self.msg("quality.flags", d, {"flags": flags}, kind="daily"))
        return out
