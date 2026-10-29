"""Verifier stage. Phase 3: mode 'off' = deterministic pass-through (risk.fused → risk.verified).
Phase 4 adds the tool-using LLM verifier with guardrails on L2+ candidates."""
from __future__ import annotations

from rockwatch.agents.base import Agent


class VerifierAgent(Agent):
    name = "verifier"
    topics = ["risk.fused"]

    def __init__(self, ctx, agent_id=None, mode: str = "off", **kw):
        super().__init__(ctx, agent_id, **kw)
        self.mode = mode

    def handle(self, env):
        if env.topic != "risk.fused":
            return []
        pl = dict(env.payload)
        pl["verifier"] = {"mode": self.mode, "decision": "PASS", "level_in": pl["level"], "level_out": pl["level"]}
        return [self.msg("risk.verified", env.sim_date, pl, zone_id=env.zone_id, quality=env.quality,
                         confidence=env.confidence, evidence_ids=[env.msg_id])]
