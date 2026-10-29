"""Open-Meteo archive (ERA5-based reanalysis) daily "gauges" per zone centre. Cached + resumable.

Weather data by Open-Meteo.com (CC BY 4.0). Free tier is non-commercial and quota-limited
(600/min, 5,000/h, 10,000/day weighted calls; long ranges count as several calls).
A 429 stops the batch; nothing is ever synthesised to fill gaps.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


class QuotaExceeded(RuntimeError):
    """Open-Meteo returned 429. `scope` in {minutely, hourly, daily, unknown}."""

    def __init__(self, scope: str, reason: str):
        super().__init__(f"{scope}: {reason}")
        self.scope = scope
        self.reason = reason


@dataclass
class ZoneRequest:
    """One zone's fetch spec."""
    region: str
    zone_id: str
    lat: float
    lon: float
    start: str
    end: str


def chunks(start: str, end: str, years: int) -> list[tuple[str, str]]:
    """Split [start, end] into ≤ `years`-long inclusive ranges."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out = []
    while s <= e:
        nxt = min(e, s + pd.DateOffset(years=years) - pd.Timedelta(days=1))
        out.append((s.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        s = nxt + pd.Timedelta(days=1)
    return out


def cache_dir(cache_root: Path, region: str) -> Path:
    d = cache_root / "weather" / region
    d.mkdir(parents=True, exist_ok=True)
    return d


def chunk_path(cdir: Path, zone_id: str, a: str, b: str) -> Path:
    return cdir / f"{zone_id}__{a}_{b}.parquet"


def _scope(reason: str) -> str:
    r = reason.lower()
    for s in ("minutely", "hourly", "daily", "monthly"):
        if s in r:
            return s
    return "unknown"


def fetch_chunk(base_url: str, req: ZoneRequest, a: str, b: str, daily: list[str], timeout: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    """One HTTP request. Raises QuotaExceeded on 429, RuntimeError on other failures."""
    import requests

    params = {"latitude": req.lat, "longitude": req.lon, "start_date": a, "end_date": b,
              "daily": ",".join(daily), "timezone": "auto"}
    r = requests.get(base_url, params=params, timeout=timeout)
    if r.status_code == 429:
        try:
            reason = r.json().get("reason", r.text[:200])
        except ValueError:
            reason = r.text[:200]
        raise QuotaExceeded(_scope(reason), reason)
    if r.status_code != 200:
        raise RuntimeError(f"Open-Meteo HTTP {r.status_code}: {r.text[:300]}")
    try:
        js = r.json()
    except ValueError as e:
        raise RuntimeError(f"Open-Meteo non-JSON body ({len(r.content)} B): {e!r}") from e
    if js.get("error"):
        raise RuntimeError(f"Open-Meteo error: {js.get('reason')}")
    d = pd.DataFrame(js["daily"])
    d["date"] = pd.to_datetime(d.pop("time"))
    meta = {k: v for k, v in js.items() if k not in ("daily",)}
    meta.update(req_lat=req.lat, req_lon=req.lon, start=a, end=b, fetched_utc=dt.datetime.utcnow().isoformat(timespec="seconds"))
    return d, meta


def pending_chunks(cdir: Path, reqs: list[ZoneRequest], years: int) -> list[tuple[ZoneRequest, str, str]]:
    """(request, a, b) still missing from cache, in request order."""
    out = []
    for q in reqs:
        for a, b in chunks(q.start, q.end, years):
            if not chunk_path(cdir, q.zone_id, a, b).exists():
                out.append((q, a, b))
    return out


def run_batch(reqs: list[ZoneRequest], cfg: dict[str, Any], cache_root: Path, budget_s: float,
              max_requests: int | None = None) -> dict[str, Any]:
    """Fetch missing chunks until done, time budget spent, or quota hit. Resumable; paced via a stamp file."""
    w = cfg["weather"]
    region = reqs[0].region if reqs else "?"
    cdir = cache_dir(cache_root, region)
    stamp = cdir.parent / "last_request.txt"
    logf = cdir.parent / "fetch_log.jsonl"
    t0 = time.monotonic()
    todo = pending_chunks(cdir, reqs, w["chunk_years"])
    done, stop, errors = 0, None, 0
    for q, a, b in todo:
        if max_requests is not None and done >= max_requests:
            stop = "max_requests"
            break
        last = float(stamp.read_text()) if stamp.exists() else 0.0
        wait = max(0.0, w["min_interval_s"] - (time.time() - last))
        if time.monotonic() - t0 + wait + 10 > budget_s:
            stop = "time_budget"
            break
        time.sleep(wait)
        stamp.write_text(str(time.time()))
        ts = time.time()
        try:
            d, meta = fetch_chunk(w["base_url"], q, a, b, w["daily"], w["timeout_s"])
        except QuotaExceeded as e:
            _log(logf, dict(zone=q.zone_id, a=a, b=b, status=f"429_{e.scope}", reason=e.reason))
            stop = f"quota_{e.scope}"
            break
        except Exception as e:  # noqa: BLE001  network/decoding: log, leave pending, continue
            _log(logf, dict(zone=q.zone_id, a=a, b=b, status="error", reason=repr(e)[:300]))
            errors += 1
            if errors >= 3:
                stop = "errors"
                break
            continue
        p = chunk_path(cdir, q.zone_id, a, b)
        d.to_parquet(p, index=False)
        p.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        _log(logf, dict(zone=q.zone_id, a=a, b=b, status="ok", days=len(d), secs=round(time.time() - ts, 2)))
        done += 1
    left = len(pending_chunks(cdir, reqs, w["chunk_years"]))
    return {"fetched": done, "remaining": left, "stopped": stop or "complete", "elapsed_s": round(time.monotonic() - t0, 1)}


def _log(path: Path, rec: dict[str, Any]) -> None:
    rec["utc"] = dt.datetime.utcnow().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def load_zone(cache_root: Path, req: ZoneRequest, years: int) -> pd.DataFrame | None:
    """Concatenate cached chunks for a zone; None if any chunk missing."""
    cdir = cache_dir(cache_root, req.region)
    parts = []
    for a, b in chunks(req.start, req.end, years):
        p = chunk_path(cdir, req.zone_id, a, b)
        if not p.exists():
            return None
        parts.append(pd.read_parquet(p))
    d = pd.concat(parts, ignore_index=True).drop_duplicates("date").sort_values("date")
    d.insert(0, "zone_id", req.zone_id)
    return d.reset_index(drop=True)


def zone_meta(cache_root: Path, req: ZoneRequest, years: int) -> dict[str, Any] | None:
    """Metadata (grid lat/lon, elevation, timezone) from the first cached chunk."""
    a, b = chunks(req.start, req.end, years)[0]
    p = chunk_path(cache_dir(cache_root, req.region), req.zone_id, a, b).with_suffix(".json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
