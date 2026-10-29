"""Message envelope + topic registry (§9.2)."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

TOPICS = {
    "sim.clock",            # replay engine day ticks (D-026)
    "sensor.rain", "sensor.thermal", "sensor.seismic",
    "quality.flags",
    "evidence.rain", "evidence.thermal", "evidence.seismic", "evidence.susceptibility", "evidence.context",
    "risk.fused", "risk.verified",
    "alerts.active", "alerts.ack",
    "agents.heartbeat", "agents.control",
    "llm.calls",
    "truth.events",
    "eval.live",
}
TRUTH_TOPIC = "truth.events"
# Only these consumers may read ground truth (§9.2). Enforced in Bus.check_access.
TRUTH_ALLOWED_PREFIXES = ("evaluator", "dashboard")
Quality = Literal["ok", "degraded", "missing"]


class Envelope(BaseModel):
    """Bus message."""
    msg_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    topic: str
    agent_id: str
    zone_id: str | None = None
    sim_date: str | None = None
    wall_ts: float = Field(default_factory=time.time)
    kind: str = "data"
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    quality: Quality = "ok"
    evidence_ids: list[str] = Field(default_factory=list)
    seq: int | None = None  # set by the bus on read

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        if self.topic not in TOPICS:
            raise ValueError(f"unknown topic {self.topic}")


def worst(*qs: str) -> str:
    """Worst quality among inputs."""
    order = {"ok": 0, "degraded": 1, "missing": 2}
    return max(qs, key=lambda q: order[q]) if qs else "ok"
