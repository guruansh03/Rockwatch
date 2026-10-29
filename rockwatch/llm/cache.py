"""LLM response cache: key = sha256(provider + model + prompt + evidence) → data/cache/llm/<key>.json (reproducible reruns)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rockwatch.llm.provider import LLMResult


def key(provider: str, model: str, system: str, user: str, evidence: Any) -> str:
    h = hashlib.sha256()
    for part in (provider, model, system, user, json.dumps(evidence, sort_keys=True, default=str)):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class LLMCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, k: str) -> LLMResult | None:
        p = self.root / f"{k}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        r = LLMResult(**d)
        r.cached = True
        return r

    def put(self, k: str, r: LLMResult) -> None:
        if r.error:
            return
        (self.root / f"{k}.json").write_text(json.dumps(asdict(r), default=str), encoding="utf-8")
