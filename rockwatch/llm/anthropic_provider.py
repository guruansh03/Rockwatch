"""Anthropic Messages API with tool use (≤ max_tool_turns). Current 5.5-family models reject temperature/top_p
(400), so sampling params are omitted; reproducibility comes from the response cache (D-034)."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from rockwatch.llm.provider import LLMResult, Provider, ToolSpec


class AnthropicProvider(Provider):
    name = "anthropic"
    supports_tools = True

    def __init__(self, model, timeout_s=20.0, max_tool_turns=4):
        super().__init__(model, timeout_s, max_tool_turns)
        import anthropic
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set (.env)")
        self.client = anthropic.Anthropic(timeout=timeout_s, max_retries=1)

    def complete(self, system, user, tools=None, max_tokens=600, meta=None):
        t0 = time.time()
        msgs: list[dict[str, Any]] = [{"role": "user", "content": user}]
        tdefs = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in (tools or [])]
        fns = {t.name: t.fn for t in (tools or [])}
        res = LLMResult("", self.name, self.model, turns=0)
        for turn in range(self.max_tool_turns + 1):
            kw: dict[str, Any] = dict(model=self.model, system=system, messages=msgs, max_tokens=max_tokens)
            if tdefs and turn < self.max_tool_turns:
                kw["tools"] = tdefs
            r = self.client.messages.create(**kw)
            res.turns += 1
            res.input_tokens += r.usage.input_tokens
            res.output_tokens += r.usage.output_tokens
            uses = [b for b in r.content if b.type == "tool_use"]
            if not uses:
                res.text = "".join(b.text for b in r.content if b.type == "text")
                break
            msgs.append({"role": "assistant", "content": [b.model_dump() for b in r.content]})
            results = []
            for u in uses:
                try:
                    out = fns[u.name](**(u.input or {}))
                except Exception as e:  # noqa: BLE001
                    out = {"error": repr(e)}
                res.tool_calls.append({"name": u.name, "input": u.input})
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": json.dumps(out, default=str)})
            msgs.append({"role": "user", "content": results})
        res.latency_s = round(time.time() - t0, 3)
        return res
