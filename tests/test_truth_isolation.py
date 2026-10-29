"""§9.2 truth isolation: only EvaluatorAgent and the dashboard overlay may read truth.events.
Static: source scan. Runtime: bus refuses other consumers; agents never subscribe to truth."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rockwatch.bus.base import TruthAccessError
from rockwatch.bus.memory import MemoryBus
from rockwatch.schemas import TRUTH_TOPIC, Envelope

PKG = Path(__file__).resolve().parent.parent / "rockwatch"
# Files allowed to mention the truth topic: definition, access control, publisher, the evaluator, the dashboard overlay.
TOPIC_ALLOWED = {"schemas.py", "bus/base.py", "replay/engine.py", "agents/evaluator.py", "dashboard/app.py"}
# Files allowed to open ground-truth event tables (offline data/eval code + truth publisher; never live agents).
EVENTS_FILE_ALLOWED = {"data/build.py", "eval/runner.py", "replay/engine.py"}


def rel(p: Path) -> str:
    return p.relative_to(PKG).as_posix()


def test_static_truth_topic_references():
    bad = [rel(p) for p in PKG.rglob("*.py") if re.search(r"TRUTH_TOPIC|truth\.events", p.read_text(encoding="utf-8"))
           and rel(p) not in TOPIC_ALLOWED]
    assert not bad, f"truth topic referenced outside allowed modules: {bad}"


def test_static_no_agent_reads_event_tables():
    bad = [rel(p) for p in PKG.rglob("*.py") if "events.parquet" in p.read_text(encoding="utf-8") and rel(p) not in EVENTS_FILE_ALLOWED]
    assert not bad, f"ground-truth tables opened outside allowed modules: {bad}"


def test_agent_subscriptions():
    from rockwatch.agents.run import classes
    for name, cls in classes().items():
        if name == "evaluator":
            assert TRUTH_TOPIC in cls.topics
        else:
            assert TRUTH_TOPIC not in cls.topics, name


@pytest.mark.parametrize("consumer", ["fusion", "alert", "verifier", "evidence_rain", "llm_analyst"])
def test_runtime_bus_refuses(consumer):
    b = MemoryBus()
    b.publish(Envelope(topic=TRUTH_TOPIC, agent_id="replay_engine", kind="day_close", payload={"events": []}))
    with pytest.raises(TruthAccessError):
        b.poll(consumer, [TRUTH_TOPIC])
    with pytest.raises(TruthAccessError):
        b.read(consumer, ["alerts.active", TRUTH_TOPIC])


def test_runtime_allowed():
    b = MemoryBus()
    b.publish(Envelope(topic=TRUTH_TOPIC, agent_id="replay_engine", kind="day_close", payload={"events": []}))
    assert len(b.poll("evaluator", [TRUTH_TOPIC])) == 1
    assert len(b.read("dashboard_overlay", [TRUTH_TOPIC])) == 1


def test_sqlite_bus_refuses(tmp_path):
    from rockwatch.bus.sqlite_bus import SqliteBus
    b = SqliteBus(tmp_path / "b.sqlite")
    with pytest.raises(TruthAccessError):
        b.poll("fusion", ["risk.fused", TRUTH_TOPIC])
