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
    if any(yx.glob("*.xlsx")):
        from rockwatch.data.yosemite import load_yosemite
        y = load_yosemite(next(yx.glob("*.xlsx")))
        (docs / "data_profile.md").open("a", encoding="utf-8").write(
            f"\n## 7. Yosemite DS746 (raw)\n\nSheet `{y.attrs.get('sheet')}`: {len(y)} rows; columns: {list(y.columns)}\n")
    print(f"wrote {docs / 'data_profile.md'}")
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
    sp.add_parser("build-data").set_defaults(func=_not_yet("P1"))
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
