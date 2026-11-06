"""Groq provider without network: request shape, 429 retry-after, optional-param fallback, key handling, factory."""
from __future__ import annotations

import json

import pytest

from rockwatch.llm import groq_provider as G


class Resp:
    def __init__(self, code, body=None, headers=None, text=""):
        self.status_code, self._body, self.headers, self.text = code, body or {}, headers or {}, text or json.dumps(body or {})

    def json(self):
        return self._body


OK = {"choices": [{"message": {"content": '{"decision": "CONFIRM"}'}}], "usage": {"prompt_tokens": 600, "completion_tokens": 90}}


@pytest.fixture
def prov(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    return G.GroqProvider("openai/gpt-oss-20b", timeout_s=5)


def test_request_and_parse(prov, monkeypatch):
    seen = {}

    def post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        return Resp(200, OK)
    monkeypatch.setattr("requests.post", post)
    r = prov.complete("sys", "user", max_tokens=300)
    assert r.text == '{"decision": "CONFIRM"}' and r.input_tokens == 600 and r.output_tokens == 90 and r.provider == "groq"
    b = seen["body"]
    assert seen["url"] == G.URL and seen["auth"] == "Bearer test-key"
    assert b["response_format"] == {"type": "json_object"} and b["temperature"] == 0 and b["max_completion_tokens"] == 1000
    assert b["messages"][0] == {"role": "system", "content": "sys"}


def test_429_then_ok(prov, monkeypatch):
    calls = iter([Resp(429, headers={"retry-after": "0"}), Resp(200, OK)])
    monkeypatch.setattr("requests.post", lambda *a, **k: next(calls))
    monkeypatch.setattr(G.time, "sleep", lambda s: None)
    assert prov.complete("s", "u").text.startswith("{")


def test_long_retry_after_raises_in_live_mode(prov, monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: Resp(429, headers={"retry-after": "30"}))
    with pytest.raises(RuntimeError, match="rate limited"):
        prov.complete("s", "u")          # live: max wait 3 s → caller falls back deterministically


def test_optional_param_dropped_on_400(prov, monkeypatch):
    bodies = []

    def post(url, headers, json, timeout):
        bodies.append(json)
        if "response_format" in json:
            return Resp(400, text='{"error": {"message": "response_format json_object is not supported"}}')
        return Resp(200, OK)
    monkeypatch.setattr("requests.post", post)
    assert prov.complete("s", "u").text
    assert "response_format" in bodies[0] and "response_format" not in bodies[1] and "response_format" in prov.dropped


def test_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        G.GroqProvider("openai/gpt-oss-20b")


def test_factory_and_cap(monkeypatch):
    from rockwatch.config import load_config
    from rockwatch.llm.provider import make_provider
    from rockwatch.llm.runtime import LLMRuntime
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    cfg = load_config()
    p = make_provider(cfg, "verifier", "groq", batch=True)
    assert p.name == "groq" and p.min_interval_s > 0 and p.model == cfg["llm"]["groq"]["verifier"]
    assert make_provider(cfg, "writer", "groq").min_interval_s == 0
    assert LLMRuntime(cfg, "verifier", provider=p).max_calls == cfg["llm"]["groq"]["max_llm_calls"]
