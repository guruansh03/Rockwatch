"""AlertAgent: hysteresis (escalate now, de-escalate after 2 lower days), dedupe, L2+ ack, re-notify.
State is rebuilt from the bus log after a restart."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from rockwatch.agents.base import Agent


def alert_step(prev_raw: int, raw: int) -> int:
    """Pure hysteresis (D-020): active[d] = max(raw[d], raw[d−1])."""
    return max(raw, prev_raw)


class AlertAgent(Agent):
    name = "alert"
    topics = ["sim.clock", "risk.verified", "alerts.ack"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.zones = list(ctx.zones["zone_id"])
        self.prev_raw = {z: 0 for z in self.zones}
        self.active = {z: 0 for z in self.zones}
        self.episode: dict[str, dict[str, Any] | None] = {z: None for z in self.zones}
        self.ver: dict[str, dict[str, Any]] = defaultdict(dict)
        self.open_days: list[str] = []
        self.renotify = ctx.cfg["agents"]["ack_renotify_days"]

    def restore(self, bus):
        last = bus.read(self.agent_id, ["alerts.active"], kind="daily_state", latest=True)
        if last:
            s = last[0].payload
            self.prev_raw.update({z: int(v) for z, v in s["raw"].items()})
            self.active.update({z: int(v) for z, v in s["levels"].items()})
            self.episode.update(s.get("episodes", {}))

    def handle(self, env):
        if env.topic == "sim.clock" and env.kind == "tick":
            self.open_days.append(env.sim_date)
        elif env.topic == "risk.verified":
            self.ver[env.sim_date][env.zone_id] = env
        elif env.topic == "alerts.ack":
            ep = self.episode.get(env.zone_id)
            if ep and ep["id"] == env.payload.get("episode_id"):
                ep["acked"] = True
                ep["acked_by"] = env.payload.get("by", "operator")
        return self._emit(False, None)

    def tick(self, now, force=False):
        return self._emit(force, now)

    def _emit(self, force, now):
        out = []
        for d in list(self.open_days):
            got = self.ver.get(d, {})
            due = force or (now is not None and now - self.tick_wall.get(d, now) >= self.ctx.watermark("alert"))
            if len(got) < len(self.zones) and not due:
                continue
            ts = pd.Timestamp(d)
            raw_today = {}
            for z in self.zones:
                e = got.get(z)
                raw = int(e.payload["verifier"]["level_out"]) if e else 0
                raw_today[z] = raw
                new = alert_step(self.prev_raw[z], raw)
                old = self.active[z]
                self.prev_raw[z], self.active[z] = raw, new
                ep = self.episode[z]
                if new >= 2 and (ep is None):
                    ep = self.episode[z] = {"id": f"{z}:{d}", "start": d, "acked": False, "last_notified": d, "max_level": new}
                if ep is not None:
                    ep["max_level"] = max(ep["max_level"], new)
                if new != old:
                    pl = {"from": old, "to": new, "episode_id": ep["id"] if ep else None,
                          "p": e.payload["p"] if e else None, "contributions": e.payload["contributions"] if e else {},
                          "quality": e.payload["quality"] if e else {}, "verifier": e.payload["verifier"] if e else None,
                          "needs_ack": new >= 2}
                    out.append(self.msg("alerts.active", d, pl, zone_id=z, kind="escalate" if new > old else "deescalate",
                                        evidence_ids=[e.msg_id] if e else []))
                elif ep is not None and new >= 2 and not ep["acked"] and (ts - pd.Timestamp(ep["last_notified"])).days >= self.renotify:
                    ep["last_notified"] = d
                    out.append(self.msg("alerts.active", d, {"episode_id": ep["id"], "level": new, "unacked_since": ep["start"]},
                                        zone_id=z, kind="renotify"))
                if new < 2 and ep is not None:
                    self.episode[z] = None
            state = {"levels": dict(self.active), "raw": raw_today,
                     "p": {z: (got[z].payload["p"] if z in got else None) for z in self.zones},
                     "unacked": [z for z, ep in self.episode.items() if ep and not ep["acked"]],
                     "episodes": {z: ep for z, ep in self.episode.items() if ep}, "missing_verified": [z for z in self.zones if z not in got]}
            out.append(self.msg("alerts.active", d, state, kind="daily_state"))
            self.open_days.remove(d)
            self.ver.pop(d, None)
        return out
