"""Guardrails (§9.4) with the mock provider: enforced in code, model never trusted."""
from __future__ import annotations

import pytest

from rockwatch.agents.llm_analyst import AnalystStore, answer
from rockwatch.agents.llm_composer import compose
from rockwatch.agents.llm_verifier import verify
from rockwatch.bus.memory import MemoryBus
from rockwatch.config import load_config
from rockwatch.llm.guardrails import ALLOWED_ACTIONS, check_verifier, numbers_ok
from rockwatch.llm.mock_provider import MockProvider
from rockwatch.llm.runtime import LLMRuntime
from rockwatch.schemas import Envelope

TH = {"t1": 0.01, "t2": 0.03, "t3": 0.06, "l3_enabled": True}


class FakeStore:
    """SYNTHETIC evidence (test-only)."""

    def __init__(self, contrib, quality="ok", p=0.05):
        self.c, self.q, self.p = contrib, quality, p

    def zone_evidence(self, z, d):
        return {"zone_id": z, "date": d, "p": self.p, "logit": -2.9, "provisional_level": 2, "n_dynamic_positive": 0,
                "contributions": self.c, "features": {"rain": {"P3": 12.5}}, "evidence_ids": ["e1", "e2"]}

    def regional_extent(self, d):
        return {"date": d, "regional_extent": 0.4, "zones_provisional_L2plus": 3, "zones_total": 10, "evidence_ids": ["e3"]}

    def zone_history(self, z, d):
        return {"zone_id": z, "train_and_undated_inventory_features": 12, "alert_days_L2plus_last_14": 2, "evidence_ids": ["e4"]}

    def data_quality(self, z, d):
        q = {g: self.q for g in self.c}
        return {"zone_id": z, "date": d, "modality_quality": q, "quality_ok": self.q == "ok", "stale_agents": [], "evidence_ids": ["e5"]}

    def snow_context(self, z, d):
        return {"zone_id": z, "date": d, "snowfall_cm_7d": 0.0, "days_reported": 7, "tmax_c": 11.2, "tmin_c": 3.1, "evidence_ids": ["e6"]}


@pytest.fixture
def rt(tmp_path):
    cfg = load_config()
    cfg["paths"]["cache"] = str(tmp_path)
    return LLMRuntime(cfg, "verifier", provider=MockProvider("mock-rules-v1"))


DYN = {"rain": 0.8, "thermal": -0.1, "seismic": 0.0, "susceptibility": 0.5, "context": 0.1}
STATIC = {"rain": -0.2, "thermal": -0.1, "seismic": 0.0, "susceptibility": 1.2, "context": 0.1}


def run(rt, store, cur=2, fault=None, ndyn=1):
    return verify(rt, store, "r1c1", "2017-09-01", cur, store.p, TH, ndyn, 2, fault=fault)


def test_valid_confirm(rt):
    r = run(rt, FakeStore(DYN))
    assert r["verifier"] == "llm" and r["decision"] == "CONFIRM" and r["level_out"] == 2


def test_never_raise_level(rt):
    r = run(rt, FakeStore(DYN), fault="raise_level")
    assert r["verifier"] == "fallback" and r["level_out"] == 2
    assert "level_not_current_or_minus_one" in r["usage"]["violations"]
    assert r["usage"]["attempts"] == 2      # retried once


def test_invalid_json_fallback(rt):
    r = run(rt, FakeStore(DYN), fault="invalid_json")
    assert r["verifier"] == "fallback" and r["usage"]["outcome"] == "fallback_guardrail"


def test_unsupported_number_and_unknown_id(rt):
    r = run(rt, FakeStore(DYN), fault="bad_number")
    assert r["verifier"] == "fallback" and any(v.startswith("unsupported_numbers") for v in r["usage"]["violations"])
    r = run(rt, FakeStore(DYN), fault="bad_evidence_id")
    assert "unknown_evidence_id" in r["usage"]["violations"]


@pytest.mark.parametrize("store,cur,why", [
    (FakeStore({**STATIC, "seismic": 0.3}), 2, "downgrade_forbidden_seismic"),
    (FakeStore(STATIC, quality="degraded"), 2, "downgrade_forbidden_quality"),
    (FakeStore(STATIC, p=0.07), 3, "downgrade_forbidden_L3"),
])
def test_forbidden_downgrades(rt, store, cur, why):
    r = run(rt, store, cur=cur, fault="forbidden_downgrade")
    assert r["level_out"] == cur and why in r["usage"]["violations"]


def test_allowed_downgrade(rt):
    r = run(rt, FakeStore(STATIC), ndyn=0)
    assert r["decision"] == "DOWNGRADE" and r["level_out"] == 1


def test_confirm_corroborates_l3_only_if_p_ge_t3(rt):
    hi = run(rt, FakeStore(DYN, p=0.07), ndyn=1)
    lo = run(rt, FakeStore(DYN, p=0.05), ndyn=1)
    assert hi["level_out"] == 3 and hi["l3_corroborated_by_llm"]
    assert lo["level_out"] == 2


def test_cache_and_cap(rt):
    s = FakeStore(DYN)
    run(rt, s)
    n = rt.calls
    r = run(rt, s)
    assert rt.calls == n and r["usage"]["cached"]
    rt.max_calls = rt.calls
    r = run(rt, FakeStore(DYN, p=0.051))
    assert r["verifier"] == "fallback" and r["usage"]["outcome"] == "fallback_cap"


def test_numbers_tolerance():
    ev = {"p": 0.04372, "c": {"rain": 0.812}, "zone_id": "r9c8", "date": "2017-09-01"}
    assert numbers_ok("zone r9c8 on 2017-09-01: p 0.044, rain 0.81, L2", ev)[0]
    assert not numbers_ok("p 0.05", ev)[0]
    assert not numbers_ok("failure expected in 3 days", ev)[0]


def test_check_verifier_schema():
    assert check_verifier({"decision": "CONFIRM"}, 2, {}, {}, {}, set())[0].startswith("missing_field")


def test_composer(rt):
    a = {"zone_id": "r1c1", "date": "2017-09-01", "level": 2, "p": 0.0512, "top_modality": "rain", "contributions": {"rain": 0.8}, "episode_id": "x"}
    m, _ = compose(rt, a)
    assert m["source"] == "llm" and set(m["actions"]) <= set(ALLOWED_ACTIONS[2])
    m, rec = compose(rt, a, fault="bad_action")
    assert m["source"] == "template" and "action_not_allowed" in rec["violations"]
    m, _ = compose(None, a)                      # LLM offline
    assert m["source"] == "template"


def test_analyst(rt):
    bus = MemoryBus()
    bus.publish(Envelope(topic="alerts.active", agent_id="alert", zone_id="r1c1", sim_date="2017-09-01", kind="escalate",
                         payload={"from": 0, "to": 2, "p": 0.05}))
    st = AnalystStore(bus, load_config())
    assert answer(rt, st, "When exactly will the slope in r1c1 fail?")["source"] == "refusal"
    assert answer(rt, st, "What is the field performance in a mine?")["source"] == "refusal"
    a = answer(rt, st, "Which alerts were raised in r1c1?")
    assert a["source"] == "llm" and a["citations"]
    a = answer(rt, st, "Which alerts were raised in r1c1?", fault="bad_evidence_id")   # irrelevant fault → still valid
    assert a["source"] in ("llm", "fallback")
