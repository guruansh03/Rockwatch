"""Bus factory."""
from __future__ import annotations

from pathlib import Path


def make_bus(kind: str, path: Path | str | None = None):
    if kind == "memory":
        from rockwatch.bus.memory import MemoryBus
        return MemoryBus()
    if kind == "sqlite":
        from rockwatch.bus.sqlite_bus import SqliteBus
        return SqliteBus(path)
    if kind == "redis":
        from rockwatch.bus.redis_bus import RedisBus
        return RedisBus()
    raise ValueError(kind)
