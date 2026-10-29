"""Redis Streams backend — cut (cut-list item #1, D-027). Kept as an explicit stub so `--bus redis` fails clearly."""
from rockwatch.bus.base import Bus


class RedisBus(Bus):  # pragma: no cover
    def __init__(self, *a, **k):
        raise NotImplementedError("Redis backend cut (cut list #1). Use --bus sqlite (default) or memory.")
