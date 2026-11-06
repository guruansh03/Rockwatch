"""RockWatch CLI (cross-platform; no shell scripts). `rockwatch <cmd>` or `python -m rockwatch <cmd>`."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rockwatch.config import load_config, repo_path

log = logging.getLogger("rockwatch")


def cmd_fetch_inventory(cfg: dict, args: argparse.Namespace) -> int:
    """Download USGS v3 CSV (+ optional Yosemite DS746)."""
    from rockwatch.data.usgs_inventory import InventoryFetchError, fetch_inventory
    from rockwatch.data.yosemite import fetch_yosemite

    raw = repo_path(cfg["inventory"]["raw_dir"])
    try:
        p = fetch_inventory(cfg["inventory"]["sciencebase_item"], raw)
        print(f"inventory: {p}")
    except InventoryFetchError as e:
        print(f"STOP: {e}\nManually download 'US_Landslide_v3_csv' from "
              f"https://doi.org/10.5066/P14AJF8I into {raw}", file=sys.stderr)
        return 2
    if args.yosemite:
        y = fetch_yosemite(cfg["yosemite"]["index_url"], repo_path(cfg["yosemite"]["raw_dir"]))
        print(f"yosemite: {y or 'skipped (see log)'}")
    return 0


def cmd_profile(cfg: dict, args: argparse.Namespace) -> int:
    """Clean inventory, write data/interim/inventory_clean.parquet and docs/data_profile.md."""
    from rockwatch.data.profiling import profile
    from rockwatch.data.usgs_inventory import clean_inventory, find_raw_file, load_raw

    raw_dir = repo_path(cfg["inventory"]["raw_dir"])
    src = find_raw_file(raw_dir)
    if src is None:
        print(f"STOP: no inventory CSV/zip in {raw_dir}. Run `rockwatch fetch-inventory` or place "
              "US_Landslide_v3_csv there.", file=sys.stderr)
        return 2
    df = load_raw(src)
    clean, rep = clean_inventory(df, cfg)
    interim = repo_path(cfg["paths"]["interim"])
    interim.mkdir(parents=True, exist_ok=True)
    clean.drop(columns=["Notes"], errors="ignore").to_parquet(interim / "inventory_clean.parquet", index=False)
    md, summary = profile(clean, rep, cfg, src.name)
    docs = repo_path(cfg["paths"]["docs"])
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "data_profile.md").write_text(md, encoding="utf-8")
    (interim / "profile_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    yx = repo_path(cfg["yosemite"]["raw_dir"])
    xl = sorted(yx.glob("*.xlsx"))
    if xl:
        from rockwatch.data.yosemite import load_yosemite, yosemite_profile_md
        y = load_yosemite(xl[0])
        with (docs / "data_profile.md").open("a", encoding="utf-8") as fh:
            fh.write(yosemite_profile_md(y, cfg["inventory"]["min_year"]))
    print(f"wrote {docs / 'data_profile.md'}")
    return 0


def cmd_build_zones(cfg: dict, args: argparse.Namespace) -> int:
    """Write data/processed/<region>/zones.parquet."""
    import pandas as pd
    from rockwatch.data.zones import build_region_zones

    inv = pd.read_parquet(repo_path(cfg["paths"]["interim"]) / "inventory_clean.parquet")
    for region in args.regions:
        z = build_region_zones(cfg, region, inv)
        out = repo_path(cfg["paths"]["processed"]) / region
        out.mkdir(parents=True, exist_ok=True)
        z.to_parquet(out / "zones.parquet", index=False)
        print(f"{region}: {len(z)} zones {z['kind'].value_counts().to_dict()}")
    return 0


def _zone_requests(cfg: dict, region: str):
    import pandas as pd
    from rockwatch.data.weather import ZoneRequest
    from rockwatch.data.zones import weather_range

    z = pd.read_parquet(repo_path(cfg["paths"]["processed"]) / region / "zones.parquet")
    a, b = weather_range(cfg["regions"][region], cfg["zones"]["antecedent_days"])
    return [ZoneRequest(region, r.zone_id, float(r.lat), float(r.lon), a, b) for r in z.itertuples()]


def cmd_fetch_weather(cfg: dict, args: argparse.Namespace) -> int:
    """Budgeted, resumable Open-Meteo fetch. Exit 0 complete, 10 partial (re-run later)."""
    from rockwatch.data.weather import run_batch

    reqs = [q for r in args.regions for q in _zone_requests(cfg, r)]
    res = run_batch(reqs, cfg, repo_path(cfg["paths"]["cache"]), args.budget_s, args.max_requests)
    print(json.dumps(res))
    return 0 if res["remaining"] == 0 else 10


def cmd_build_data(cfg: dict, args: argparse.Namespace) -> int:
    """Features + labels + splits for each region (weather must be cached; see fetch-weather)."""
    from rockwatch.data.build import build_region

    for r in args.regions:
        s = build_region(cfg, r, allow_partial=args.allow_partial)
        print(json.dumps({k: s[k] for k in ("region", "zones_total", "panel_rows", "by_split")}, default=str))
        print(f"{r}: missing weather zones = {len(s['zones_missing_weather'])}")
    from rockwatch.data.build import write_data_card
    print(f"wrote {write_data_card(cfg, args.regions)}")
    return 0


def cmd_train(cfg: dict, args: argparse.Namespace) -> int:
    """Fit fusion + ablations, Platt on val, thresholds on val. Saves processed/<region>/models/*.json."""
    from rockwatch.eval.runner import load_inputs, train_models

    for r in args.regions:
        P, short = load_inputs(cfg, r)
        ms = train_models(cfg, r, P, short)
        th = ms["full"].thresholds
        print(f"{r}: full C={ms['full'].C} val_AP={ms['full'].train_info['val_ap']:.4f} "
              f"t1={th['t1']:.4f} t2={th['t2']:.4f} t3={th['t3']} L3={th['l3_enabled']}")
    return 0


def _existing_test_reports(cfg: dict, region: str) -> list:
    rep = repo_path(cfg["paths"]["reports"])
    return sorted(p for p in rep.glob(f"eval_*_{region}_test") if (p / "metrics.json").exists())


def cmd_eval(cfg: dict, args: argparse.Namespace) -> int:
    """Evaluate a split. Test only with --final (once; rerun needs --force-rerun-with-reason)."""
    import datetime as dt
    from rockwatch.eval.report import write_report
    from rockwatch.eval.runner import evaluate, git_hash

    for r in args.regions:
        if args.split == "test":
            if not args.final:
                print("REFUSED: the test split is evaluated only via `eval --split test --final` after CP2.", file=sys.stderr)
                return 4
            bs = repo_path(cfg["paths"]["processed"]) / r / "build_summary.json"
            miss = json.loads(bs.read_text(encoding="utf-8")).get("zones_missing_weather", []) if bs.exists() else ["no build_summary"]
            if miss:
                print(f"REFUSED: {r} data is partial ({len(miss)} zones without weather). Finish fetch-weather + build-data + train first.",
                      file=sys.stderr)
                return 4
            prev = _existing_test_reports(cfg, r)
            if prev and not args.force_rerun_with_reason:
                print(f"REFUSED: test metrics already exist ({prev[-1].name}). Use --force-rerun-with-reason.", file=sys.stderr)
                return 4
            log = repo_path(cfg["paths"]["reports"]) / "final_runs.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(f"{dt.datetime.now().isoformat()} region={r} git={git_hash()} reason={args.force_rerun_with_reason or 'first final run'}\n")
        res = evaluate(cfg, r, args.split, retrain=args.retrain, llm=args.llm == "on")
        out = write_report(res, cfg, git_hash(), res.get("llm_usage"))
        m = res["rockwatch"]
        print(f"{r}/{args.split}: recall_before={m['recall_before']} recall_at={m['recall_at']} "
              f"prec_ep={m['precision_episode']} f1={m['f1_at']} alert_frac={m['alert_day_fraction']} -> {out}")
    return 0


def cmd_run_demo(cfg: dict, args: argparse.Namespace) -> int:
    """Spawn all agent processes + replay engine (dashboard added in Phase 5; --headless prints a summary)."""
    if args.bus == "redis":
        print("Redis backend cut (cut list #1); use --bus sqlite", file=sys.stderr)
        return 3
    if args.bus == "memory":
        from rockwatch.agents.base import AgentContext
        from rockwatch.agents.run import build
        from rockwatch.bus.memory import MemoryBus
        from rockwatch.replay.engine import run_local
        from rockwatch.replay.scenarios import resolve
        region, start, end = resolve(cfg, args.scenario, args.days)
        ctx = AgentContext(cfg, region, start, end, args.speed, params={"llm": args.llm})
        bus = MemoryBus()
        run_local(ctx, bus, build(ctx, bus))
        print(f"memory bus (in-process, deterministic): {len(bus.log)} messages over {region} {start}→{end}")
        return 0
    from rockwatch.replay.launcher import launch
    kill = (args.kill_agent, args.kill_at_day) if args.kill_agent else None
    s = launch(cfg, args.scenario, args.speed, args.days, kill, set(args.auto_restart or []), llm=args.llm,
               dashboard=not args.headless, port=args.port, keep_open=not args.no_wait, ui=args.ui,
               open_browser=not args.no_browser)
    print(json.dumps({k: s[k] for k in ("sim_days", "days_with_daily_state", "fused_msgs", "active_level_zone_days",
                                         "supervisor_flags", "degraded_fused_days", "eval_live_last", "offline_eval", "llm", "run_dir")},
                     indent=1, default=str))
    return 0 if s["days_with_daily_state"] == s["sim_days"] else 5


def cmd_agents(cfg: dict, args: argparse.Namespace) -> int:
    """agents status | kill <agent_id>  (latest run unless --run)."""
    import os
    import signal
    import time
    from pathlib import Path
    from rockwatch.bus.sqlite_bus import SqliteBus
    from rockwatch.replay.launcher import heartbeats, latest_run

    run = Path(args.run) if args.run else latest_run(cfg)
    if run is None:
        print("no runs found", file=sys.stderr)
        return 2
    bus = SqliteBus(run / "bus.sqlite")
    if args.action == "kill":
        reg = {r["agent_id"]: r for r in bus.registry()}
        if args.target not in reg:
            print(f"unknown agent {args.target}", file=sys.stderr)
            return 2
        os.kill(reg[args.target]["pid"], signal.SIGTERM)
        print(f"killed {args.target} (pid {reg[args.target]['pid']})")
        return 0
    hb = heartbeats(bus)
    flags = {}
    for e in bus.read("cli", ["quality.flags"]):
        if e.kind in ("agent_stale", "agent_recovered"):
            flags[e.payload["agent_id"]] = e.kind
    now = time.time()
    print(f"run: {run.name}")
    print(f"{'agent':26s} {'pid':>7s} {'restarts':>8s} {'last_hb_s':>9s}  supervisor")
    for r in bus.registry():
        a = r["agent_id"]
        age = now - hb[a] if a in hb else float("nan")
        print(f"{a:26s} {r['pid']:7d} {r['restarts']:8d} {age:9.1f}  {flags.get(a, 'ok')}")
    return 0


def cmd_ask(cfg: dict, args: argparse.Namespace) -> int:
    """LLM-Analyst over a run's bus log (latest run unless --run)."""
    from pathlib import Path
    from rockwatch.agents.llm_analyst import AnalystStore, answer
    from rockwatch.bus.sqlite_bus import SqliteBus
    from rockwatch.llm.runtime import LLMRuntime
    from rockwatch.replay.launcher import latest_run

    run = Path(args.run) if args.run else latest_run(cfg)
    if run is None:
        print("no runs found", file=sys.stderr)
        return 2
    rt = LLMRuntime(cfg, "writer") if args.llm == "on" else None
    a = answer(rt, AnalystStore(SqliteBus(run / "bus.sqlite"), cfg), args.question)
    print(json.dumps({k: v for k, v in a.items() if k != "records"}, indent=1, default=str))
    return 0


def cmd_llm_smoke(cfg: dict, args: argparse.Namespace) -> int:
    """Real-provider smoke run: verifier (N val L2+ candidates, tools), composer, analyst refusal. Logged to reports/."""
    import datetime as dt
    import numpy as np
    from rockwatch.agents.base import AgentContext
    from rockwatch.agents.llm_composer import alert_view, compose
    from rockwatch.agents.llm_verifier import verify
    from rockwatch.eval.runner import load_inputs, load_models, n_dynamic_positive
    from rockwatch.fusion.thresholds import raw_levels
    from rockwatch.llm.evidence import PanelStore
    from rockwatch.llm.provider import make_provider
    from rockwatch.llm.runtime import LLMRuntime

    r = args.region
    P, _ = load_inputs(cfg, r)
    full = load_models(cfg, r)["full"]
    pred = full.predict(P)
    nd = n_dynamic_positive(pred, cfg)
    th = {k: v for k, v in full.thresholds.items() if k != "sweep"}
    raw = raw_levels(pred["p"].to_numpy(), nd, th, cfg["thresholds"]["corroboration_min_dynamic"])
    rc = cfg["regions"][r]
    ctx = AgentContext(cfg, r, rc["splits"]["train"][0], rc["splits"]["test"][1])
    store = PanelStore(P, pred, raw, nd, ctx)
    val = (P["split"] == "val").to_numpy() & (raw >= 2)
    idx = np.flatnonzero(val)
    idx = idx[np.argsort(-pred["p"].to_numpy()[idx])][: args.n]
    vrt = LLMRuntime(cfg, "verifier", provider=make_provider(cfg, "verifier", args.provider, batch=True))
    wrt = LLMRuntime(cfg, "writer", provider=make_provider(cfg, "writer", args.provider, batch=True))
    out = {"provider": vrt.provider.name, "verifier_model": vrt.provider.model, "writer_model": wrt.provider.model, "verifier": [], "composer": []}
    for i in idx:
        z, d = P.at[i, "zone_id"], P.at[i, "date"].strftime("%Y-%m-%d")
        v = verify(vrt, store, z, d, int(raw[i]), float(pred.at[i, "p"]), th, int(nd[i]), cfg["thresholds"]["corroboration_min_dynamic"])
        out["verifier"].append(v)
        a = alert_view(z, d, int(v["level_out"]), float(pred.at[i, "p"]), {g: float(pred.at[i, f"c_{g}"]) for g in full.groups}, None)
        if a["level"] >= 2:
            msg, rec = compose(wrt, a)
            out["composer"].append({"alert": a, "message": msg, "usage": rec})
    out["usage"] = {"verifier": vrt.usage(), "writer": wrt.usage()}
    rep = repo_path(cfg["paths"]["reports"])
    rep.mkdir(parents=True, exist_ok=True)
    f = rep / f"llm_smoke_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{out['provider']}.json"
    f.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"file": str(f), "usage": out["usage"],
                      "decisions": [(x["zone_id"], x["date"], x["decision"], x.get("verifier"), x.get("rationale")) for x in out["verifier"]]},
                     indent=1, default=str))
    ok = out["usage"]["verifier"]["outcomes"].get("ok", 0)
    if out["provider"] != "mock" and not ok:
        print("SMOKE FAILED: no verifier call returned ok (check key / model IDs / network); see the file above.", file=sys.stderr)
        return 3
    return 0


def cmd_cp2_packet(cfg: dict, args: argparse.Namespace) -> int:
    """Prepare the CP2 decision packet (val only; scenarios from weather/quakes)."""
    from rockwatch.eval.cp2 import packet
    print(packet(cfg, args.region))
    return 0


def cmd_ui(cfg: dict, args: argparse.Namespace) -> int:
    """Control-room web UI over recorded or live runs (http://localhost:8600)."""
    from rockwatch.dashboard.server import main as ui_main
    argv = ["--port", str(args.port)] + (["--run", args.run] if args.run else [])
    return ui_main(argv)


def _not_yet(phase: str):
    def f(cfg: dict, args: argparse.Namespace) -> int:
        print(f"not implemented yet ({phase})", file=sys.stderr)
        return 3
    return f


def build_parser() -> argparse.ArgumentParser:
    """Argument parser for all target commands (§15)."""
    p = argparse.ArgumentParser(prog="rockwatch")
    p.add_argument("--config", default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    sp = p.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fetch-inventory")
    f.add_argument("--no-yosemite", dest="yosemite", action="store_false")
    f.set_defaults(func=cmd_fetch_inventory)
    sp.add_parser("profile").set_defaults(func=cmd_profile)
    z = sp.add_parser("build-zones")
    z.add_argument("--regions", nargs="+", default=["A", "Y"])
    z.set_defaults(func=cmd_build_zones)
    fw = sp.add_parser("fetch-weather")
    fw.add_argument("--regions", nargs="+", default=["A", "Y"])
    fw.add_argument("--budget-s", type=float, default=3600.0)
    fw.add_argument("--max-requests", type=int, default=None)
    fw.set_defaults(func=cmd_fetch_weather)
    bd = sp.add_parser("build-data")
    bd.add_argument("--regions", nargs="+", default=["A", "Y"])
    bd.add_argument("--allow-partial", action="store_true")
    bd.set_defaults(func=cmd_build_data)
    t = sp.add_parser("train")
    t.add_argument("--regions", nargs="+", default=["A", "Y"])
    t.set_defaults(func=cmd_train)
    e = sp.add_parser("eval")
    e.add_argument("--split", choices=["val", "test"], required=True)
    e.add_argument("--final", action="store_true")
    e.add_argument("--llm", choices=["on", "off"], default="off")
    e.add_argument("--force-rerun-with-reason", default=None)
    e.add_argument("--regions", nargs="+", default=["A"])
    e.add_argument("--retrain", action="store_true")
    e.set_defaults(func=cmd_eval)
    d = sp.add_parser("run-demo")
    d.add_argument("--scenario", required=True)
    d.add_argument("--bus", choices=["sqlite", "memory", "redis"], default="sqlite")
    d.add_argument("--speed", type=float, default=1.5)
    d.add_argument("--days", type=int, default=None)
    d.add_argument("--headless", action="store_true")
    d.add_argument("--kill-agent", default=None, help="fault injection: agent_id to kill")
    d.add_argument("--kill-at-day", type=int, default=10)
    d.add_argument("--auto-restart", nargs="*", default=None, help="agent_ids the supervisor may restart")
    d.set_defaults(func=cmd_run_demo)
    d.add_argument("--llm", choices=["on", "off"], default="off")
    d.add_argument("--port", type=int, default=8600)
    d.add_argument("--ui", choices=["web", "streamlit"], default="web", help="web control room (default) or the Streamlit fallback")
    d.add_argument("--no-wait", action="store_true", help="close the dashboard when the replay ends")
    d.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    q = sp.add_parser("ask")
    q.add_argument("question")
    q.add_argument("--run", default=None)
    q.add_argument("--llm", choices=["on", "off"], default="on")
    q.set_defaults(func=cmd_ask)
    sm = sp.add_parser("llm-smoke")
    sm.add_argument("--region", default="A")
    sm.add_argument("--n", type=int, default=3)
    sm.add_argument("--provider", default=None, help="anthropic|groq|ollama|mock (default: env ROCKWATCH_LLM_PROVIDER)")
    sm.set_defaults(func=cmd_llm_smoke)
    ui = sp.add_parser("ui")
    ui.add_argument("--run", default=None)
    ui.add_argument("--port", type=int, default=8600)
    ui.set_defaults(func=cmd_ui)
    cp = sp.add_parser("cp2-packet")
    cp.add_argument("--region", default="A")
    cp.set_defaults(func=cmd_cp2_packet)
    a = sp.add_parser("agents")
    a.add_argument("action", choices=["status", "kill"])
    a.add_argument("target", nargs="?", default=None)
    a.add_argument("--run", default=None)
    a.set_defaults(func=cmd_agents)
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config(Path(args.config) if args.config else None)
    return int(args.func(cfg, args))


if __name__ == "__main__":
    raise SystemExit(main())
