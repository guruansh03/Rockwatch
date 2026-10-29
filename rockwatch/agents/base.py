"""Agent contract (§9.1): own state, own loop, bus-only communication, heartbeat every 2 wall-seconds.
Decision logic lives in pure step functions; Agent subclasses only route messages to them."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import numpy as np
import pandas as pd

from rockwatch.bus.base import Bus
from rockwatch.config import repo_path
from rockwatch.schemas import Envelope

log = logging.getLogger(__name__)
HEARTBEAT_S = 2.0


@dataclass
class AgentContext:
    """Static run context shared by all agents (read-only)."""
    cfg: dict[str, Any]
    region: str
    start: str               # first sim day
    end: str                 # last sim day
    speed: float = 1.5       # wall seconds per sim day
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def rc(self) -> dict[str, Any]:
        return self.cfg["regions"][self.region]

    @cached_property
    def zones(self) -> pd.DataFrame:
        """Zones the deployed model was built on (build_summary) that also have cached weather."""
        import json

        from rockwatch.data.weather import ZoneRequest, load_zone
        from rockwatch.data.zones import weather_range

        proc = repo_path(self.cfg["paths"]["processed"]) / self.region
        z = pd.read_parquet(proc / "zones.parquet")
        bs = proc / "build_summary.json"
        if bs.exists():
            miss = set(json.loads(bs.read_text(encoding="utf-8"))["zones_missing_weather"])
            z = z[~z["zone_id"].isin(miss)]
        a, b = weather_range(self.rc, self.cfg["zones"]["antecedent_days"])
        cache = repo_path(self.cfg["paths"]["cache"])
        ok = [r.zone_id for r in z.itertuples()
              if load_zone(cache, ZoneRequest(self.region, r.zone_id, float(r.lat), float(r.lon), a, b), self.cfg["weather"]["chunk_years"]) is not None]
        return z[z["zone_id"].isin(ok)].reset_index(drop=True)

    @cached_property
    def weather(self) -> dict[str, pd.DataFrame]:
        """zone_id → daily weather indexed by date (contiguous). The 'historical gauge database'."""
        from rockwatch.data.weather import ZoneRequest, load_zone
        from rockwatch.data.zones import weather_range

        a, b = weather_range(self.rc, self.cfg["zones"]["antecedent_days"])
        cache = repo_path(self.cfg["paths"]["cache"])
        out = {}
        for r in self.zones.itertuples():
            w = load_zone(cache, ZoneRequest(self.region, r.zone_id, float(r.lat), float(r.lon), a, b), self.cfg["weather"]["chunk_years"])
            out[r.zone_id] = w.set_index("date").reindex(pd.date_range(a, b, freq="D"))
        return out

    @cached_property
    def model(self):
        from rockwatch.fusion.model import FusionModel
        p = repo_path(self.cfg["paths"]["processed"]) / self.region / "models" / "full.json"
        return FusionModel.from_json(p.read_text(encoding="utf-8"))

    def watermark(self, name: str) -> float:
        """Wall-second watermark after a day tick (fraction of speed)."""
        return self.cfg["agents"]["watermarks"][name] * self.speed


def day(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def iso(d: pd.Timestamp) -> str:
    return d.strftime("%Y-%m-%d")


class Agent:
    """Base agent. Subclasses set `topics` and implement handle()/tick()."""
    name = "agent"
    topics: list[str] = []

    def __init__(self, ctx: AgentContext, agent_id: str | None = None, **kw: Any) -> None:
        self.ctx = ctx
        self.agent_id = agent_id or self.name
        self.processed = 0
        self.tick_wall: dict[str, float] = {}   # sim_date -> wall time of its sim.clock tick
        self.current_day: str | None = None

    # ---- to override
    def handle(self, env: Envelope) -> list[Envelope]:
        return []

    def tick(self, now: float, force: bool = False) -> list[Envelope]:
        """Timer hook (watermarks). force=True: deterministic local runner says 'everything for the day is in'."""
        return []

    def restore(self, bus: Bus) -> None:
        """Rebuild state after restart (default: nothing)."""

    def on_control(self, env: Envelope) -> None:
        """Fault-injection / operator controls (agents.control kinds other than stop)."""

    # ---- helpers
    def on_clock(self, env: Envelope) -> None:
        if env.topic == "sim.clock" and env.kind == "tick":
            self.tick_wall[env.sim_date] = time.time()
            self.current_day = env.sim_date

    def msg(self, topic: str, sim_date: str | None, payload: dict[str, Any], zone_id: str | None = None,
            kind: str = "data", quality: str = "ok", confidence: float = 1.0, evidence_ids: list[str] | None = None) -> Envelope:
        return Envelope(topic=topic, agent_id=self.agent_id, zone_id=zone_id, sim_date=sim_date, kind=kind,
                        payload=payload, quality=quality, confidence=confidence, evidence_ids=evidence_ids or [])

    def heartbeat(self) -> Envelope:
        return self.msg("agents.heartbeat", self.current_day, {"pid": os.getpid(), "processed": self.processed}, kind="heartbeat")


def run_loop(agent: Agent, bus: Bus, poll_s: float = 0.05, max_wall_s: float | None = None) -> None:
    """Process loop for one OS process. Stops on agents.control stop (all or this agent)."""
    agent.restore(bus)
    topics = sorted(set(agent.topics) | {"agents.control"})
    last_hb = 0.0
    t0 = time.time()
    while True:
        now = time.time()
        if now - last_hb >= HEARTBEAT_S:
            bus.publish(agent.heartbeat())
            last_hb = now
        out: list[Envelope] = []
        for env in bus.poll(agent.agent_id, topics):
            if env.topic == "agents.control" and env.kind == "stop" and env.payload.get("target") in (None, agent.agent_id):
                bus.publish(agent.msg("agents.heartbeat", agent.current_day, {"pid": os.getpid(), "stopping": True}, kind="heartbeat"))
                return
            if env.topic == "agents.control":
                agent.on_control(env)
                continue
            agent.on_clock(env)
            try:
                out += agent.handle(env)
            except Exception:  # noqa: BLE001
                log.exception("%s failed on %s", agent.agent_id, env.topic)
            agent.processed += 1
        out += agent.tick(time.time())
        if out:
            bus.publish(out)
        if max_wall_s and time.time() - t0 > max_wall_s:
            return
        if not out:
            time.sleep(poll_s)
