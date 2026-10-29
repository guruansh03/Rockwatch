"""Shared LLM call path: prompt load, cache, call cap, one retry on guardrail failure, usage log."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from rockwatch.config import repo_path
from rockwatch.llm import cache as C
from rockwatch.llm.guardrails import parse_json
from rockwatch.llm.provider import Provider, make_provider

PROMPTS = Path(__file__).parent / "prompts"


def prompt(name: str, **kw: Any) -> str:
    shared = (PROMPTS / "shared_rules.md").read_text(encoding="utf-8")
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").format(**kw) + "\n\n" + shared


class LLMRuntime:
    """One per agent/eval run. `max_calls` caps NON-cached provider calls; beyond it callers fall back."""

    def __init__(self, cfg: dict[str, Any], role: str, provider: Provider | None = None, max_calls: int | None = None):
        self.cfg = cfg
        self.provider = provider or make_provider(cfg, role)
        self.cache = C.LLMCache(repo_path(cfg["paths"]["cache"]) / "llm")
        self.max_calls = max_calls if max_calls is not None else cfg["llm"]["max_llm_calls"]
        self.calls = 0
        self.records: list[dict[str, Any]] = []

    def run(self, task: str, system: str, user: str, evidence: Any, check: Callable[[dict | None], list[str]],
            tools=None, meta: dict[str, Any] | None = None, max_tokens: int = 500) -> tuple[dict | None, dict[str, Any]]:
        """→ (validated output or None, usage record). None ⇒ caller uses its deterministic fallback."""
        p = self.provider
        rec: dict[str, Any] = {"task": task, "provider": p.name, "model": p.model, "attempts": 0, "cached": False, "input_tokens": 0,
                               "output_tokens": 0, "latency_s": 0.0, "violations": [], "outcome": None, "tool_calls": 0}
        msg = user
        for attempt in range(2):
            fault = (meta or {}).get("_mock_fault")   # test-only fault injection must not hit/poison the cache
            k = C.key(p.name, p.model, system, msg, evidence if fault is None else {"e": evidence, "fault": fault})
            r = self.cache.get(k)
            if r is None:
                if self.calls >= self.max_calls:
                    rec["outcome"] = "fallback_cap"
                    break
                self.calls += 1
                t0 = time.time()
                try:
                    r = p.complete(system, msg, tools=tools if p.supports_tools else None, max_tokens=max_tokens, meta=meta)
                except Exception as e:  # noqa: BLE001 (timeout, HTTP, auth)
                    rec["violations"].append(f"provider_error:{type(e).__name__}")
                    rec["latency_s"] += round(time.time() - t0, 3)
                    rec["outcome"] = "fallback_error"
                    break
                self.cache.put(k, r)
            rec["attempts"] += 1
            rec["cached"] = rec["cached"] or r.cached
            rec["input_tokens"] += r.input_tokens
            rec["output_tokens"] += r.output_tokens
            rec["latency_s"] += r.latency_s
            rec["tool_calls"] += len(r.tool_calls)
            out = parse_json(r.text)
            v = check(out)
            if not v:
                rec["outcome"] = "ok" if attempt == 0 else "ok_after_retry"
                self.records.append(rec)
                return out, rec
            rec["violations"] += v
            msg = user + "\n\nYour previous answer violated these rules: " + "; ".join(v) + ". Return corrected JSON only."
            if meta is not None and "_mock_fault" in meta and attempt == 0 and meta.get("_mock_fault_once"):
                meta = {k2: v2 for k2, v2 in meta.items() if k2 != "_mock_fault"}
        rec["outcome"] = rec["outcome"] or "fallback_guardrail"
        self.records.append(rec)
        return None, rec

    def usage(self) -> dict[str, Any]:
        from collections import Counter
        o = Counter(r["outcome"] for r in self.records)
        return {"provider": self.provider.name, "model": self.provider.model, "calls_made": self.calls, "cap": self.max_calls,
                "requests": len(self.records), "outcomes": dict(o), "cached": sum(r["cached"] for r in self.records),
                "input_tokens": sum(r["input_tokens"] for r in self.records), "output_tokens": sum(r["output_tokens"] for r in self.records),
                "latency_s_total": round(sum(r["latency_s"] for r in self.records), 2),
                "cost": None if not self.cfg["llm"].get("prices") else None}
