"""In-process bus (tests, batch, deterministic local runner)."""
from __future__ import annotations

import threading

from rockwatch.bus.base import Bus
from rockwatch.schemas import Envelope


class MemoryBus(Bus):
    def __init__(self) -> None:
        self.log: list[Envelope] = []
        self.offsets: dict[str, int] = {}
        self.lock = threading.Lock()

    def publish(self, envs):
        envs = envs if isinstance(envs, list) else [envs]
        with self.lock:
            for e in envs:
                e.seq = len(self.log) + 1
                self.log.append(e)

    def _poll(self, consumer, topics, max_n):
        ts = set(topics)
        with self.lock:
            off = self.offsets.get(consumer, 0)
            out = [e for e in self.log[off:] if e.topic in ts][:max_n]
            if out:
                # advance to the last returned seq (messages of other topics in between are skipped safely)
                self.offsets[consumer] = out[-1].seq if len(out) == max_n else len(self.log)
            else:
                self.offsets[consumer] = len(self.log)
        return out

    def _read(self, topics, since_seq, kind, limit, latest):
        ts = set(topics)
        with self.lock:
            out = [e for e in self.log[since_seq:] if e.topic in ts and (kind is None or e.kind == kind)]
        if latest:
            out = out[-(limit or 1):]
        elif limit:
            out = out[:limit]
        return out
