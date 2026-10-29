"""Abstract bus. Backends: memory (tests/batch), sqlite (demo default), redis (optional; cut-list #1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from rockwatch.schemas import TRUTH_ALLOWED_PREFIXES, TRUTH_TOPIC, Envelope


class TruthAccessError(PermissionError):
    """A non-allowed consumer tried to read truth.events."""


def check_access(consumer: str, topics: Iterable[str]) -> None:
    """Runtime truth isolation: only evaluator*/dashboard* may read truth.events."""
    if TRUTH_TOPIC in set(topics) and not consumer.startswith(TRUTH_ALLOWED_PREFIXES):
        raise TruthAccessError(f"{consumer} may not read {TRUTH_TOPIC}")


class Bus(ABC):
    """Append-only log with per-consumer offsets."""

    @abstractmethod
    def publish(self, envs: Envelope | list[Envelope]) -> None: ...

    @abstractmethod
    def _poll(self, consumer: str, topics: list[str], max_n: int) -> list[Envelope]: ...

    @abstractmethod
    def _read(self, topics: list[str], since_seq: int, kind: str | None, limit: int | None, latest: bool) -> list[Envelope]: ...

    def poll(self, consumer: str, topics: list[str], max_n: int = 5000) -> list[Envelope]:
        """New messages on topics since this consumer's offset; advances the offset (at-most-once)."""
        check_access(consumer, topics)
        return self._poll(consumer, topics, max_n)

    def read(self, reader: str, topics: list[str], since_seq: int = 0, kind: str | None = None,
             limit: int | None = None, latest: bool = False) -> list[Envelope]:
        """Random-access read of the log (restore, dashboard, offline eval). Truth-gated."""
        check_access(reader, topics)
        return self._read(topics, since_seq, kind, limit, latest)

    def close(self) -> None:  # pragma: no cover
        pass
