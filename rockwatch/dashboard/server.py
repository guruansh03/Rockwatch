"""RockWatch control-room web UI: stdlib HTTP server (no extra dependencies) over a run's sqlite bus.

Binds 127.0.0.1 only. Reads with reader id 'dashboard' (truth overlay allowed, closed days only).
Writes only operator actions: alerts.ack, agents.control (llm_offline, drop_zone, pause, resume) and
agent kill/restart through the run registry.

    python -m rockwatch ui [--run DIR] [--port 8600]      # or automatically from `run-demo`
"""
from __future__ import annotations

import json
import mimetypes
import os
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from rockwatch.config import REPO_ROOT, load_config, repo_path
from rockwatch.dashboard import data as D
from rockwatch.schemas import Envelope

WEB = Path(__file__).parent / "web"
R = "dashboard"
CONTROL_KINDS = ("llm_offline", "drop_zone", "pause", "resume", "speed")
SPEED_RANGE = (0.75, 4.0)        # wall s per sim-day the operator may pick (agents' watermarks scale with it)


def llm_setup(cfg: dict[str, Any]) -> dict[str, Any]:
    """Which LLM provider the agents of this repo use (same rule as make_provider). Never returns the key."""
    from dotenv import load_dotenv
    load_dotenv(repo_path(".env"))
    name = os.getenv("ROCKWATCH_LLM_PROVIDER", cfg["llm"].get("provider", "mock"))
    out: dict[str, Any] = {"provider": name}
    if name == "anthropic":
        out.update(key_set=bool(os.getenv("ANTHROPIC_API_KEY")),
                   verifier=os.getenv("ROCKWATCH_MODEL_VERIFIER", "claude-haiku-5-5"), writer=os.getenv("ROCKWATCH_MODEL_WRITER", "claude-sonnet-5-5"))
    if name == "groq":
        g = cfg["llm"].get("groq", {})
        out.update(key_set=bool(os.getenv("GROQ_API_KEY", "").strip()),
                   verifier=os.getenv("GROQ_MODEL_VERIFIER", g.get("verifier")), writer=os.getenv("GROQ_MODEL_WRITER", g.get("writer")))
    return out


def _num(x: Any, nd: int = 4) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if x != x else round(x, nd)


