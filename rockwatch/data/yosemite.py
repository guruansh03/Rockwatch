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
    """Parse the `Master` sheet. Header row located by the 'Year' cell. Adds `date` (exact Y/M/D only)
    and `date_kind` (exact|undated). Narrative/free-text columns are untrusted: dropped."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = pd.read_excel(path, sheet_name="Master", header=None)
    hdr = next(i for i in range(min(30, len(raw))) if "Year" in [str(x).strip() for x in raw.iloc[i].tolist()])
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr].tolist()]
    df = df.dropna(how="all")
    df = df.drop(columns=[c for c in df.columns if c.lower().startswith(("narrative", "published"))])
    y = pd.to_numeric(df["Year"], errors="coerce")
    m = pd.to_numeric(df["Month"], errors="coerce")
    d = pd.to_numeric(df["Day"], errors="coerce")
    ok = y.notna() & m.between(1, 12) & d.between(1, 31)
    dates = pd.to_datetime(
        dict(year=y.where(ok), month=m.where(ok), day=d.where(ok)), errors="coerce"
    )
    df["date"] = dates
    df["date_kind"] = df["date"].notna().map({True: "exact", False: "undated"})
    df.attrs["sheet"] = "Master"
    return df.reset_index(drop=True)


def yosemite_profile_md(df: pd.DataFrame, min_year: int) -> str:
    """Markdown section for the profile."""
    ex = df[(df["date_kind"] == "exact") & (df["date"].dt.year >= min_year)]
    typ = "Type of slope movement"
    trig = "Triggering condition(s)"
    out = [f"\n## 7. Yosemite DS746 (rockfall track candidate)\n",
           f"- Rows: {len(df)}; exact-dated (Y/M/D): {(df['date_kind'] == 'exact').sum()}; exact since {min_year}: **{len(ex)}**; "
           f"distinct dates since {min_year}: **{ex['date'].nunique()}**.",
           "- No coordinates in sheet (named locations only) → whole valley ≈ 1–2 zones (0.25°). Eyewitness/reporting bias.",
           "\n- Exact since %d by 5-yr bin:\n" % min_year,
           (ex["date"].dt.year // 5 * 5).value_counts().sort_index().to_frame("n").to_markdown() if hasattr(pd.DataFrame, "to_markdown") and _has_tabulate() else str((ex["date"].dt.year // 5 * 5).value_counts().sort_index().to_dict())]
    if typ in df.columns:
        out.append(f"\n- `{typ}` (exact since {min_year}): {ex[typ].astype(str).value_counts().to_dict()}")
    if trig in df.columns:
        out.append(f"- `{trig}` (exact since {min_year}, top 12): {ex[trig].astype(str).value_counts().head(12).to_dict()}")
    return "\n".join(out) + "\n"


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False
