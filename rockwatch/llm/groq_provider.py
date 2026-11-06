"""Groq (OpenAI-compatible chat completions, free tier). No tool loop: callers pre-bundle the evidence into the
prompt, exactly as for Ollama (§9.4). Handles the free-tier rate limits: optional pacing between requests and
429 retry-after waits. Never logs the key."""
from __future__ import annotations

import os
import threading
import time

from rockwatch.llm.provider import LLMResult, Provider

URL = "https://api.groq.com/openai/v1/chat/completions"
OPTIONAL = ("response_format", "reasoning_effort")   # dropped (once, remembered) if the API rejects them


class GroqProvider(Provider):
    name = "groq"
    supports_tools = False
    _lock = threading.Lock()
    _last = 0.0          # wall time of the last request (process-wide pacing)

    def __init__(self, model, timeout_s=20.0, max_tool_turns=4, min_interval_s=0.0, max_wait_s=None):
        super().__init__(model, timeout_s, max_tool_turns)
        self.key = os.getenv("GROQ_API_KEY", "").strip()
        if not self.key:
            raise RuntimeError("GROQ_API_KEY not set (.env)")
        self.min_interval_s = float(min_interval_s)
        # batch runs (pacing on) may wait out a per-minute limit; live runs keep waits short so deadlines hold
        self.max_wait_s = float(max_wait_s if max_wait_s is not None else (65.0 if self.min_interval_s > 0 else 3.0))
        self.dropped: set[str] = set()

    def _body(self, system, user, max_tokens):
        b = {"model": self.model, "temperature": 0,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
             # reasoning models spend completion tokens on reasoning first: leave room for the JSON answer
             "max_completion_tokens": int(max_tokens) + (700 if "gpt-oss" in self.model else 0),
             "response_format": {"type": "json_object"}}
        if "gpt-oss" in self.model:
            b["reasoning_effort"] = "low"
        for k in self.dropped:
            b.pop(k, None)
        return b

    def _pace(self):
        if self.min_interval_s <= 0:
            return
        with GroqProvider._lock:
            wait = GroqProvider._last + self.min_interval_s - time.time()
            if wait > 0:
                time.sleep(wait)
            GroqProvider._last = time.time()

    def complete(self, system, user, tools=None, max_tokens=600, meta=None):
        import requests
        t0 = time.time()
        hdr = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(5):
            self._pace()
            r = requests.post(URL, headers=hdr, json=self._body(system, user, max_tokens), timeout=self.timeout_s)
            if r.status_code == 429:
                try:
                    wait = float(r.headers.get("retry-after", "5"))
                except ValueError:
                    wait = 5.0
                if wait > self.max_wait_s or attempt == 4:
                    raise RuntimeError(f"groq rate limited (retry-after {wait:.0f}s)")
                time.sleep(wait + 0.5)
                continue
            if r.status_code == 400:
                msg = r.text.lower()
                bad = [k for k in OPTIONAL if k not in self.dropped and (k in msg or (k == "response_format" and "json" in msg))]
                if bad:
                    self.dropped.update(bad)
                    continue
            if r.status_code >= 400:
                raise RuntimeError(f"groq HTTP {r.status_code}: {r.text[:200]}")
            js = r.json()
            u = js.get("usage") or {}
            text = (js["choices"][0]["message"].get("content") or "").strip()
            return LLMResult(text, self.name, self.model, int(u.get("prompt_tokens", 0)),
                             int(u.get("completion_tokens", 0)), round(time.time() - t0, 3))
        raise RuntimeError("groq: retries exhausted")
