"""Optional rockfall track: USGS DS746 Yosemite rock falls 1857-2011.

Download if reachable; else skip and log. Eyewitness bias. Used only if Phase 0 shows value.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
XLSX_NAME = "Yosemite_rock_fall_database_1857-2011.xlsx"


def fetch_yosemite(index_url: str, raw_dir: Path, timeout: int = 60) -> Path | None:
    """Find the .xlsx link on the DS746 page and download it. Returns None (logged) on failure."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / XLSX_NAME
    if dest.exists():
        return dest
    try:
        import requests
        from urllib.parse import urljoin

        r = requests.get(index_url, timeout=timeout)
        r.raise_for_status()
        links = re.findall(r'href="([^"]+\.xlsx)"', r.text, flags=re.I)
        if not links:
            log.warning("DS746: no .xlsx link on %s; skipping", index_url)
            return None
        url = urljoin(index_url, next((l for l in links if "rock" in l.lower()), links[0]))
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
    except Exception as e:  # noqa: BLE001
        log.warning("DS746 fetch failed (%r); Yosemite track skipped", e)
        return None


def load_yosemite(path: Path) -> pd.DataFrame:
    """Load all sheets; return the largest as raw DataFrame (schema profiled, not assumed)."""
    sheets = pd.read_excel(path, sheet_name=None)
    name = max(sheets, key=lambda k: len(sheets[k]))
    df = sheets[name]
    df.attrs["sheet"] = name
    return df
