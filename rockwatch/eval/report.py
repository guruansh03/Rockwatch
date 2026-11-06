"""Report writer (§10): reports/eval_<ts>_<region>_<split>/ with metrics, plots, ablation, frozen config."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from rockwatch.config import repo_path

FOOTER = ("Data: USGS Landslide Inventories across the US v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; "
          "USGS ComCat. Weather data by Open-Meteo.com (CC BY 4.0).")


def _f(x: Any, nd: int = 3) -> str:
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _ci(m: dict[str, Any], k: str) -> str:
    ci = (m.get("ci95") or {}).get(k)
    return f"{_f(m.get(k))} [{_f(ci[0])}, {_f(ci[1])}]" if ci else _f(m.get(k))


ROW_KEYS = ["recall_before", "recall_at", "precision_episode", "precision_day", "f1_at", "f1_day", "false_alarms_per_zone_year", "alert_day_fraction"]


def _table(rows: dict[str, dict[str, Any]], with_ci: bool) -> list[str]:
    L = ["| system | " + " | ".join(ROW_KEYS) + " | episodes |", "|---|" + "---|" * (len(ROW_KEYS) + 1)]
    for name, m in rows.items():
        cells = [(_ci(m, k) if with_ci else _f(m.get(k))) for k in ROW_KEYS]
        L.append(f"| {name} | " + " | ".join(cells) + f" | {m.get('n_episodes', '–')} |")
    return L


def write_report(res: dict[str, Any], cfg: dict[str, Any], git: str, llm_usage: dict[str, Any] | None = None) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = repo_path(cfg["paths"]["reports"]) / f"eval_{ts}_{res['region']}_{res['split']}"
    out.mkdir(parents=True, exist_ok=True)
    small = {k: v for k, v in res.items() if k not in ("pr_curves", "val_sweep_full")}
    small["git_hash"] = git
    small["generated"] = ts
    (out / "metrics.json").write_text(json.dumps(small, indent=1, default=float), encoding="utf-8")
    (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (out / "git_hash.txt").write_text(git + "\n", encoding="utf-8")
    (out / "llm_usage.json").write_text(json.dumps(llm_usage or {"llm_verifier": res.get("llm_verifier", "off"), "calls": 0}, indent=1), encoding="utf-8")
    rw = res["rockwatch"]
    L = [f"# RockWatch evaluation — region {res['region']} ({res['region_name']}), split **{res['split']}**\n",
         f"> **{res['banner']}** Lead time in days (daily inputs); no time-of-failure prediction.\n",
         f"Period {res['period'][0]} → {res['period'][1]} · git `{git[:10]}` · LLM verifier: {res['llm_verifier']} · alert level for P/R: L2+\n"]
    dc = res.get("data_coverage", {})
    if dc.get("partial"):
        L.append(f"**⚠ PARTIAL DATA: {dc['zones_missing_weather']} of {dc['zones_total']} zones lack weather. Smoke test only — not a result.**\n")
    if res["split"] == "val":
        L.append("_Validation split: thresholds and baseline cut-offs were tuned on this split, so these numbers are optimistic._\n")
    L.append(f"Event-days: {rw['n_event_days']} · short-range events: {rw['n_short_range']} · zone-days: {rw['zone_days']}\n")
    L.append("## RockWatch vs baselines (95% CI: block bootstrap by storm cluster, "
             f"{rw['ci95']['n_resamples']} resamples, {rw['ci95']['n_blocks']} blocks)\n")
    rows = {"RockWatch (full fusion)": rw}
    for k, v in res["baselines"].items():
        rows[k] = v
    L += _table({"RockWatch (full fusion)": rw}, True)
    L.append("")
    L += _table({k: v for k, v in rows.items() if k != "RockWatch (full fusion)"}, True)
    L.append("\nB4 = mean over random draws at RockWatch's alert-day fraction (range95 in metrics.json). "
             "B2 is the published USGS Seattle cumulative threshold, designed for Seattle, applied unchanged.\n")
    L.append("## Thresholds (validation-only rules)\n")
    th = res["thresholds"]
    L.append(f"- t1 (L1) = {_f(th['t1'], 4)} — {th['rule_t1']}\n- t2 (L2) = {_f(th['t2'], 4)} — {th['rule_t2']}\n"
             f"- t3 (L3) = {_f(th['t3'], 4)} — {th['rule_t3']}; L3 enabled: {th['l3_enabled']}\n")
    L.append(f"- Active zone-days by level: {rw['level_counts_active_days']}; L1+ recall_at {_f(rw['l1plus']['recall_at'])}, "
             f"alert-day fraction {_f(rw['l1plus']['alert_day_fraction'])}\n")
    L.append("## Breakdowns (recall over event-days)\n")
    L.append("| subset | n | recall_before | recall_at |\n|---|---|---|---|")
    for k, v in res["breakdowns"].items():
        L.append(f"| {k} | {v['n']} | {_f(v['recall_before'])} | {_f(v['recall_at'])} |")
    ld = rw.get("lead_days") or {}
    L.append(f"\n## Lead days (TP_at events)\n\nn={ld.get('n')}, median={_f(ld.get('median'))}, mean={_f(ld.get('mean'))}; "
             f"histogram {ld.get('hist')} (0 = same-day nowcast only).\n")
    L.append(f"## Model\n\nC={res['model']['C']}, positives={res['model']['n_pos']}, negatives sampled={res['model']['n_neg_sampled']} "
             f"(ratio {res['model']['neg_per_pos_actual']}:1 of {res['model']['n_neg_available']} available), val AP={_f(res['model']['val_ap'])}.\n")
    L.append("See `ablation.md`, `pr_curve.png`, `lead_days.png`.\n")
    L.append(f"---\n{FOOTER}\n")
    (out / "metrics.md").write_text("\n".join(L), encoding="utf-8")
    A = [f"# Ablations — region {res['region']}, split {res['split']}\n", f"> {res['banner']}\n",
         "Each row: separate L2-LR + Platt + thresholds chosen on validation; evaluated on this split at L2+.\n",
         "| groups | val AP | t2 | recall_before | recall_at | precision_episode | precision_day | f1_at | FA/zone-yr | alert-day frac |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for k, m in res["ablations"].items():
        A.append(f"| {k} | {_f(m['val_ap'])} | {_f(m['t2'], 4)} | {_f(m['recall_before'])} | {_f(m['recall_at'])} | {_f(m['precision_episode'])} | "
                 f"{_f(m['precision_day'])} | {_f(m['f1_at'])} | {_f(m['false_alarms_per_zone_year'])} | {_f(m['alert_day_fraction'])} |")
    if res.get("llm_usage"):
        u = res["llm_usage"]
        A.append(f"\nLLM-Verifier: provider {u['provider']} / {u['model']}; candidates {u['candidates']}; provider calls {u['calls_made']} "
                 f"(cap {u['cap']}); outcomes {u['outcomes']}; decisions {u['decisions']}; levels changed {u['levels_changed']}.\n")
    else:
        A.append("\nLLM-Verifier off for this run (`--llm on` adds full ± verifier rows; same split, same cache).\n")
    (out / "ablation.md").write_text("\n".join(A) + "\n", encoding="utf-8")
    _plots(res, out)
    return out


PALETTE = {"full": "#16181B", "rain": "#1F5FAD", "B1_P1": "#8A8F96", "B3_climatology": "#4E8E69"}
INK, MUTED, RULE, ACCENT = "#16181B", "#7C8188", "#E2E0DA", "#DD6A1E"


def _style(ax) -> None:
    """Match the control-room UI: thin rules, no top/right spines, muted ticks."""
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(RULE)
    ax.tick_params(colors=MUTED, labelsize=8, length=3)
    ax.grid(color=RULE, linewidth=0.8, linestyle=(0, (2, 3)))
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    ax.title.set_color(INK)


def _plots(res: dict[str, Any], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": ["IBM Plex Sans", "DejaVu Sans"], "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "semibold",
                         "axes.titlelocation": "left", "axes.labelsize": 9, "legend.frameon": False})
    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    for name, pts in res["pr_curves"].items():
        pts = [(r, p) for r, p in pts if r is not None and p is not None]
        if pts:
            r, p = zip(*sorted(pts))
            ax.plot(r, p, label=name, lw=2.0 if name == "full" else 1.2, color=PALETTE.get(name, MUTED), zorder=3 if name == "full" else 2)
    rw = res["rockwatch"]
    if rw["recall_at"] is not None and rw["precision_episode"] is not None:
        ax.scatter([rw["recall_at"]], [rw["precision_episode"]], s=42, color=ACCENT, edgecolor="white", linewidth=1.2, zorder=5, label="RockWatch @ t2")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("event-day recall (TP_at)")
    ax.set_ylabel("episode precision (lower bound)")
    ax.set_title(f"Precision–recall sweep · region {res['region']} · {res['split']}", pad=34)
    _style(ax)
    ax.legend(fontsize=7.5, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 1.0), borderaxespad=1.6)
    fig.text(0.01, 0.012, res["banner"], fontsize=6.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(out / "pr_curve.png", dpi=150)
    plt.close(fig)
    ld = np.asarray(res.get("lead_days_tp_at") or [])
    cap = 30
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    if len(ld):
        clipped = np.minimum(ld, cap)
        counts = np.bincount(clipped.astype(int), minlength=cap + 1)
        colors = [ACCENT if k == 0 else INK for k in range(cap + 1)]
        colors[-1] = MUTED
        ax.bar(np.arange(cap + 1), counts, width=0.78, color=colors)
        ax.set_xticks([0, 1, 2, 3, 5, 7, 10, 14, 21, cap])
        ax.set_xticklabels([str(t) if t < cap else f"{cap}+" for t in [0, 1, 2, 3, 5, 7, 10, 14, 21, cap]])
        if (ld >= cap).any():
            ax.text(cap, counts[-1], f"  {int((ld >= cap).sum())} in episodes ≥{cap} d", fontsize=7, color=MUTED, va="bottom", ha="right")
    ax.set_xlabel("lead (days) = event day − start of the matched alert episode   (0 = same-day nowcast)")
    ax.set_ylabel("TP_at event-days")
    ax.set_title("Lead-days distribution (days, not hours)")
    _style(ax)
    fig.text(0.01, 0.012, res["banner"], fontsize=6.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out / "lead_days.png", dpi=150)
    plt.close(fig)
