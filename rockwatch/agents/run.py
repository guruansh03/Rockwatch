"""Agent factory + process entry point: `python -m rockwatch.agents.run --agent NAME ...` (one OS process per agent)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rockwatch.agents.base import AgentContext, run_loop
from rockwatch.config import load_config


def classes():
    from rockwatch.agents.alert import AlertAgent
    from rockwatch.agents.context import ContextAgent
    from rockwatch.agents.evaluator import EvaluatorAgent
    from rockwatch.agents.evidence_rain import EvidenceRainAgent
    from rockwatch.agents.evidence_seismic import EvidenceSeismicAgent
    from rockwatch.agents.evidence_susceptibility import EvidenceSusceptibilityAgent
    from rockwatch.agents.evidence_thermal import EvidenceThermalAgent
    from rockwatch.agents.fusion import FusionAgent
    from rockwatch.agents.llm_verifier import VerifierAgent
    from rockwatch.agents.quality import QualityAgent
    from rockwatch.agents.sensor_rain import RainSensorAgent
    from rockwatch.agents.sensor_seismic import SeismicSensorAgent
    from rockwatch.agents.sensor_thermal import ThermalSensorAgent
    from rockwatch.agents.supervisor import SupervisorAgent
    return {c.name: c for c in (RainSensorAgent, ThermalSensorAgent, SeismicSensorAgent, QualityAgent, EvidenceRainAgent,
                                EvidenceThermalAgent, EvidenceSeismicAgent, EvidenceSusceptibilityAgent, ContextAgent, FusionAgent,
                                VerifierAgent, AlertAgent, SupervisorAgent, EvaluatorAgent)}


def agent_specs(cfg) -> list[tuple[str, str, dict]]:
    """(agent_id, class name, kwargs) for a full pipeline."""
    n = cfg["agents"]["rain_sensor_groups"]
    specs = [(f"sensor_rain_{g}", "sensor_rain", {"group": g, "n_groups": n}) for g in range(n)]
    specs += [(x, x, {}) for x in ("sensor_thermal", "sensor_seismic", "quality", "evidence_rain", "evidence_thermal",
                                   "evidence_seismic", "evidence_susceptibility", "context", "fusion", "verifier", "alert",
                                   "supervisor", "evaluator")]
    return specs


def build(ctx: AgentContext, bus=None, only: list[str] | None = None) -> list:
    C = classes()
    out = []
    for aid, cname, kw in agent_specs(ctx.cfg):
        if only and aid not in only:
            continue
        if cname == "supervisor":
            kw = {**kw, "bus": bus}
        out.append(C[cname](ctx, agent_id=aid, **kw))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--speed", type=float, default=1.5)
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, filename=str(Path(a.run_dir) / f"{a.agent}.log"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from rockwatch.bus.sqlite_bus import SqliteBus
    cfg = load_config(a.config)
    ctx = AgentContext(cfg, a.region, a.start, a.end, a.speed)
    bus = SqliteBus(Path(a.run_dir) / "bus.sqlite")
    agent = build(ctx, bus, only=[a.agent])[0]
    run_loop(agent, bus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
