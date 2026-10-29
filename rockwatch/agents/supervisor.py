"""SupervisorAgent (non-LLM): heartbeat staleness → quality.flags (agent_stale / agent_recovered), optional restart
via the sqlite registry, degraded banner state."""
from __future__ import annotations

import logging
import subprocess
import time

from rockwatch.agents.base import Agent

log = logging.getLogger(__name__)


def stale_set(last_seen: dict[str, float], now: float, after_s: float, stopped: set[str]) -> set[str]:
    """Pure: agents whose last heartbeat is older than after_s (excluding cleanly stopped ones)."""
    return {a for a, t in last_seen.items() if now - t > after_s and a not in stopped}


class SupervisorAgent(Agent):
    name = "supervisor"
    topics = ["agents.heartbeat"]

    def __init__(self, ctx, agent_id=None, bus=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.bus = bus
        self.last_seen: dict[str, float] = {}
        self.stale: set[str] = set()
        self.stopped: set[str] = set()
        self.after = ctx.cfg["agents"]["stale_after_s"]
        self.restart_after = ctx.cfg["agents"]["restart_after_s"]
        self.last_check = 0.0

    def handle(self, env):
        if env.agent_id == self.agent_id:
            return []
        self.last_seen[env.agent_id] = time.time()
        if env.payload.get("stopping"):
            self.stopped.add(env.agent_id)
        return []

    def tick(self, now, force=False):
        if now - self.last_check < 1.0 and not force:
            return []
        self.last_check = now
        cur = stale_set(self.last_seen, now, self.after, self.stopped)
        out = []
        for a in sorted(cur - self.stale):
            out.append(self.msg("quality.flags", self.current_day, {"agent_id": a, "last_seen_s_ago": round(now - self.last_seen[a], 1),
                                                                   "banner": f"{a} stale — dependent evidence degraded"}, kind="agent_stale",
                                quality="degraded"))
        for a in sorted(self.stale - cur):
            out.append(self.msg("quality.flags", self.current_day, {"agent_id": a}, kind="agent_recovered"))
        self.stale = cur
        out += self._restart(now)
        return out

    def _restart(self, now):
        if self.bus is None or not hasattr(self.bus, "registry"):
            return []
        out = []
        for r in self.bus.registry():
            a = r["agent_id"]
            if a in self.stale and r["auto_restart"] and now - self.last_seen.get(a, now) > self.restart_after:
                p = subprocess.Popen(r["cmd"])
                self.bus.bump_restart(a, p.pid)
                self.last_seen[a] = now
                out.append(self.msg("quality.flags", self.current_day, {"agent_id": a, "new_pid": p.pid}, kind="agent_restarted"))
        return out
