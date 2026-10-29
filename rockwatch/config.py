"""Config loading. All tunables live in config/default.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "default.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load YAML config; default = config/default.yaml."""
    p = Path(path) if path else DEFAULT_CONFIG
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def repo_path(rel: str | Path) -> Path:
    """Resolve a repo-relative path."""
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p
