"""LLM provider interface + factory (ROCKWATCH_LLM_PROVIDER = anthropic | groq | ollama | mock)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    """Read-only tool exposed to a tool-using provider."""
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., Any]


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 1
    cached: bool = False
    error: str | None = None


class Provider:
    name = "base"
    supports_tools = False

    def __init__(self, model: str, timeout_s: float = 20.0, max_tool_turns: int = 4):
        self.model, self.timeout_s, self.max_tool_turns = model, timeout_s, max_tool_turns

    def complete(self, system: str, user: str, tools: list[ToolSpec] | None = None, max_tokens: int = 600,
                 meta: dict[str, Any] | None = None) -> LLMResult:
        raise NotImplementedError


def make_provider(cfg: dict[str, Any], role: str = "verifier", name: str | None = None, batch: bool = False) -> Provider:
    """role ∈ {verifier, writer}. Model IDs from env (§9.4). batch=True: offline eval/smoke (rate-limit pacing on)."""
    from dotenv import load_dotenv

    from rockwatch.config import repo_path
    load_dotenv(repo_path(".env"))
    lc = cfg["llm"]
    name = name or os.getenv("ROCKWATCH_LLM_PROVIDER", lc.get("provider", "mock"))
    if name == "anthropic":
        from rockwatch.llm.anthropic_provider import AnthropicProvider
        model = os.getenv("ROCKWATCH_MODEL_VERIFIER" if role == "verifier" else "ROCKWATCH_MODEL_WRITER",
                          "claude-haiku-5-5" if role == "verifier" else "claude-sonnet-5-5")
        return AnthropicProvider(model, lc["timeout_s"], lc["max_tool_turns"])
    if name == "groq":
        from rockwatch.llm.groq_provider import GroqProvider
        g = lc.get("groq", {})
        model = os.getenv("GROQ_MODEL_VERIFIER" if role == "verifier" else "GROQ_MODEL_WRITER",
                          g.get("verifier" if role == "verifier" else "writer", "openai/gpt-oss-20b"))
        return GroqProvider(model, lc["timeout_s"], lc["max_tool_turns"], min_interval_s=g.get("min_interval_s_batch", 7.5) if batch else 0.0)
    if name == "ollama":
        from rockwatch.llm.ollama_provider import OllamaProvider
        return OllamaProvider(os.getenv("OLLAMA_MODEL", "qwen2.5:7b"), lc["timeout_s"], lc["max_tool_turns"],
                              url=os.getenv("OLLAMA_URL", "http://localhost:11434"))
    if name == "mock":
        from rockwatch.llm.mock_provider import MockProvider
        return MockProvider("mock-rules-v1")
    raise ValueError(f"unknown provider {name}")
