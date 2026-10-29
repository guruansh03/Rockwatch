"""EvaluatorAgent: the only agent allowed to read truth.events. Live running metrics → eval.live;
offline recompute from the bus log reuses eval.matching."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from rockwatch.agents.base import Agent
from rockwatch.schemas import TRUTH_TOPIC


class EvaluatorAgent(Agent):
    name = "evaluator"
    topics = ["alerts.active", TRUTH_TOPIC]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id, **kw)
        self.levels: dict[str, dict[str, int]] = {}
        self.pending: list = []
        self.c = {"event_days": 0, "tp_before": 0, "tp_at": 0, "alert_zone_days": 0, "zone_days": 0}

    def handle(self, env):
        if env.topic == "alerts.active" and env.kind == "daily_state":
            self.levels[env.sim_date] = env.payload["levels"]
            self.c["alert_zone_days"] += sum(1 for v in env.payload["levels"].values() if v >= 2)
            self.c["zone_days"] += len(env.payload["levels"])
        elif env.topic == TRUTH_TOPIC and env.kind == "day_close":
            self.pending.append(env)
        return self._score()

    def _score(self):
        out, keep = [], []
        for e in self.pending:
            d = e.sim_date
            if d not in self.levels:
                keep.append(e)
                continue
            prev = self.levels.get((pd.Timestamp(d) - pd.Timedelta(days=1)).strftime("%Y-%m-%d"), {})
            for z in sorted({ev["zone_id"] for ev in e.payload["events"] if ev["zone_id"] in self.levels[d]}):
                self.c["event_days"] += 1
                b = prev.get(z, 0) >= 2
                self.c["tp_before"] += b
                self.c["tp_at"] += b or self.levels[d][z] >= 2
            n = self.c["event_days"]
            out.append(self.msg("eval.live", d, {**self.c, "recall_before": self.c["tp_before"] / n if n else None,
                                                 "recall_at": self.c["tp_at"] / n if n else None,
                                                 "alert_day_fraction": self.c["alert_zone_days"] / self.c["zone_days"] if self.c["zone_days"] else None},
                                kind="running"))
        self.pending = keep
        return out


def recompute_from_log(bus, reader: str = "evaluator_offline") -> dict[str, Any]:
    """Offline: rebuild raw levels + truth from the bus log, score with eval.matching (no hysteresis re-derivation)."""
    from rockwatch.eval.matching import make_frame, match
    from rockwatch.eval.metrics import metrics

    st = bus.read(reader, ["alerts.active"], kind="daily_state")
    tr = bus.read(reader, [TRUTH_TOPIC], kind="day_close")
    if not st:
        return {}
    rows = [(z, pd.Timestamp(e.sim_date), int(r)) for e in st for z, r in e.payload["raw"].items()]
    P = pd.DataFrame(rows, columns=["zone_id", "date", "raw"])
    ev = {(x["zone_id"], pd.Timestamp(e.sim_date)) for e in tr for x in e.payload["events"]}
    P["y"] = [int((z, d) in ev) for z, d in zip(P["zone_id"], P["date"])]
    P = P.sort_values(["zone_id", "date"]).reset_index(drop=True)
    fr = make_frame(P, (P["date"].min().strftime("%Y-%m-%d"), P["date"].max().strftime("%Y-%m-%d")))
    return metrics(match(fr, P["raw"].to_numpy(np.int8), 2, with_details=True))
