"""FusionAgent: logit = b0 + Σ w_q·contribution, Platt → p, provisional level, corroboration count."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from rockwatch.agents.base import Agent
from rockwatch.fusion.thresholds import raw_levels
from rockwatch.schemas import worst

ZONE_GROUPS = ["rain", "thermal", "seismic", "susceptibility"]
SENSOR_OF = {"rain": ("sensor_rain",), "thermal": ("sensor_thermal",), "seismic": ("sensor_seismic",)}


def fuse(model, contrib: dict[str, float], quality: dict[str, str], th: dict[str, Any], qw: dict[str, float],
         dynamic: list[str], min_dyn: int) -> dict[str, Any]:
    """Pure fusion for one zone-day. Missing modality → contribution 0 (train mean), weight 0."""
    groups = list(model.groups)
    logit = model.intercept + sum(qw[quality.get(g, "missing")] * contrib.get(g, 0.0) for g in groups)
    p = float(model.proba(np.array([logit]))[0])
    ndyn = int(sum(1 for g in dynamic if g in groups and quality.get(g, "missing") != "missing" and contrib.get(g, 0.0) > 0))
    lvl = int(raw_levels(np.array([p]), np.array([ndyn]), th, min_dyn)[0])
    return {"logit": float(logit), "p": p, "n_dyn_pos": ndyn, "level": lvl,
            "contributions": {g: float(contrib.get(g, 0.0)) for g in groups}, "quality": {g: quality.get(g, "missing") for g in groups}}


class FusionAgent(Agent):
    name = "fusion"
    topics = ["sim.clock", "evidence.rain", "evidence.thermal", "evidence.seismic", "evidence.susceptibility",
              "evidence.context", "quality.flags"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.model = ctx.model
        self.th = {k: v for k, v in self.model.thresholds.items() if k != "sweep"}
        self.zones = list(ctx.zones["zone_id"])
        self.ev: dict[str, dict[str, dict[str, tuple]]] = defaultdict(lambda: defaultdict(dict))  # day→zone→group→(c,q,id)
        self.ctxev: dict[str, tuple] = {}
        self.qflags: dict[str, dict] = {}
        self.stale: set[str] = set()
        self.open_days: list[str] = []
        a = ctx.cfg["fusion"]
        self.qw, self.dyn = a["quality_weights"], a["dynamic_modalities"]
        self.min_dyn = ctx.cfg["thresholds"]["corroboration_min_dynamic"]

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
        elif env.topic == "evidence.context":
            self.ctxev[env.sim_date] = (env.payload["contribution"], env.quality, env.msg_id)
        elif env.topic.startswith("evidence."):
            self.ev[env.sim_date][env.zone_id][env.payload["group"]] = (env.payload["contribution"], env.quality, env.msg_id)
        elif env.topic == "quality.flags":
            if env.kind == "daily":
                self.qflags[env.sim_date] = env.payload.get("flags", {})
            elif env.kind == "agent_stale":
                self.stale.add(env.payload["agent_id"])
            elif env.kind == "agent_recovered":
                self.stale.discard(env.payload["agent_id"])
        return self._emit(False, None)

    def tick(self, now, force=False):
        return self._emit(force, now)

    def _emit(self, force, now):
        out = []
        groups = list(self.model.groups)
        for d in list(self.open_days):
            evd = self.ev.get(d, {})
            n_need = sum(1 for g in groups if g != "context")
            complete = (all(len(evd.get(z, {})) >= n_need for z in self.zones) and ("context" not in groups or d in self.ctxev)
                        and d in self.qflags)
            due = force or (now is not None and now - self.tick_wall.get(d, now) >= self.ctx.watermark("fusion"))
            if not (complete or due):
                continue
            qf = self.qflags.get(d)
            quality_agent_down = qf is None or "quality" in self.stale
            for z in self.zones:
                contrib, qual, ids = {}, {}, []
                for g in groups:
                    if g == "context":
                        c, q, mid = self.ctxev.get(d, (0.0, "missing", None))
                    else:
                        c, q, mid = evd.get(z, {}).get(g, (0.0, "missing", None))
                    if g in ("rain", "thermal") and qf is not None and z in qf:
                        q = worst(q, qf[z].get(g, "ok"))
                    if quality_agent_down and g in ("rain", "thermal") and q == "ok":
                        q = "degraded"   # §9.3: QualityAgent down → assume degraded
                    contrib[g], qual[g] = c, q
                    if mid:
                        ids.append(mid)
                r = fuse(self.model, contrib, qual, self.th, self.qw, self.dyn, self.min_dyn)
                overall = "ok" if all(v == "ok" for v in qual.values()) else "degraded"
                out.append(self.msg("risk.fused", d, r, zone_id=z, quality=overall, confidence=r["p"], evidence_ids=ids))
            self.open_days.remove(d)
            self.ev.pop(d, None)
            self.ctxev.pop(d, None)
            self.qflags.pop(d, None)
        return out
