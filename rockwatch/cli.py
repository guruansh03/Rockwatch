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
    sp.add_parser("train").set_defaults(func=_not_yet("P2"))
    e = sp.add_parser("eval")
    e.add_argument("--split", choices=["val", "test"], required=True)
    e.add_argument("--final", action="store_true")
    e.add_argument("--llm", choices=["on", "off"], default="off")
    e.add_argument("--force-rerun-with-reason", default=None)
    e.set_defaults(func=_not_yet("P2/P6"))
    d = sp.add_parser("run-demo")
    d.add_argument("--scenario", required=True)
    d.add_argument("--bus", choices=["sqlite", "memory", "redis"], default="sqlite")
    d.add_argument("--speed", type=float, default=1.5)
    d.set_defaults(func=_not_yet("P3/P5"))
    a = sp.add_parser("agents")
    a.add_argument("action", choices=["status"])
    a.set_defaults(func=_not_yet("P3"))
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config(Path(args.config) if args.config else None)
    return int(args.func(cfg, args))


if __name__ == "__main__":
    raise SystemExit(main())