class App:
    """API logic, independent of HTTP (unit-tested directly)."""

    def __init__(self, cfg: dict[str, Any], run_dir: Path | None = None):
        self.cfg = cfg
        self.fixed_run = Path(run_dir) if run_dir else None
        self._bus: dict[str, Any] = {}
        self._zones: dict[str, pd.DataFrame] = {}
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ helpers
    def runs(self) -> list[Path]:
        root = repo_path(self.cfg["paths"].get("runs", "data/runs"))
        runs = [p for p in root.glob("*") if (p / "bus.sqlite").exists() and (p / "run.json").exists()]
        return sorted(runs, key=lambda p: (p / "run.json").stat().st_mtime)   # oldest → newest (by start time)

    def run_dir(self, name: str | None) -> Path:
        if name:
            for p in self.runs():
                if p.name == name:
                    return p
            raise FileNotFoundError(f"unknown run {name}")
        if self.fixed_run:
            return self.fixed_run
        r = self.runs()
        if not r:
            raise FileNotFoundError("no runs yet — start one with `python -m rockwatch run-demo --scenario dev_val`")
        return r[-1]

    def bus(self, run: Path):
        from rockwatch.bus.sqlite_bus import SqliteBus
        k = str(run)
        with self.lock:
            if k not in self._bus:
                self._bus[k] = SqliteBus(run / "bus.sqlite")
            return self._bus[k]

    def zones(self, region: str) -> pd.DataFrame:
        if region not in self._zones:
            proc = repo_path(self.cfg["paths"]["processed"]) / region
            z = pd.read_parquet(proc / "zones.parquet")
            bs = proc / "build_summary.json"
            if bs.exists():
                miss = set(json.loads(bs.read_text(encoding="utf-8"))["zones_missing_weather"])
                z = z[~z["zone_id"].isin(miss)]
            self._zones[region] = z.reset_index(drop=True)
        return self._zones[region]

    def thresholds(self, region: str) -> dict[str, Any]:
        p = repo_path(self.cfg["paths"]["processed"]) / region / "models" / "full.json"
        if not p.exists():
            return {}
        m = json.loads(p.read_text(encoding="utf-8"))
        return {k: m["thresholds"].get(k) for k in ("t1", "t2", "t3", "l3_enabled", "rule_t2")}

    # ------------------------------------------------------------------ GET
    def api_runs(self, q: dict[str, str]) -> Any:
        out = []
        for p in self.runs()[::-1]:
            info = D.run_info(p)
            rc = self.cfg["regions"].get(info.get("region"), {})
            out.append({"name": p.name, **info, "finished": (p / "summary.json").exists(),
                        "region_short": rc.get("name", info.get("region", "?")).split(",")[0].split("(")[0].strip()})
        return out

    def api_meta(self, q: dict[str, str]) -> Any:
        run = self.run_dir(q.get("run"))
        info = D.run_info(run)
        rc = self.cfg["regions"][info["region"]]
        z = self.zones(info["region"])
        return {"run": run.name, "info": info, "region": info["region"], "region_name": rc["name"], "deg": self.cfg["zones"]["deg"],
                "single_zone": "single_zone" in rc, "thresholds": self.thresholds(info["region"]), "llm_setup": llm_setup(self.cfg),
                "split_of_run": next((k for k, (a, b) in rc["splits"].items() if a <= info["start"] and info["end"] <= b), "mixed"),
                "days_total": int((pd.Timestamp(info["end"]) - pd.Timestamp(info["start"])).days) + 1,
                "banner": self.cfg["eval"]["banner"], "renotify_days": self.cfg["agents"].get("ack_renotify_days", 2),
                "zones": [{"zone_id": r.zone_id, "lat": float(r.lat), "lon": float(r.lon), "kind": r.kind,
                           "n_prior": int(r.n_prior_features)} for r in z.itertuples()]}

    def api_state(self, q: dict[str, str]) -> Any:
        run = self.run_dir(q.get("run"))
        b = self.bus(run)
        info = D.run_info(run)
        latest = D.latest_state(b)
        view = q.get("day")
        st = (b.read(R, ["alerts.active"], kind="daily_state", sim_date=view, latest=True) or [latest])[0] if view else latest
        clk = b.read(R, ["sim.clock"], kind="tick", latest=True)
        ctl = b.read(R, ["agents.control"])
        pr = [e for e in ctl if e.kind in ("pause", "resume")]
        paused = bool(pr) and pr[-1].kind == "pause"
        off = [e for e in ctl if e.kind == "llm_offline"]
        drops: dict[str, bool] = {}
        for e in ctl:
            if e.kind == "drop_zone":
                drops[e.payload["zone_id"]] = bool(e.payload.get("on", True))
        ended = bool(b.read(R, ["sim.clock"], kind="end", latest=True))
        stopped = any(e.kind == "stop" for e in ctl)
        day = st.sim_date if st else None
        live = b.read(R, ["eval.live"], sim_date=view, latest=True) if view else b.read(R, ["eval.live"], latest=True)
        sp = [e for e in ctl if e.kind == "speed"]
        last_call = b.read(R, ["llm.calls"], latest=True)
        levels = {k: int(v) for k, v in (st.payload["levels"] if st else {}).items()}
        status = "finished" if (ended or stopped) else ("paused" if paused else ("live" if clk else "starting"))
        return {"run": run.name, "status": status, "day": day, "tick_day": clk[0].sim_date if clk else None,
                "day_index": (pd.Timestamp(day) - pd.Timestamp(info["start"])).days + 1 if day else 0,
                "levels": levels, "p": {k: _num(v) for k, v in (st.payload.get("p", {}) if st else {}).items()},
                "unacked": st.payload.get("unacked", []) if st else [], "episodes": st.payload.get("episodes", {}) if st else {},
                "n_l1": sum(v == 1 for v in levels.values()), "n_l2": sum(v >= 2 for v in levels.values()),
                "n_l3": sum(v >= 3 for v in levels.values()), "degraded": D.degraded_today(b, day), "stale": D.stale_agents(b),
                "llm_calls": len(b.read(R, ["llm.calls"])), "llm_offline": bool(off) and bool(off[-1].payload.get("on")),
                "dropped": sorted(z for z, on in drops.items() if on),
                "live_eval": {k: (_num(v) if isinstance(v, float) else v) for k, v in live[0].payload.items()} if live else None,
                "seq": latest.seq if latest else 0, "view": view, "latest_day": latest.sim_date if latest else None,
                "speed": float(sp[-1].payload["s"]) if sp else float(info.get("speed", 1.5)), "launch_speed": float(info.get("speed", 1.5)),
                "llm_model_seen": last_call[0].payload.get("model") if last_call else None,
                "llm_provider_seen": last_call[0].payload.get("provider") if last_call else None}

    def api_history(self, q: dict[str, str]) -> Any:
        run = self.run_dir(q.get("run"))
        b = self.bus(run)
        truth = D.truth_counts(b)
        out = []
        for e in b.read(R, ["alerts.active"], kind="daily_state"):
            lv = list(e.payload["levels"].values())
            ps = [v for v in (e.payload.get("p") or {}).values() if v is not None]
            out.append({"day": e.sim_date, "l0": sum(v == 0 for v in lv), "l1": sum(v == 1 for v in lv), "l2": sum(v == 2 for v in lv),
                        "l3": sum(v == 3 for v in lv), "n": len(lv), "max": max(lv) if lv else 0,
                        "pmax": _num(max(ps)) if ps else None, "truth": truth.get(e.sim_date)})
        return out

    def api_zone(self, q: dict[str, str]) -> Any:
        run = self.run_dir(q.get("run"))
        b = self.bus(run)
        z = q["zone"]
        df = D.zone_series(b, z)
        rows = []
        for r in df.to_dict("records"):
            rows.append({k: (v.strftime("%Y-%m-%d") if k == "date" else (v if isinstance(v, str) else _num(v))) for k, v in r.items()})
        view = q.get("day")
        last = next((r for r in reversed(rows) if r.get("p") is not None and (not view or r["date"] <= view)), None)
        feats: dict[str, Any] = {}
        if last:
            for e in b.read(R, ["evidence.rain", "evidence.thermal", "evidence.seismic", "evidence.susceptibility"], zone_id=z, sim_date=last["date"]):
                feats[e.payload["group"]] = {"features": {k: _num(v) for k, v in e.payload["features"].items()},
                                             "contribution": _num(e.payload["contribution"]), "quality": e.quality}
            cx = b.read(R, ["evidence.context"], sim_date=last["date"], latest=True)
            if cx:
                feats["context"] = {"features": {k: _num(v) for k, v in cx[0].payload["features"].items()},
                                    "contribution": _num(cx[0].payload["contribution"]), "quality": cx[0].quality}
        ver = b.read(R, ["risk.verified"], zone_id=z, sim_date=last["date"], latest=True) if last else []
        return {"zone": z, "series": rows, "last": last, "evidence": feats,
                "verifier": ver[0].payload.get("verifier") if ver else None, "quality": ver[0].payload.get("quality") if ver else None}

    def api_alerts(self, q: dict[str, str]) -> Any:
        run = self.run_dir(q.get("run"))
        out = []
        for a in D.alerts_feed(self.bus(run), limit=int(q.get("limit", 40))):
            pl, m, v = a["payload"], a["message"], a["verifier"]
            out.append({"seq": a["seq"], "date": a["date"], "zone": a["zone_id"], "kind": a["kind"], "from": pl.get("from"),
                        "to": pl.get("to", pl.get("level")), "p": _num(pl.get("p")), "episode_id": pl.get("episode_id"),
                        "contributions": {k: _num(x, 3) for k, x in (pl.get("contributions") or {}).items()},
                        "message": {k: m.get(k) for k in ("headline", "body", "actions", "source")} if m else None,
                        "verifier": {k: v.get(k) for k in ("decision", "verifier", "mode", "level_in", "level_out", "rationale",
                                                           "confidence", "l3_corroborated_by_llm")} if v else None})
        return out

    def api_agents(self, q: dict[str, str]) -> Any:
        b = self.bus(self.run_dir(q.get("run")))
        t = D.agent_table(b)
        llm = D.llm_log(b, 40)
        return {"agents": json.loads(t.to_json(orient="records")), "llm": json.loads(llm.to_json(orient="records"))}

    def api_truth(self, q: dict[str, str]) -> Any:
        run = self.run_dir(q.get("run"))
        info = D.run_info(run)
        st = D.latest_state(self.bus(run))
        upto = q.get("day") or (st.sim_date if st else None)
        tm = D.truth_markers(self.bus(run), upto, int(q.get("days", 14)), self.zones(info["region"]))
        return [{"zone": r.zone_id, "date": r.date, "type": r.type, "lat": _num(r.lat), "lon": _num(r.lon)} for r in tm.itertuples()]

    def api_reports(self, q: dict[str, str]) -> Any:
        out = []
        for p in sorted(repo_path(self.cfg["paths"]["reports"]).glob("eval_*"))[::-1]:
            if not (p / "metrics.json").exists():
                continue
            m = json.loads((p / "metrics.json").read_text(encoding="utf-8"))
            out.append({"name": p.name, "region": m["region"], "split": m["split"], "llm": m.get("llm_verifier"),
                        "partial": bool((m.get("data_coverage") or {}).get("partial")), "generated": m.get("generated")})
        return out

    def api_report(self, q: dict[str, str]) -> Any:
        name = Path(q["name"]).name
        p = repo_path(self.cfg["paths"]["reports"]) / name
        m = json.loads((p / "metrics.json").read_text(encoding="utf-8"))
        return {"name": name, "metrics": m, "images": [f"/reports/{name}/{f}" for f in ("pr_curve.png", "lead_days.png") if (p / f).exists()]}

    # ------------------------------------------------------------------ POST
    def post_ack(self, body: dict[str, Any]) -> Any:
        b = self.bus(self.run_dir(body.get("run")))
        st = D.latest_state(b)
        z = body["zone"]
        ep = (st.payload.get("episodes", {}) if st else {}).get(z)
        if not ep:
            return {"ok": False, "error": "no open L2+ episode in this zone"}
        b.publish(Envelope(topic="alerts.ack", agent_id="dashboard", zone_id=z, sim_date=st.sim_date,
                           payload={"episode_id": ep["id"], "by": body.get("by", "operator")}))
        return {"ok": True, "episode_id": ep["id"]}

    def post_control(self, body: dict[str, Any]) -> Any:
        kind = body.get("kind")
        if kind not in CONTROL_KINDS:
            return {"ok": False, "error": f"unknown control {kind}"}
        if kind == "speed":
            try:
                v = float((body.get("payload") or {}).get("s"))
            except (TypeError, ValueError):
                return {"ok": False, "error": "speed needs payload.s (wall seconds per sim-day)"}
            if not SPEED_RANGE[0] <= v <= SPEED_RANGE[1]:
                return {"ok": False, "error": f"speed must be within {SPEED_RANGE[0]}–{SPEED_RANGE[1]} s/day"}
            body = {**body, "payload": {"s": v}}
        self.bus(self.run_dir(body.get("run"))).publish(
            Envelope(topic="agents.control", agent_id="dashboard", kind=kind, payload=body.get("payload") or {}))
        return {"ok": True}

    def post_agent(self, body: dict[str, Any]) -> Any:
        b = self.bus(self.run_dir(body.get("run")))
        reg = {r["agent_id"]: r for r in b.registry()}
        a = body.get("agent")
        if a not in reg:
            return {"ok": False, "error": f"unknown agent {a}"}
        if body.get("action") == "kill":
            try:
                os.kill(reg[a]["pid"], signal.SIGTERM)
            except (ProcessLookupError, OSError) as e:
                return {"ok": False, "error": f"kill failed: {e}"}
            return {"ok": True}
        if body.get("action") == "restart":
            p = subprocess.Popen(reg[a]["cmd"], cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            b.bump_restart(a, p.pid)
            b.publish(Envelope(topic="quality.flags", agent_id="dashboard", kind="agent_restarted", payload={"agent_id": a, "new_pid": p.pid}))
            return {"ok": True, "pid": p.pid}
        return {"ok": False, "error": "unknown action"}

    def post_ask(self, body: dict[str, Any]) -> Any:
        from rockwatch.agents.llm_analyst import AnalystStore, answer
        from rockwatch.llm.runtime import LLMRuntime
        b = self.bus(self.run_dir(body.get("run")))
        q = str(body.get("question", "")).strip()[:500]
        if not q:
            return {"answer": "Ask a question about this run's alerts, zones or metrics.", "citations": [], "source": "empty"}
        warn = None
        rt = None
        if body.get("llm"):
            try:
                rt = LLMRuntime(self.cfg, "writer")
            except Exception as e:  # noqa: BLE001
                warn = f"LLM unavailable ({type(e).__name__}); answered from records only"
        a = answer(rt, AnalystStore(b, self.cfg), q)
        out = {k: a.get(k) for k in ("answer", "citations", "source")}
        if warn:
            out["warning"] = warn
        return out


GET_ROUTES = {"/api/runs": "api_runs", "/api/meta": "api_meta", "/api/state": "api_state", "/api/history": "api_history",
              "/api/zone": "api_zone", "/api/alerts": "api_alerts", "/api/agents": "api_agents", "/api/truth": "api_truth",
              "/api/reports": "api_reports", "/api/report": "api_report"}
POST_ROUTES = {"/api/ack": "post_ack", "/api/control": "post_control", "/api/agent": "post_agent", "/api/ask": "post_ask"}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RockWatch/1.0"

        def log_message(self, *a: Any) -> None:  # keep the console quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str, cache: bool = False) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=600" if cache else "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, code: int = 200) -> None:
            self._send(code, json.dumps(obj, default=str).encode("utf-8"), "application/json; charset=utf-8")

        def _file(self, root: Path, rel: str, cache: bool) -> bool:
            f = (root / unquote(rel)).resolve()
            if root.resolve() in f.parents and f.is_file():
                ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype.endswith("javascript"):
                    ctype += "; charset=utf-8"
                self._send(200, f.read_bytes(), ctype, cache)
                return True
            return False

        def do_GET(self) -> None:  # noqa: N802
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path in GET_ROUTES:
                    return self._json(getattr(app, GET_ROUTES[u.path])(q))
                if u.path in ("/", "/index.html"):
                    return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
                if u.path.startswith("/static/") and self._file(WEB, u.path[len("/static/"):], cache=False):
                    return
                if u.path.startswith("/reports/") and u.path.endswith((".png", ".md", ".json")) and \
                        self._file(repo_path(app.cfg["paths"]["reports"]), u.path[len("/reports/"):], cache=True):
                    return
                self._json({"error": "not found"}, 404)
            except FileNotFoundError as e:
                self._json({"error": str(e)}, 404)
            except Exception as e:  # noqa: BLE001
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_POST(self) -> None:  # noqa: N802
            u = urlparse(self.path)
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                if u.path in POST_ROUTES:
                    return self._json(getattr(app, POST_ROUTES[u.path])(body))
                self._json({"error": "not found"}, 404)
            except Exception as e:  # noqa: BLE001
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
    return Handler


def serve(cfg: dict[str, Any] | None = None, run_dir: Path | None = None, port: int = 8600, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), make_handler(App(cfg or load_config(), run_dir)))
    srv.daemon_threads = True
    return srv


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rockwatch ui")
    ap.add_argument("--run", default=None, help="run directory (default: latest; switchable in the UI)")
    ap.add_argument("--port", type=int, default=8600)
    a = ap.parse_args(argv)
    srv = serve(run_dir=Path(a.run) if a.run else None, port=a.port)
    print(f"RockWatch control room: http://localhost:{a.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
