"""EvidenceSeismicAgent: 100 km / 3-day quake features per zone → contribution."""
from __future__ import annotations

import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.config import repo_path
from rockwatch.features.seismic import seismic_step


class EvidenceSeismicAgent(Agent):
    name = "evidence_seismic"
    group = "seismic"
    topics = ["sim.clock", "sensor.seismic"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.z = ctx.zones[["zone_id", "lat", "lon"]].to_dict("records")
        self._init(pd.Timestamp(ctx.start))
        self.read: dict[str, tuple] = {}
        self.open_days: list[str] = []
        self.model = ctx.model

    def _init(self, d: pd.Timestamp):
        """Warm the 2-day window from the quake archive (history the sensor already delivered)."""
        q = pd.read_parquet(repo_path(self.ctx.cfg["paths"]["processed"]) / self.ctx.region / "quakes.parquet")
        self.state = {}
        for zz in self.z:
            st: list = []
            for k in (2, 1):
                dd = d - pd.Timedelta(days=k)
                g = q[q["date_local"] == dd]
                qs = [{"lat": r.lat, "lon": r.lon, "mag": None if pd.isna(r.mag) else r.mag} for r in g.itertuples()]
                st, _ = seismic_step(st, qs, zz["lat"], zz["lon"])
            self.state[zz["zone_id"]] = st
        self.next_day = d

    def restore(self, bus):
        last = bus.read(self.agent_id, ["sim.clock"], kind="tick", latest=True)
        if last and pd.Timestamp(last[0].sim_date) > pd.Timestamp(self.ctx.start):
            self._init(pd.Timestamp(last[0].sim_date))

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
        elif env.topic == "sensor.seismic":
            self.read[env.sim_date] = (env.payload.get("quakes", []), env.msg_id)
        return self._emit(False, None)

    def tick(self, now, force=False):
        return self._emit(force, now)

    def _emit(self, force, now):
        out = []
        for d in list(self.open_days):
            ts = pd.Timestamp(d)
            if ts != self.next_day:
                if ts < self.next_day:
                    self.open_days.remove(d)
                continue
            due = force or (now is not None and now - self.tick_wall.get(d, now) >= self.ctx.watermark("evidence_missing"))
            if d not in self.read and not due:
                continue
            have = d in self.read
            qs, mid = self.read.pop(d, ([], None))
            for zz in self.z:
                self.state[zz["zone_id"]], f = seismic_step(self.state[zz["zone_id"]], qs,
                                                            zz["lat"], zz["lon"])
                q = "ok" if have else "missing"
                c = 0.0 if q == "missing" else self.model.group_contribution(self.group, f)
                out.append(self.msg("evidence.seismic", d, {"features": f, "contribution": c, "group": self.group},
                                    zone_id=zz["zone_id"], quality=q, evidence_ids=[mid] if mid else []))
            self.next_day = ts + pd.Timedelta(days=1)
            self.open_days.remove(d)
        return out
