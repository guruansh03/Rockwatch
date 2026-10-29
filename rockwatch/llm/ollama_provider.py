"""Local Ollama (free). No tool loop: callers pre-bundle evidence into the prompt (§9.4)."""
from __future__ import annotations

import time

from rockwatch.llm.provider import LLMResult, Provider


class OllamaProvider(Provider):
    name = "ollama"
    supports_tools = False

    def __init__(self, model, timeout_s=20.0, max_tool_turns=4, url="http://localhost:11434"):
        super().__init__(model, timeout_s, max_tool_turns)
        self.url = url.rstrip("/")

    def complete(self, system, user, tools=None, max_tokens=600, meta=None):
        import requests
        t0 = time.time()
        r = requests.post(f"{self.url}/api/chat", timeout=self.timeout_s, json={
            "model": self.model, "stream": False, "format": "json",
            "options": {"temperature": 0, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        js = r.json()
        return LLMResult(js["message"]["content"], self.name, self.model, js.get("prompt_eval_count", 0), js.get("eval_count", 0),
                         round(time.time() - t0, 3))
