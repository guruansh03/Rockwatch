"""CP2 decision packet (no test labels are read): validation results under both L2 threshold rules and
demo-scenario proposals for the test period chosen from WEATHER and QUAKES only."""
from __future__ import annotations

import copy
import datetime as dt
import json
from typing import Any

import numpy as np
import pandas as pd

from rockwatch.config import repo_path
from rockwatch.data.quakes import haversine_km


def scenario_proposals(cfg: dict[str, Any], region: str, days: int = 45) -> dict[str, Any]:
    from rockwatch.agents.base import AgentContext
    rc = cfg["regions"][region]
    a, b = rc["splits"]["test"]
    ctx = AgentContext(cfg, region, a, b)
    pr = pd.DataFrame({z: w["precipitation_sum"] for z, w in ctx.weather.items()})
    pr = pr[(pr.index >= a) & (pr.index <= b)]
    reg = pr.mean(axis=1).rolling(days).mean().dropna()   # region-mean daily precip over a window ending at index
    storm_end, quiet_end = reg.idxmax(), reg.idxmin()
    q = pd.read_parquet(repo_path(cfg["paths"]["processed"]) / region / "quakes.parquet")
    q = q[(q["date_local"] >= a) & (q["date_local"] <= b)]
    z = ctx.zones
    dmin = np.array([haversine_km(r.lat, r.lon, z["lat"].to_numpy(), z["lon"].to_numpy()).min() for r in q.itertuples()]) if len(q) else np.array([])
    near = q[dmin <= 100] if len(q) else q
    out = {"storm": {"start": (storm_end - pd.Timedelta(days=days - 1)).strftime("%Y-%m-%d"), "days": days,
                     "why": f"wettest {days}-day window of region-mean precipitation in test period ({reg.max():.1f} mm/day)"},
           "quiet": {"start": (quiet_end - pd.Timedelta(days=days - 1)).strftime("%Y-%m-%d"), "days": days,
                     "why": f"driest {days}-day window ({reg.min():.2f} mm/day)"}}
    if len(near):
        big = near.sort_values("mag").iloc[-1]
        s = pd.Timestamp(big["date_local"]) - pd.Timedelta(days=10)
        out["earthquake"] = {"start": max(s, pd.Timestamp(a)).strftime("%Y-%m-%d"), "days": days,
                             "why": f"largest quake ≤100 km of a zone in test period: M{big['mag']} on {pd.Timestamp(big['date_local']).date()}"}
    return {k: {**v, "region": region} for k, v in out.items()}


def packet(cfg: dict[str, Any], region: str) -> str:
    from rockwatch.eval.runner import evaluate
    bs = json.loads((repo_path(cfg["paths"]["processed"]) / region / "build_summary.json").read_text(encoding="utf-8"))
    rows = []
    for rule in ("f1_episode", "f1_day"):
        c = copy.deepcopy(cfg)
        c["thresholds"]["t2_rule"] = rule
        c["eval"]["bootstrap_n"] = 200
        r = evaluate(c, region, "val", retrain=True)
        m = r["rockwatch"]
        rows.append((rule, r["thresholds"]["t2"], m, r["baselines"]))
    # restore models for the configured rule
    evaluate(cfg, region, "val", retrain=True)
    sc = scenario_proposals(cfg, region)
    f = lambda x: "–" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))  # noqa: E731
    L = [f"# CP2 decision packet — region {region}\n", f"Generated {dt.datetime.now():%Y-%m-%d %H:%M}. **No test-split labels were read to produce this page.**\n",
         f"Data coverage: {bs['zones_total'] - len(bs['zones_missing_weather'])}/{bs['zones_total']} zones with weather"
         + (" — **PARTIAL: complete the weather fetch before the final run.**" if bs["zones_missing_weather"] else "") + "\n",
         "## Decision 1 — L2 threshold rule (validation split; optimistic because thresholds are tuned here)\n",
         "| t2 rule | t2 | recall_before | recall_at | precision_episode | precision_day | F1_at | F1_day | alert-day frac | FA/zone-yr | B4 random recall_at @ same frac |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for rule, t2, m, b in rows:
        L.append(f"| {rule} | {t2:.4f} | {f(m['recall_before'])} | {f(m['recall_at'])} | {f(m['precision_episode'])} | {f(m['precision_day'])} | "
                 f"{f(m['f1_at'])} | {f(m['f1_day'])} | {f(m['alert_day_fraction'])} | {f(m['false_alarms_per_zone_year'])} | {f(b['B4_random_matched_rate']['recall_at'])} |")
    L += ["\n- `f1_episode` = spec §8 as written. Episode precision counts a long episode as one hit, so it can favour near-always-on alerting.",
          "- `f1_day` = day-level precision: every alert-day costs. Recommended if `f1_episode` gives an alert-day fraction near 1.\n",
          "## Decision 2 — demo scenarios (test period; chosen from weather + quakes only)\n", "| name | start | days | why |", "|---|---|---|---|"]
    for k, v in sc.items():
        L.append(f"| test_{k} | {v['start']} | {v['days']} | {v['why']} |")
    L += ["\n## Decision 3 — run the final evaluation\n",
          "`python -m rockwatch eval --split test --final --regions A Y` then `--llm on` (same split, same cache).",
          "Test metrics can be produced once; reruns need `--force-rerun-with-reason`.\n",
          "Reply at CP2 with: t2 rule, scenario OK/changes, go/no-go for the final run."]
    out = repo_path(cfg["paths"]["docs"]) / f"cp2_packet_{region}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    (repo_path(cfg["paths"]["docs"]) / f"cp2_scenarios_{region}.json").write_text(json.dumps(sc, indent=1), encoding="utf-8")
    return str(out)
