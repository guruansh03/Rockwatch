"""Evaluation runner: train/load models, choose thresholds on val, evaluate a split, baselines,
ablations, breakdowns, bootstrap CIs → reports/eval_<ts>_<region>_<split>/."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rockwatch.config import repo_path
from rockwatch.data.splits import split_ranges
from rockwatch.eval.baselines import climatology_score, random_alerts, tune_threshold
from rockwatch.eval.bootstrap import bootstrap_ci
from rockwatch.eval.matching import make_frame, match
from rockwatch.eval.metrics import metrics
from rockwatch.fusion.model import ABLATIONS, FusionModel, fit_fusion
from rockwatch.fusion.thresholds import choose, raw_levels, sweep, grid

SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}


def load_inputs(cfg: dict[str, Any], region: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = repo_path(cfg["paths"]["processed"]) / region
    P = pd.read_parquet(d / "features.parquet").sort_values(["zone_id", "date"]).reset_index(drop=True)
    ev = pd.read_parquet(d / "events.parquet")
    short = ev[(ev["date_kind"] == "short_range") & ev["zone_selected"]]
    return P, short


def n_dynamic_positive(pred: pd.DataFrame, cfg: dict[str, Any]) -> np.ndarray:
    cols = [f"c_{g}" for g in cfg["fusion"]["dynamic_modalities"] if f"c_{g}" in pred.columns]
    return (pred[cols] > 0).sum(axis=1).to_numpy() if cols else np.zeros(len(pred), int)


def train_models(cfg: dict[str, Any], region: str, P: pd.DataFrame, short: pd.DataFrame) -> dict[str, FusionModel]:
    """Fit every ablation (full included); thresholds on val; save JSON under processed/<r>/models/."""
    rc = cfg["regions"][region]
    fr_val = make_frame(P, tuple(rc["splits"]["val"]), short)
    out = {}
    mdir = repo_path(cfg["paths"]["processed"]) / region / "models"
    mdir.mkdir(parents=True, exist_ok=True)
    for name, groups in ABLATIONS.items():
        m = fit_fusion(P, groups, cfg)
        pred = m.predict(P)
        m.thresholds = choose(fr_val, pred["p"].to_numpy(), n_dynamic_positive(pred, cfg), cfg)
        (mdir / f"{name}.json").write_text(m.to_json(), encoding="utf-8")
        out[name] = m
    return out


def load_models(cfg: dict[str, Any], region: str) -> dict[str, FusionModel] | None:
    mdir = repo_path(cfg["paths"]["processed"]) / region / "models"
    if not all((mdir / f"{n}.json").exists() for n in ABLATIONS):
        return None
    return {n: FusionModel.from_json((mdir / f"{n}.json").read_text(encoding="utf-8")) for n in ABLATIONS}


def _eval_levels(fr, raw, cfg, boot=True) -> dict[str, Any]:
    det = match(fr, raw, cfg["eval"]["level_main"], with_details=True)
    m = metrics(det)
    if boot:
        m["ci95"] = bootstrap_ci(fr, det, cfg["eval"]["bootstrap_n"], seed=cfg["fusion"]["seed"], gap=cfg["eval"]["storm_gap_days"])
    return m, det


def breakdowns(fr, det) -> dict[str, Any]:
    """Recall (before/at) over event-day subsets."""
    meta = fr.event_meta.copy()
    meta["tpb"], meta["tpa"] = det["tp_before_mask"], det["tp_at_mask"]
    meta["season"] = meta["date"].dt.month.map(SEASON)
    out: dict[str, Any] = {}

    def rec(df):
        return {"n": int(len(df)), "recall_before": float(df["tpb"].mean()) if len(df) else None,
                "recall_at": float(df["tpa"].mean()) if len(df) else None}
    if "y_fall" in meta:
        out["type_fall"] = rec(meta[meta["y_fall"] == 1])
        out["type_not_fall_only"] = rec(meta[meta["y_fall"] == 0])
    if "y_c5" in meta:
        out["confidence_ge5"] = rec(meta[meta["y_c5"] == 1])
    if "y_no_eq" in meta:
        out["without_eq_triggered"] = rec(meta[meta["y_no_eq"] == 1])
        out["eq_triggered_only"] = rec(meta[meta["y_no_eq"] == 0])
    for s in ("DJF", "MAM", "JJA", "SON"):
        out[f"season_{s}"] = rec(meta[meta["season"] == s])
    return out


def apply_llm_verifier(cfg, region, P, pred, raw, ndyn, th, fr, provider=None) -> tuple[np.ndarray, dict[str, Any]]:
    """Run the LLM-Verifier on every provisional L2+ row in the evaluated period (same code as live, PanelStore
    evidence, shared cache). Beyond max_llm_calls → deterministic fallback (counted)."""
    from rockwatch.agents.base import AgentContext
    from rockwatch.agents.llm_verifier import verify
    from rockwatch.llm.evidence import PanelStore
    from rockwatch.llm.runtime import LLMRuntime

    rc = cfg["regions"][region]
    ctx = AgentContext(cfg, region, rc["splits"]["train"][0], rc["splits"]["test"][1])
    store = PanelStore(P, pred, raw, ndyn, ctx)
    rt = LLMRuntime(cfg, "verifier", provider=provider)
    out = raw.copy()
    rows = np.flatnonzero((raw >= 2) & fr.in_period)
    # deterministic cap (D-035): verify the max_llm_calls highest-p candidates; the rest keep the deterministic level
    order = rows[np.argsort(-pred["p"].to_numpy()[rows], kind="stable")]
    todo, skipped = order[: rt.max_calls], order[rt.max_calls:]
    dec: dict[str, int] = {"FALLBACK_CAP": int(len(skipped))} if len(skipped) else {}
    for i in todo:
        z, d = P.at[i, "zone_id"], P.at[i, "date"].strftime("%Y-%m-%d")
        r = verify(rt, store, z, d, int(raw[i]), float(pred.at[i, "p"]), th, int(ndyn[i]), cfg["thresholds"]["corroboration_min_dynamic"])
        out[i] = r["level_out"]
        dec[r["decision"]] = dec.get(r["decision"], 0) + 1
    usage = rt.usage()
    usage.update(candidates=int(len(rows)), decisions=dec, levels_changed=int((out != raw).sum()))
    return out, usage


def evaluate(cfg: dict[str, Any], region: str, split: str, retrain: bool = False, llm: bool = False) -> dict[str, Any]:
    """Full evaluation of one region/split (optionally with the LLM-Verifier on L2+ candidates)."""
    rc = cfg["regions"][region]
    P, short = load_inputs(cfg, region)
    models = None if retrain else load_models(cfg, region)
    if models is None:
        models = train_models(cfg, region, P, short)
    per = tuple(rc["splits"][split])
    fr = make_frame(P, per, short)
    fr_val = make_frame(P, tuple(rc["splits"]["val"]), short)
    bs = json.loads((repo_path(cfg["paths"]["processed"]) / region / "build_summary.json").read_text(encoding="utf-8"))
    res: dict[str, Any] = {"region": region, "region_name": rc["name"], "split": split, "period": per,
                           "banner": cfg["eval"]["banner"], "llm_verifier": "on" if llm else "off",
                           "data_coverage": {"zones_total": bs["zones_total"], "zones_missing_weather": len(bs["zones_missing_weather"]),
                                             "partial": bool(bs["zones_missing_weather"])}}
    # ---- full model
    full = models["full"]
    pred = full.predict(P)
    ndyn = n_dynamic_positive(pred, cfg)
    p = pred["p"].to_numpy()
    raw = raw_levels(p, ndyn, full.thresholds, cfg["thresholds"]["corroboration_min_dynamic"])
    m_off = None
    if llm:
        th = {k: v for k, v in full.thresholds.items() if k != "sweep"}
        m_off = metrics(match(fr, (raw >= 2).astype(np.int8) * 2, 2))
        raw, res["llm_usage"] = apply_llm_verifier(cfg, region, P, pred, raw, ndyn, th, fr)
    m, det = _eval_levels(fr, raw, cfg)
    m["level_counts_active_days"] = {f"L{k}": int(((det["active"] == k) & fr.in_period).sum()) for k in range(4)}
    m["l1plus"] = metrics(match(fr, (raw >= 1).astype(np.int8) * 2, 2))
    m["l3"] = metrics(match(fr, (raw >= 3).astype(np.int8) * 3, 3)) if full.thresholds.get("l3_enabled") else "disabled"
    res["rockwatch"] = m
    res["thresholds"] = {k: v for k, v in full.thresholds.items() if k != "sweep"}
    res["model"] = {"C": full.C, "intercept": full.intercept, "coef": full.coef, "platt": [full.platt_a, full.platt_b], **full.train_info}
    res["breakdowns"] = breakdowns(fr, det)
    res["lead_days_tp_at"] = det["lead_days"]
    # ---- baselines
    n = cfg["thresholds"]["n_grid"]
    base: dict[str, Any] = {}
    s1 = P["P1"].fillna(0).to_numpy()
    q = tune_threshold(fr_val, s1, n)
    base["B1_P1_threshold"] = {"q_mm": q, **_eval_levels(fr, (s1 >= q).astype(np.int8) * 2, cfg)[0]}
    s2 = P["seattle_ct_margin_in"].to_numpy()
    base["B2_seattle_ct_designed_for_seattle"] = _eval_levels(fr, (np.nan_to_num(s2, nan=-9) > 0).astype(np.int8) * 2, cfg)[0]
    s3 = climatology_score(P, cfg["eval"]["clim_smoothing_k"])
    t3c = tune_threshold(fr_val, s3, n)
    base["B3_seasonal_climatology"] = {"t": t3c, **_eval_levels(fr, (s3 >= t3c).astype(np.int8) * 2, cfg)[0]}
    base["B4_random_matched_rate"] = random_alerts(fr, m["alert_day_fraction"] or 0.0, cfg["eval"]["random_baseline_draws"], cfg["fusion"]["seed"])
    # ---- ablations (B5 = rain)
    abl: dict[str, Any] = {}
    curves: dict[str, Any] = {}
    for name, mod in models.items():
        pr = mod.predict(P)
        rl = raw_levels(pr["p"].to_numpy(), n_dynamic_positive(pr, cfg), mod.thresholds, cfg["thresholds"]["corroboration_min_dynamic"])
        am = metrics(match(fr, (rl >= 2).astype(np.int8) * 2, 2))
        am["val_ap"] = mod.train_info.get("val_ap")
        am["t2"] = mod.thresholds["t2"]
        abl[name] = am
        if name in ("rain", "full"):
            ts = grid(pr["p"].to_numpy()[fr.in_period], 60)
            curves[name] = [(x["recall_at"], x["precision_episode"]) for x in sweep(fr, pr["p"].to_numpy(), ts)]
    base["B5_rain_only"] = abl["rain"]
    if llm:
        abl["full (LLM-Verifier off)"] = {**m_off, "val_ap": full.train_info.get("val_ap"), "t2": full.thresholds["t2"]}
        abl["full + LLM-Verifier"] = {**{k: m[k] for k in m if k != "ci95"}, "val_ap": full.train_info.get("val_ap"), "t2": full.thresholds["t2"]}
    res["baselines"] = base
    res["ablations"] = abl
    for nm, sc in (("B1_P1", s1), ("B3_climatology", s3)):
        ts = grid(sc[fr.in_period], 60)
        curves[nm] = [(x["recall_at"], x["precision_episode"]) for x in sweep(fr, sc, ts)]
    res["pr_curves"] = curves
    res["val_sweep_full"] = full.thresholds.get("sweep")
    return res


def git_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=repo_path(".")).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"
