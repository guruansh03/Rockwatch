"""EvidenceThermalAgent: freeze–thaw cycles + Tmax anomaly (train-only climatology) → contribution."""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.features.thermal import doy_climatology, thermal_state_init, thermal_step


class EvidenceThermalAgent(Agent):
    name = "evidence_thermal"
    group = "thermal"
    topics = ["sim.clock", "sensor.thermal"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.zones = list(ctx.zones["zone_id"])
        tr = ctx.rc["splits"]["train"]
        self.clim = {z: doy_climatology(ctx.weather[z].rename_axis("date").reset_index(), tr[0], tr[1]) for z in self.zones}
        self._init(pd.Timestamp(ctx.start))
        self.read: dict[tuple, dict] = {}
        self.src: dict[tuple, list[str]] = defaultdict(list)
        self.open_days: list[str] = []
        self.model = ctx.model

    def _init(self, d):
        self.state = {z: thermal_state_init(self.ctx.weather[z], d, self.clim[z]) for z in self.zones}
        self.next_day = {z: d for z in self.zones}

    def restore(self, bus):
        last = bus.read(self.agent_id, ["sim.clock"], kind="tick", latest=True)
        if last and pd.Timestamp(last[0].sim_date) > pd.Timestamp(self.ctx.start):
            self._init(pd.Timestamp(last[0].sim_date))

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
        elif env.topic == "sensor.thermal" and env.zone_id in self.state:
            self.read[(env.zone_id, env.sim_date)] = env.payload
            self.src[(env.zone_id, env.sim_date)].append(env.msg_id)
        return self._emit(False, None)

    def tick(self, now, force=False):
        return self._emit(force, now)

    def _emit(self, force, now):
        out = []
        for d in list(self.open_days):
            ts = pd.Timestamp(d)
            due = force or (now is not None and now - self.tick_wall.get(d, now) >= self.ctx.watermark("evidence_missing"))
            done = 0
            for z in self.zones:
                if self.next_day[z] != ts:
                    done += self.next_day[z] > ts
                    continue
                k = (z, d)
                if k not in self.read and not due:
                    continue
                have = k in self.read
                r = self.read.pop(k, {"temperature_2m_max": None, "temperature_2m_min": None})
                self.state[z], f = thermal_step(self.state[z], r, ts)
                q = "ok" if have else "missing"
                if q == "ok" and any(v != v for v in f.values()):   # NaN window (earlier gap) → degraded, never silent
                    q = "degraded"
                c = 0.0 if q == "missing" else self.model.group_contribution(self.group, f)
                out.append(self.msg("evidence.thermal", d, {"features": f, "contribution": c, "group": self.group},
                                    zone_id=z, quality=q, evidence_ids=self.src.pop(k, [])))
                self.next_day[z] = ts + pd.Timedelta(days=1)
                done += 1
            if done == len(self.zones):
                self.open_days.remove(d)
        return out
