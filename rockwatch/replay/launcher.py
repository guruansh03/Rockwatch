"""run-demo launcher: one OS process per agent (sqlite bus), replay engine in the foreground, fault injection,
clean shutdown, run summary. Cross-platform (subprocess + sys.executable; no shell scripts)."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from rockwatch.agents.base import AgentContext
from rockwatch.agents.run import agent_specs
from rockwatch.config import REPO_ROOT, repo_path
from rockwatch.replay.engine import Engine
from rockwatch.replay.scenarios import resolve
from rockwatch.schemas import Envelope


def runs_root(cfg) -> Path:
    return repo_path(cfg["paths"].get("runs", "data/runs"))


def latest_run(cfg) -> Path | None:
    r = [p for p in runs_root(cfg).glob("*") if (p / "bus.sqlite").exists() and (p / "run.json").exists()]
    return max(r, key=lambda p: (p / "run.json").stat().st_mtime) if r else None


def heartbeats(bus) -> dict[str, float]:
    """agent_id → wall_ts of latest heartbeat."""
    last: dict[str, float] = {}
    for e in bus.read("launcher", ["agents.heartbeat"]):
        last[e.agent_id] = e.wall_ts
    return last


def launch(cfg: dict[str, Any], scenario: str, speed: float, days: int | None = None, kill: tuple[str, int] | None = None,
           auto_restart: set[str] | None = None, log=print, llm: str = "off", dashboard: bool = False, port: int = 8600,
           keep_open: bool = True, ui: str = "web", open_browser: bool = True) -> dict[str, Any]:
    from rockwatch.bus.sqlite_bus import SqliteBus
    from rockwatch.agents.evaluator import recompute_from_log

    region, start, end = resolve(cfg, scenario, days)
    run_dir = runs_root(cfg) / f"{scenario}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(dict(scenario=scenario, region=region, start=start, end=end, speed=speed, llm=llm)), encoding="utf-8")
    bus = SqliteBus(run_dir / "bus.sqlite")
    ctx = AgentContext(cfg, region, start, end, speed)
    procs: dict[str, subprocess.Popen] = {}
    auto_restart = auto_restart or set()
    for aid, _, _ in agent_specs(cfg):
        cmd = [sys.executable, "-m", "rockwatch.agents.run", "--agent", aid, "--run-dir", str(run_dir), "--region", region,
               "--start", start, "--end", end, "--speed", str(speed), "--llm", llm]
        p = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=open(run_dir / f"{aid}.stderr", "w"))
        procs[aid] = p
        bus.register(aid, cmd, p.pid, aid in auto_restart)
    log(f"run dir: {run_dir}  ({len(procs)} agent processes)")
    t0 = time.time()
    while time.time() - t0 < 120:
        hb = heartbeats(bus)
        if all(a in hb for a in procs):
            break
        dead = [a for a, p in procs.items() if p.poll() is not None]
        if dead:
            raise RuntimeError(f"agents died at startup: {dead} (see {run_dir}/*.stderr)")
        time.sleep(0.5)
    else:
        raise RuntimeError("agents not ready after 120 s")
    log(f"all agents up in {time.time() - t0:.1f}s; replaying {start} → {end} at {speed}s/day")
    dash = None
    if dashboard:
        import os
        import webbrowser
        env = {**os.environ, "ROCKWATCH_RUN_DIR": str(run_dir)}
        if ui == "streamlit":
            cmd = [sys.executable, "-m", "streamlit", "run", str(REPO_ROOT / "rockwatch" / "dashboard" / "app.py"),
                   "--server.headless", "true", "--server.port", str(port), "--browser.gatherUsageStats", "false"]
        else:
            cmd = [sys.executable, "-m", "rockwatch.dashboard.server", "--run", str(run_dir), "--port", str(port)]
        dash = subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env, stdout=open(run_dir / "dashboard.log", "w"), stderr=subprocess.STDOUT)
        url = f"http://localhost:{port}/?run={run_dir.name}"
        log(f"control room: {url}")
        time.sleep(2.5)
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                pass
    eng = Engine(ctx, bus)

    def on_day(i, d):
        if kill and i == kill[1] and kill[0] in procs:
            procs[kill[0]].terminate()
            log(f"[fault] killed {kill[0]} at sim-day {i} ({d})")
        if i % 10 == 0:
            log(f"  sim-day {i:3d} {d}")
    eng.run(on_day)
    last = eng.days[-1]
    t1 = time.time()
    while time.time() - t1 < 10 * speed + 5:
        if bus.read("launcher", ["alerts.active"], kind="daily_state", latest=True)[0:1] and \
                bus.read("launcher", ["alerts.active"], kind="daily_state", latest=True)[0].sim_date == last:
            break
        time.sleep(0.3)
    time.sleep(max(2.5, 2 * speed))   # let supervisor/evaluator flush
    summary = summarize(bus, eng.days)
    summary["offline_eval"] = {k: v for k, v in recompute_from_log(bus).items() if k != "lead_days"}
    summary["run_dir"] = str(run_dir)
    bus.publish(Envelope(topic="agents.control", agent_id="launcher", kind="stop", payload={"target": None}))
    for p in procs.values():
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.terminate()
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    if dash is not None:
        if keep_open:
            log("replay finished — dashboard stays up for review; press Ctrl+C to exit")
            try:
                dash.wait()
            except KeyboardInterrupt:
                pass
        dash.terminate()
    return summary


def summarize(bus, days: list[str]) -> dict[str, Any]:
    ev = bus.read("launcher", ["risk.fused", "risk.verified", "alerts.active", "quality.flags", "evidence.rain", "eval.live", "llm.calls"])
    c = Counter((e.topic, e.kind) for e in ev)
    states = [e for e in ev if e.topic == "alerts.active" and e.kind == "daily_state"]
    lv = Counter(v for e in states for v in e.payload["levels"].values())
    stale = [e.payload for e in ev if e.topic == "quality.flags" and e.kind in ("agent_stale", "agent_recovered", "agent_restarted")]
    degraded_days = sorted({e.sim_date for e in ev if e.topic == "risk.fused" and e.quality != "ok"})
    live = [e.payload for e in ev if e.topic == "eval.live"]
    return {"sim_days": len(days), "days_with_daily_state": len(states), "fused_msgs": c[("risk.fused", "data")],
            "message_counts": {f"{t}/{k}": n for (t, k), n in sorted(c.items())},
            "active_level_zone_days": {f"L{k}": v for k, v in sorted(lv.items())},
            "supervisor_flags": stale, "degraded_fused_days": [degraded_days[0], degraded_days[-1], len(degraded_days)] if degraded_days else [],
            "eval_live_last": live[-1] if live else None,
            "llm": {"calls": c[("llm.calls", "verifier")] + c[("llm.calls", "composer")],
                    "outcomes": dict(Counter(e.payload.get("outcome") for e in ev if e.topic == "llm.calls")),
                    "verifier_decisions": dict(Counter(e.payload["verifier"].get("decision") for e in ev if e.topic == "risk.verified")),
                    "messages_composed": c[("alerts.active", "message")]}}
