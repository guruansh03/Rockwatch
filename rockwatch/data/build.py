"""build-data orchestration (§6–7): zones → weather → features → labels → splits → parquet + data card."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from rockwatch.config import repo_path
from rockwatch.data import labels as L
from rockwatch.data.quakes import fetch_region
from rockwatch.data.splits import assign_split, split_ranges, validate
from rockwatch.data.weather import ZoneRequest, load_zone, zone_meta
from rockwatch.data.zones import assign_cells, build_grid, weather_range
from rockwatch.features.context import regional_extent, season
from rockwatch.features.rainfall import rain_features
from rockwatch.features.seismic import seismic_features
from rockwatch.features.susceptibility import susceptibility
from rockwatch.features.thermal import doy_climatology, thermal_features

log = logging.getLogger(__name__)
FEATURE_GROUPS = {
    "rain": ["P1", "P3", "P15", "P30", "API", "precip_hours", "intensity", "seattle_ct_margin_in", "rain_on_snow"],
    "thermal": ["ft_cycles_7d", "tmax_anom"],
    "seismic": ["eq_max_mag_3d", "eq_count_3d", "eq_min_dist_km_3d"],
    "susceptibility": ["susc"],
    "context": ["month_sin", "month_cos", "regional_extent"],
}


def build_region(cfg: dict[str, Any], region: str, allow_partial: bool = False) -> dict[str, Any]:
    """Build data/processed/<region>/{features,events}.parquet. Returns a summary dict."""
    rc = cfg["regions"][region]
    validate(rc)
    sr = split_ranges(rc)
    proc = repo_path(cfg["paths"]["processed"]) / region
    cache = repo_path(cfg["paths"]["cache"])
    zones = pd.read_parquet(proc / "zones.parquet")
    a, b = weather_range(rc, cfg["zones"]["antecedent_days"])
    yrs = cfg["weather"]["chunk_years"]
    frames, missing, metas = [], [], {}
    for z in zones.itertuples():
        req = ZoneRequest(region, z.zone_id, float(z.lat), float(z.lon), a, b)
        w = load_zone(cache, req, yrs)
        if w is None:
            missing.append(z.zone_id)
            continue
        metas[z.zone_id] = zone_meta(cache, req, yrs)
        w = w.set_index("date").reindex(pd.date_range(a, b, freq="D")).rename_axis("date").reset_index()
        w["zone_id"] = z.zone_id
        f = rain_features(w)
        clim = doy_climatology(w, rc["splits"]["train"][0], rc["splits"]["train"][1])
        t = thermal_features(w, clim)
        f = pd.concat([f, t.drop(columns="date")], axis=1)
        f.insert(0, "zone_id", z.zone_id)
        f["wx_missing"] = w[cfg["weather"]["daily"]].isna().any(axis=1).astype(int)
        frames.append(f)
    if missing and not allow_partial:
        raise RuntimeError(f"{region}: weather missing for {len(missing)} zones; run fetch-weather or pass --allow-partial")
    zones_ok = zones[~zones["zone_id"].isin(missing)]
    panel = pd.concat(frames, ignore_index=True)
    panel = panel[(panel["date"] >= sr["train"][0]) & (panel["date"] <= sr["test"][1])].reset_index(drop=True)

    quakes = fetch_region(cfg, region, a, b, cache)
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    seis = seismic_features(zones_ok, dates, quakes)
    panel = panel.merge(seis, on=["zone_id", "date"], how="left")

    deg = cfg["zones"]["deg"]
    if "single_zone" in rc:
        panel["susc"] = 0.0
        y = __import__("rockwatch.data.yosemite", fromlist=["load_yosemite"]).load_yosemite(
            next(repo_path(cfg["yosemite"]["raw_dir"]).glob("*.xlsx")))
        events = L.yosemite_events(y, rc["single_zone"]["zone_id"])
    else:
        inv = pd.read_parquet(repo_path(cfg["paths"]["interim"]) / "inventory_clean.parquet")
        cells = assign_cells(inv, rc["bbox"], deg)
        sus = susceptibility(cells, build_grid(rc["bbox"], deg), rc["splits"]["train"][1])
        panel = panel.merge(sus[["zone_id", "susc"]], on="zone_id", how="left")
        events = L.usgs_events(inv, rc, deg, cfg["inventory"]["c_min"])

    panel = pd.concat([panel, season(panel["date"])], axis=1)
    panel["regional_extent"] = regional_extent(panel[["zone_id", "date", "P3"]], tuple(rc["splits"]["val"]))
    panel["split"] = assign_split(panel["date"], rc)
    lab = L.label_panel(panel[["zone_id", "date"]], events)
    panel = pd.concat([panel, lab.drop(columns=["zone_id", "date"])], axis=1)

    events["split"] = assign_split(pd.to_datetime(events["date_min"]), rc)
    events["zone_selected"] = events["zone_id"].isin(zones_ok["zone_id"])
    proc.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(proc / "features.parquet", index=False)
    events.to_parquet(proc / "events.parquet", index=False)
    quakes.to_parquet(proc / "quakes.parquet", index=False)
    (proc / "zone_meta.json").write_text(json.dumps(metas, indent=1, default=str), encoding="utf-8")
    summary = summarize(region, rc, zones, missing, panel, events, quakes)
    (proc / "build_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


def summarize(region, rc, zones, missing, panel, events, quakes) -> dict[str, Any]:
    ex = events[events["date_kind"] == "exact"]
    in_panel = ex[ex["zone_selected"] & ex["split"].isin(["train", "val", "test"])]
    s: dict[str, Any] = {
        "region": region, "name": rc["name"], "zones_total": len(zones), "zones_missing_weather": missing,
        "zone_kinds": zones["kind"].value_counts().to_dict(), "panel_rows": len(panel),
        "dates": [str(panel["date"].min().date()), str(panel["date"].max().date())],
        "wx_missing_rows": int(panel["wx_missing"].sum()),
        "feature_nan_rows": {c: int(panel[c].isna().sum()) for g in FEATURE_GROUPS.values() for c in g},
        "quakes_M3plus": len(quakes), "quakes_max_mag": float(quakes["mag"].max()) if len(quakes) else None,
        "exact_events_total": len(ex), "exact_events_in_unselected_zones": int((~ex["zone_selected"]).sum()),
        "exact_events_in_gaps_or_outside": int((~ex["split"].isin(["train", "val", "test"])).sum()),
        "short_range_events": int((events["date_kind"] == "short_range").sum()),
        "by_split": {},
    }
    for k in ("train", "val", "test"):
        p = panel[panel["split"] == k]
        s["by_split"][k] = {"zone_days": len(p), "pos_zone_days": int(p["y"].sum()), "pos_fall": int(p["y_fall"].sum()),
                            "pos_no_eq": int(p["y_no_eq"].sum()), "pos_rate": round(float(p["y"].mean()), 5) if len(p) else None,
                            "events": int((in_panel["split"] == k).sum())}
    return s


def write_data_card(cfg: dict[str, Any], regions: list[str]) -> Path:
    """docs/data_card.md from build_summary.json files (numbers computed, never typed)."""
    L_: list[str] = ["# Data card — RockWatch-FuseGuard\n",
                     "> US natural-slope and road-cut data; **not open-pit mine performance**. Reported precision is a "
                     "**lower bound** (unreported events). Lead time in **days** (daily inputs).\n",
                     "## Sources\n",
                     "- Ground truth: USGS, *Landslide Inventories across the United States* v3.0, DOI 10.5066/P14AJF8I (CC0). "
                     "Point + polygon CSVs. Training labels / evaluation only — never a live input.",
                     "- Rockfall track: USGS Data Series 746, Yosemite rock falls 1857–2011 (Stock et al.). No coordinates; one valley zone.",
                     "- Weather: Open-Meteo historical archive (ERA5-family reanalysis), daily, `timezone=auto`. "
                     "**Weather data by Open-Meteo.com** (CC BY 4.0). One request per zone centre.",
                     "- Earthquakes: USGS ComCat FDSN, region bbox + 200 km, M≥3.\n",
                     "## Construction\n",
                     f"- Zones: {cfg['zones']['deg']}° cells. Kept = cells with ≥1 undated or train-period inventory feature, "
                     f"+ random sample of zero-feature 8-neighbour cells (ratio {cfg['zones']['zero_feature_ratio']}, seed {cfg['zones']['seed']}).",
                     f"- Labels: exact-dated events, Confidence ≥ {cfg['inventory']['c_min']}; y_fall, y_no_eq, y_c5 subsets. "
                     "Short-range events stored for range-aware matching only. Long-range/undated never positive.",
                     "- Splits: chronological with ≥30-day gaps (config `regions.*.splits`, frozen at CP1).",
                     "- Features (≤ day d only): rain (P1, P3, P15, P30, API k=0.9, hours, intensity, Seattle CT margin, rain-on-snow), "
                     "thermal (freeze–thaw 7 d, Tmax anomaly vs train-only DOY climatology), seismic (100 km / 3 d: max M, count, min dist), "
                     "susceptibility (log1p prior count, neighbour-smoothed; train+undated only), context (month sin/cos, regional extent).\n"]
    for r in regions:
        p = repo_path(cfg["paths"]["processed"]) / r / "build_summary.json"
        if not p.exists():
            continue
        s = json.loads(p.read_text(encoding="utf-8"))
        L_.append(f"## Region {r}: {s['name']}\n")
        L_.append(f"- Zones: {s['zones_total']} {s['zone_kinds']}; missing weather: {len(s['zones_missing_weather'])}.")
        L_.append(f"- Panel: {s['panel_rows']} zone-days, {s['dates'][0]} → {s['dates'][1]}; rows with any missing weather var: {s['wx_missing_rows']}.")
        L_.append(f"- Quakes M≥3 in buffer: {s['quakes_M3plus']} (max M{s['quakes_max_mag']}).")
        L_.append(f"- Exact events: {s['exact_events_total']}; in unselected zones (dropped, leakage-safe selection): "
                  f"{s['exact_events_in_unselected_zones']}; in gaps/outside splits: {s['exact_events_in_gaps_or_outside']}; "
                  f"short-range events: {s['short_range_events']}.\n")
        L_.append("| split | zone_days | pos_zone_days | pos_fall | pos_no_eq | pos_rate | events |")
        L_.append("|---|---|---|---|---|---|---|")
        for k, v in s["by_split"].items():
            L_.append(f"| {k} | {v['zone_days']} | {v['pos_zone_days']} | {v['pos_fall']} | {v['pos_no_eq']} | {v['pos_rate']} | {v['events']} |")
        L_.append("")
    L_.append("## Known biases\n")
    L_.append("- Region A truth = one agency log (AK DOT) along highways: road-cut slopes, maintenance-reporting bias, "
              "reporting declines 2021–22 (test FP inflated).")
    L_.append("- Yosemite: eyewitness bias (visitor-dense areas), reporting intensity rises after ~2000.")
    L_.append("- Reanalysis precipitation underestimates local convective/orographic extremes.")
    out = repo_path(cfg["paths"]["docs"]) / "data_card.md"
    out.write_text("\n".join(L_) + "\n", encoding="utf-8")
    return out
