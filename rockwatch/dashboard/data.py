"""Pure read helpers for the dashboard (testable without Streamlit). Reader id 'dashboard' (truth overlay allowed)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from rockwatch.schemas import Envelope

R = "dashboard"
LEVEL_COLORS = {0: [46, 160, 67, 90], 1: [240, 200, 40, 150], 2: [245, 130, 30, 190], 3: [220, 40, 40, 220]}
LEVEL_NAMES = {0: "L0 Normal", 1: "L1 Watch", 2: "L2 Warning", 3: "L3 Alarm"}


def run_info(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def latest_state(bus) -> Envelope | None:
    s = bus.read(R, ["alerts.active"], kind="daily_state", latest=True)
    return s[0] if s else None


def zone_table(zones: pd.DataFrame, state: Envelope | None, deg: float) -> pd.DataFrame:
    z = zones[["zone_id", "lat", "lon", "kind", "n_prior_features"]].copy()
    lv = state.payload["levels"] if state else {}
    pp = state.payload.get("p", {}) if state else {}
    z["level"] = z["zone_id"].map(lambda x: int(lv.get(x, 0)))
    z["p"] = z["zone_id"].map(lambda x: pp.get(x))
    z["color"] = z["level"].map(LEVEL_COLORS)
    h = deg / 2
    z["polygon"] = [[[lo - h, la - h], [lo + h, la - h], [lo + h, la + h], [lo - h, la + h]] for la, lo in zip(z["lat"], z["lon"])]
    z["label"] = z["level"].map(LEVEL_NAMES)
    return z


def truth_markers(bus, upto: str | None, days: int, zones: pd.DataFrame) -> pd.DataFrame:
    """Ground-truth overlay: events of CLOSED days only (published after day close), last `days`."""
    if not upto:
        return pd.DataFrame(columns=["zone_id", "date", "lat", "lon"])
    d0 = (pd.Timestamp(upto) - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    ev = bus.read(R, ["truth.events"], kind="day_close", date_from=d0)
    rows = [{"zone_id": x["zone_id"], "date": e.sim_date, "type": x.get("type_family")} for e in ev if e.sim_date <= upto for x in e.payload["events"]]
    df = pd.DataFrame(rows, columns=["zone_id", "date", "type"])
    return df.merge(zones[["zone_id", "lat", "lon"]], on="zone_id", how="left")


def truth_counts(bus) -> dict[str, int]:
    """Reported events per CLOSED sim-day (overlay only; agents never read this)."""
    return {e.sim_date: len(e.payload["events"]) for e in bus.read(R, ["truth.events"], kind="day_close")}


def zone_series(bus, zone_id: str) -> pd.DataFrame:
    """Per-day rain features, contributions, p, level for one zone."""
    er = {e.sim_date: e for e in bus.read(R, ["evidence.rain"], zone_id=zone_id)}
    fz = {e.sim_date: e for e in bus.read(R, ["risk.verified"], zone_id=zone_id)}
    rows = []
    for d in sorted(set(er) | set(fz)):
        f = er[d].payload["features"] if d in er else {}
        v = fz.get(d)
        r = {"date": pd.Timestamp(d), "P1": f.get("P1"), "P3": f.get("P3"), "P15": f.get("P15"),
             "p": v.payload["p"] if v else None, "level": v.payload["verifier"]["level_out"] if v else None,
             "rain_quality": er[d].quality if d in er else "missing"}
        if v:
            r.update({f"c_{k}": x for k, x in v.payload["contributions"].items()})
        rows.append(r)
    df = pd.DataFrame(rows)
    if len(df) and df["P15"].notna().any():
        # USGS Seattle cumulative threshold expressed as the P3 (mm) needed given P15: P3_in = 3.5 − 0.67·P15_in
        df["seattle_P3_threshold_mm"] = (3.5 - 0.67 * (df["P15"] / 25.4)) * 25.4
    return df


def alerts_feed(bus, limit: int = 60) -> list[dict[str, Any]]:
    ev = bus.read(R, ["alerts.active"])
    msgs = {(e.zone_id, e.sim_date): e.payload for e in ev if e.kind == "message"}
    out = []
    for e in ev:
        if e.kind not in ("escalate", "deescalate", "renotify"):
            continue
        ver = bus.read(R, ["risk.verified"], zone_id=e.zone_id, sim_date=e.sim_date, latest=True)
        out.append({"seq": e.seq, "date": e.sim_date, "zone_id": e.zone_id, "kind": e.kind, "payload": e.payload,
                    "message": msgs.get((e.zone_id, e.sim_date)), "verifier": ver[0].payload.get("verifier") if ver else None})
    return out[-limit:][::-1]


def agent_table(bus) -> pd.DataFrame:
    hb: dict[str, float] = {}
    for e in bus.read(R, ["agents.heartbeat"]):
        hb[e.agent_id] = e.wall_ts
    flags: dict[str, str] = {}
    for e in bus.read(R, ["quality.flags"]):
        if e.kind in ("agent_stale", "agent_recovered", "agent_restarted"):
            flags[e.payload["agent_id"]] = e.kind
    reg = bus.registry() if hasattr(bus, "registry") else []
    now = time.time()
    return pd.DataFrame([{"agent": r["agent_id"], "pid": r["pid"], "restarts": r["restarts"],
                          "last_heartbeat_s": round(now - hb[r["agent_id"]], 1) if r["agent_id"] in hb else None,
                          "supervisor": {"agent_stale": "STALE", "agent_recovered": "recovered", "agent_restarted": "restarted"}.get(flags.get(r["agent_id"]), "ok")}
                         for r in reg])


def stale_agents(bus) -> list[str]:
    st: dict[str, bool] = {}
    for e in bus.read(R, ["quality.flags"]):
        if e.kind == "agent_stale":
            st[e.payload["agent_id"]] = True
        elif e.kind in ("agent_recovered", "agent_restarted"):
            st[e.payload["agent_id"]] = False
    return sorted(a for a, v in st.items() if v)


def degraded_today(bus, day: str | None) -> int:
    if not day:
        return 0
    return sum(1 for e in bus.read(R, ["risk.fused"], sim_date=day) if e.quality != "ok")


def llm_log(bus, limit: int = 50) -> pd.DataFrame:
    ev = bus.read(R, ["llm.calls"])[-limit:]
    return pd.DataFrame([{"date": e.sim_date, "zone": e.zone_id, "task": e.payload.get("task"), "model": e.payload.get("model"),
                          "outcome": e.payload.get("outcome"), "cached": e.payload.get("cached"), "in_tok": e.payload.get("input_tokens"),
                          "out_tok": e.payload.get("output_tokens"), "latency_s": e.payload.get("latency_s"),
                          "violations": "; ".join(e.payload.get("violations", []))} for e in ev][::-1])
