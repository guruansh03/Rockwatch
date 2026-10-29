"""Replay engine: drives the sim clock and publishes ground truth for each day AFTER it closes.
Truth goes only to truth.events (readable by evaluator/dashboard only)."""
from __future__ import annotations

import time
from typing import Any

import pandas as pd

from rockwatch.agents.base import AgentContext
from rockwatch.bus.base import Bus
from rockwatch.config import repo_path
from rockwatch.replay.clock import sim_days
from rockwatch.schemas import TRUTH_TOPIC, Envelope


def load_truth(ctx: AgentContext) -> dict[str, list[dict[str, Any]]]:
    """Exact-dated events in the replayed zones, keyed by local date."""
    ev = pd.read_parquet(repo_path(ctx.cfg["paths"]["processed"]) / ctx.region / "events.parquet")
    ev = ev[(ev["date_kind"] == "exact") & ev["zone_id"].isin(set(ctx.zones["zone_id"]))]
    out: dict[str, list[dict[str, Any]]] = {}
    for r in ev.itertuples():
        out.setdefault(pd.Timestamp(r.date_min).strftime("%Y-%m-%d"), []).append(
            {"event_id": r.event_id, "zone_id": r.zone_id, "type_family": r.type_family, "inventory": r.inventory})
    return out


class Engine:
    agent_id = "replay_engine"

    def __init__(self, ctx: AgentContext, bus: Bus):
        self.ctx, self.bus = ctx, bus
        self.days = sim_days(ctx.start, ctx.end)
        self.truth = load_truth(ctx)

    def tick_msg(self, d: str) -> Envelope:
        return Envelope(topic="sim.clock", agent_id=self.agent_id, sim_date=d, kind="tick", payload={"speed": self.ctx.speed})

    def truth_msg(self, d: str) -> Envelope:
        return Envelope(topic=TRUTH_TOPIC, agent_id=self.agent_id, sim_date=d, kind="day_close", payload={"events": self.truth.get(d, [])})

    def run(self, on_day=None) -> None:
        """Real-time replay for multi-process runs (2-day warm-up pause so every agent is polling)."""
        time.sleep(2 * self.ctx.speed)
        for i, d in enumerate(self.days):
            t0 = time.time()
            self.bus.publish(self.tick_msg(d))
            if on_day:
                on_day(i, d)
            time.sleep(max(0.0, self.ctx.speed - (time.time() - t0)))
            self.bus.publish(self.truth_msg(d))
        self.bus.publish(Envelope(topic="sim.clock", agent_id=self.agent_id, sim_date=self.days[-1], kind="end"))


def run_local(ctx: AgentContext, bus: Bus, agents: list, days: list[str] | None = None, engine: Engine | None = None) -> None:
    """Deterministic in-process run (tests, parity): tick → quiesce → force watermarks → quiesce → truth."""
    eng = engine or Engine(ctx, bus)

    def pump(force: bool) -> bool:
        any_out = False
        for _ in range(100):
            moved = False
            for a in agents:
                outs = []
                for env in bus.poll(a.agent_id, a.topics):
                    a.on_clock(env)
                    outs += a.handle(env)
                if force:
                    outs += a.tick(time.time(), force=True)
                if outs:
                    bus.publish(outs)
                    moved = any_out = True
            if not moved:
                break
        return any_out

    for d in days or eng.days:
        bus.publish(eng.tick_msg(d))
        pump(False)
        while pump(True):
            pass
        bus.publish(eng.truth_msg(d))
        pump(False)
