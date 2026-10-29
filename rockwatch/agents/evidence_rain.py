"""EvidenceRainAgent: streaming rain features (same definitions as batch, parity-tested) → contribution (log-odds)."""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.features.rainfall import rain_state_init, rain_step


class EvidenceRainAgent(Agent):
    name = "evidence_rain"
    group = "rain"
    topics = ["sim.clock", "sensor.rain", "sensor.thermal"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.zones = list(ctx.zones["zone_id"])
        start = pd.Timestamp(ctx.start)
        self.state = {z: rain_state_init(ctx.weather[z], start) for z in self.zones}
        self.next_day = {z: start for z in self.zones}     # next day each zone expects (strict order)
        self.rain: dict[tuple, dict] = {}
        self.tmax: dict[tuple, float | None] = {}
        self.src: dict[tuple, list[str]] = defaultdict(list)
        self.open_days: list[str] = []
        self.model = ctx.model

    def restore(self, bus):
        """After a restart: warm state up to the current sim day (missed days are not replayed)."""
        last = bus.read(self.agent_id, ["sim.clock"], kind="tick", latest=True)
        if last and pd.Timestamp(last[0].sim_date) > pd.Timestamp(self.ctx.start):
            d = pd.Timestamp(last[0].sim_date)
            self.state = {z: rain_state_init(self.ctx.weather[z], d) for z in self.zones}
            self.next_day = {z: d for z in self.zones}

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
        elif env.topic == "sensor.rain" and env.zone_id in self.state:
            self.rain[(env.zone_id, env.sim_date)] = env.payload
            self.src[(env.zone_id, env.sim_date)].append(env.msg_id)
        elif env.topic == "sensor.thermal" and env.zone_id in self.state:
            self.tmax[(env.zone_id, env.sim_date)] = env.payload.get("temperature_2m_max")
            self.src[(env.zone_id, env.sim_date)].append(env.msg_id)
        return self._emit(force=False, now=None)

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
                have_r, have_t = k in self.rain, k in self.tmax
                if not (have_r and have_t) and not due:
                    continue
                r = dict(self.rain.pop(k, {}) or {})
                r["temperature_2m_max"] = self.tmax.pop(k, None)
                q = "ok" if have_r and have_t else ("degraded" if have_r else "missing")
                if not have_r:
                    r.update(precipitation_sum=None, rain_sum=None, snowfall_sum=None, precipitation_hours=None)
                self.state[z], f = rain_step(self.state[z], r)
                if q == "ok" and any(v != v for v in f.values()):   # NaN window (earlier gap) → degraded, never silent
                    q = "degraded"
                c = 0.0 if q == "missing" else self.model.group_contribution(self.group, f)
                out.append(self.msg(f"evidence.{self.group}", d, {"features": f, "contribution": c, "group": self.group},
                                    zone_id=z, quality=q, evidence_ids=self.src.pop(k, [])))
                self.next_day[z] = ts + pd.Timedelta(days=1)
                done += 1
            if done == len(self.zones):
                self.open_days.remove(d)
        return out
