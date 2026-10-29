"""Phase 0 profiling -> docs/data_profile.md. Region ranking + chronological split proposal.

Every number in the profile is computed from the real inventory. Nothing is filled in by hand.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rockwatch.data.usgs_inventory import CleanReport

EQ_INVENTORIES = ("USGS Earthquake-Triggered Ground Failure", "USGS Seismogenic Mass Movements")


# --------------------------------------------------------------------------- grid helpers
def zone_rc(lat: pd.Series | np.ndarray, lon: pd.Series | np.ndarray, deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Global grid indices (row from lat, col from lon), cell = deg."""
    r = np.floor(np.asarray(lat, dtype=float) / deg).astype(int)
    c = np.floor(np.asarray(lon, dtype=float) / deg).astype(int)
    return r, c


def dated_positives(df: pd.DataFrame, c_min: int, min_year: int) -> pd.DataFrame:
    """Exact-dated events with confidence >= c_min since min_year."""
    m = (df["date_kind"] == "exact") & (df["confidence"].fillna(-1) >= c_min) & (df["date_min"].dt.year >= min_year)
    return df[m]


def positive_zone_days(ev: pd.DataFrame, deg: float) -> pd.DataFrame:
    """Unique (zr, zc, date) with lat/lon of the zone centre and fall flag (any fall event that zone-day)."""
    if ev.empty:
        return pd.DataFrame(columns=["zr", "zc", "date", "lat_c", "lon_c", "has_fall", "n_events"])
    r, c = zone_rc(ev["lat"], ev["lon"], deg)
    t = pd.DataFrame({"zr": r, "zc": c, "date": ev["date_min"].values,
                      "is_fall": (ev["type_family"] == "fall").values})
    g = t.groupby(["zr", "zc", "date"], as_index=False).agg(has_fall=("is_fall", "any"), n_events=("is_fall", "size"))
    g["lat_c"] = (g["zr"] + 0.5) * deg
    g["lon_c"] = (g["zc"] + 0.5) * deg
    return g


# --------------------------------------------------------------------------- region ranking
@dataclass
class Region:
    """Candidate region bbox and its positive counts."""
    lat0: float
    lat1: float
    lon0: float
    lon1: float
    window_deg: float
    pos_zone_days: int
    fall_zone_days: int
    distinct_days: int
    storm_clusters: int
    pos_zone_days_c5: int
    pos_zone_days_no_eq: int
    n_zones_with_pos: int

    def bbox(self) -> tuple[float, float, float, float]:
        """(lat0, lat1, lon0, lon1)."""
        return (self.lat0, self.lat1, self.lon0, self.lon1)


def storm_clusters(dates: pd.Series, gap_days: int = 3) -> int:
    """Clusters of event dates where consecutive dates differ by <= gap_days (region-wide)."""
    d = pd.Series(pd.to_datetime(dates).unique()).sort_values()
    if d.empty:
        return 0
    return int(1 + (d.diff().dt.days > gap_days).sum())


def in_bbox(df: pd.DataFrame, bbox: tuple[float, float, float, float], lat: str = "lat", lon: str = "lon") -> pd.Series:
    """Half-open bbox mask."""
    a0, a1, o0, o1 = bbox
    return (df[lat] >= a0) & (df[lat] < a1) & (df[lon] >= o0) & (df[lon] < o1)


def region_stats(clean: pd.DataFrame, bbox: tuple[float, float, float, float], window: float,
                 c_min: int, c_alt: int, min_year: int, deg: float) -> Region:
    """Compute all ranking stats for one bbox."""
    sub = clean[in_bbox(clean, bbox)]
    ev = dated_positives(sub, c_min, min_year)
    pz = positive_zone_days(ev, deg)
    pz5 = positive_zone_days(dated_positives(sub, c_alt, min_year), deg)
    ev_no = ev[~ev["Inventory"].isin(EQ_INVENTORIES)]
    pz_no = positive_zone_days(ev_no, deg)
    return Region(
        lat0=bbox[0], lat1=bbox[1], lon0=bbox[2], lon1=bbox[3], window_deg=window,
        pos_zone_days=len(pz), fall_zone_days=int(pz["has_fall"].sum()) if len(pz) else 0,
        distinct_days=int(pz["date"].nunique()) if len(pz) else 0,
        storm_clusters=storm_clusters(pz["date"]) if len(pz) else 0,
        pos_zone_days_c5=len(pz5), pos_zone_days_no_eq=len(pz_no),
        n_zones_with_pos=int(pz[["zr", "zc"]].drop_duplicates().shape[0]) if len(pz) else 0,
    )


def rank_windows(pz: pd.DataFrame, window: float, step: float, top_k: int) -> list[tuple[float, float, float, float, int]]:
    """Sliding square windows (multiple of step) ranked by positive zone-days; greedy non-overlap.

    Returns (lat0, lat1, lon0, lon1, count). Uses a summed-area table on step-sized bins of zone centres.
    """
    if pz.empty:
        return []
    k = int(round(window / step))
    br = np.floor(pz["lat_c"].to_numpy() / step).astype(int)
    bc = np.floor(pz["lon_c"].to_numpy() / step).astype(int)
    r0, c0 = br.min(), bc.min()
    H = np.zeros((br.max() - r0 + 1 + k, bc.max() - c0 + 1 + k), dtype=np.int64)
    np.add.at(H, (br - r0, bc - c0), 1)
    S = np.zeros((H.shape[0] + 1, H.shape[1] + 1), dtype=np.int64)
    S[1:, 1:] = H.cumsum(0).cumsum(1)
    nr, nc = H.shape[0] - k + 1, H.shape[1] - k + 1
    W = S[k:k + nr, k:k + nc] - S[0:nr, k:k + nc] - S[k:k + nr, 0:nc] + S[0:nr, 0:nc]
    taken = np.zeros_like(H, dtype=bool)
    out = []
    order = np.argsort(W, axis=None)[::-1]
    for idx in order:
        i, j = np.unravel_index(idx, W.shape)
        cnt = int(W[i, j])
        if cnt <= 0 or len(out) >= top_k:
            break
        if taken[i:i + k, j:j + k].any():
            continue
        taken[i:i + k, j:j + k] = True
        lat0, lon0 = (i + r0) * step, (j + c0) * step
        out.append((lat0, lat0 + window, lon0, lon0 + window, cnt))
    return out


# --------------------------------------------------------------------------- splits
@dataclass
class SplitProposal:
    """Chronological split with gaps. Dates inclusive."""
    train: tuple[str, str]
    val: tuple[str, str]
    test: tuple[str, str]
    gap_days: int
    counts: dict[str, int]
    clusters: dict[str, int]
    lost_in_gaps: int


def coverage_start(dates: pd.Series, frac: float = 0.1) -> pd.Timestamp:
    """Start of active reporting (D-010): Jan 1 of the first year whose positive count is
    >= max(2, frac * median of nonzero annual counts). Earlier zone-days are not true negatives."""
    yc = pd.to_datetime(dates).dt.year.value_counts().sort_index()
    thr = max(2.0, frac * float(yc.median()))
    y0 = int(yc[yc >= thr].index.min()) if (yc >= thr).any() else int(yc.index.min())
    return pd.Timestamp(year=y0, month=1, day=1)


def propose_splits(pz: pd.DataFrame, fracs: tuple[float, float, float], gap_days: int,
                   start: dt.date, end: dt.date | None = None) -> SplitProposal | None:
    """Boundaries at cumulative positive-zone-day quantiles; 30-day gap after train and after val."""
    d = pd.to_datetime(pz["date"]).sort_values().reset_index(drop=True)
    d = d[d >= pd.Timestamp(start)]
    if len(d) < 10:
        return None
    start = max(pd.Timestamp(start), coverage_start(d))
    d = d[d >= start]
    end_ts = pd.Timestamp(end) if end else d.iloc[-1]
    n = len(d)
    b1 = d.iloc[int(np.floor(fracs[0] * n)) - 1]
    b2 = d.iloc[int(np.floor((fracs[0] + fracs[1]) * n)) - 1]
    g = pd.Timedelta(days=gap_days)
    one = pd.Timedelta(days=1)
    tr = (pd.Timestamp(start), b1)
    va = (b1 + g + one, b2)
    te = (b2 + g + one, end_ts)
    if va[0] > va[1] or te[0] > te[1]:
        return None

    def cnt(a: pd.Timestamp, b: pd.Timestamp) -> int:
        return int(((d >= a) & (d <= b)).sum())

    def cl(a: pd.Timestamp, b: pd.Timestamp) -> int:
        return storm_clusters(d[(d >= a) & (d <= b)])

    counts = {"train": cnt(*tr), "val": cnt(*va), "test": cnt(*te)}
    f = lambda t: t.strftime("%Y-%m-%d")  # noqa: E731
    return SplitProposal(
        train=(f(tr[0]), f(tr[1])), val=(f(va[0]), f(va[1])), test=(f(te[0]), f(te[1])),
        gap_days=gap_days, counts=counts,
        clusters={"train": cl(*tr), "val": cl(*va), "test": cl(*te)},
        lost_in_gaps=n - sum(counts.values()),
    )


# --------------------------------------------------------------------------- report
def _md_table(s: pd.Series | pd.DataFrame, name: str = "count") -> str:
    df = s.to_frame(name) if isinstance(s, pd.Series) else s
    df = df.reset_index()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def profile(clean: pd.DataFrame, rep: CleanReport, cfg: dict[str, Any], source_file: str) -> tuple[str, dict[str, Any]]:
    """Build markdown profile + machine-readable summary dict."""
    inv, pc = cfg["inventory"], cfg["profiling"]
    c_min, c_alt, min_year, deg = inv["c_min"], inv["c_alt"], inv["min_year"], pc["zone_deg"]
    md: list[str] = []
    A = md.append
    A("# Data profile — USGS Landslide Inventories across the US v3.0\n")
    A(f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from `{source_file}` by `rockwatch profile`.  ")
    A("Source: USGS, *Landslide Inventories across the United States* v3.0, DOI 10.5066/P14AJF8I (CC0).  ")
    A("**US natural-slope data; not open-pit mine performance.** Unreported events exist, so any precision derived later is a lower bound.\n")

    A("## 1. Cleaning summary\n")
    A(_md_table(pd.Series(asdict(rep)).drop("excluded_type_counts").astype(str), "value"))
    A("\nExcluded LS_Type values (top 30):\n")
    A(_md_table(pd.Series(rep.excluded_type_counts, dtype="int64"), "n") if rep.excluded_type_counts else "_none_")

    A("\n## 2. Counts (all confidence levels)\n")
    A("### date_kind\n" + _md_table(clean["date_kind"].value_counts()))
    A("\n### type_family\n" + _md_table(clean["type_family"].value_counts()))
    A("\n### Confidence\n" + _md_table(clean["confidence"].value_counts(dropna=False).sort_index()))
    A("\n### Raw LS_Type (top 40) → type_family\n")
    lt = clean.groupby(clean["LS_Type"].fillna("<empty>"))["type_family"].agg(["first", "size"]).sort_values("size", ascending=False).head(40)
    A(_md_table(lt.rename(columns={"first": "type_family", "size": "n"})))
    A("\n### Inventory (top 40)\n" + _md_table(clean["Inventory"].fillna("<empty>").value_counts().head(40)))
    dated = clean[clean["date_min"].notna()]
    dec = (dated["date_min"].dt.year // 10 * 10).value_counts().sort_index()
    A("\n### Decade of Date_Min (dated rows)\n" + _md_table(dec))
    A("\n### date_kind × Confidence\n" + _md_table(pd.crosstab(clean["date_kind"], clean["confidence"])))

    ev = dated_positives(clean, c_min, min_year)
    A(f"\n## 3. Exact-dated events since {min_year}\n")
    A(f"- C≥{c_min}: **{len(ev)}** events; C≥{c_alt}: **{len(dated_positives(clean, c_alt, min_year))}** events.")
    A(f"- C≥{c_min} by type_family:\n\n" + _md_table(ev["type_family"].value_counts()))
    A(f"\n- C≥{c_min} by Inventory (EQ-triggered marked *):\n\n" + _md_table(
        ev["Inventory"].fillna("<empty>").map(lambda x: x + (" *" if x in EQ_INVENTORIES else "")).value_counts()))
    A(f"\n- C≥{c_min} raw LS_Type (top 30) → family:\n\n" + _md_table(
        ev.groupby(ev["LS_Type"].fillna("<empty>"))["type_family"].agg(["first", "size"])
        .sort_values("size", ascending=False).head(30).rename(columns={"first": "type_family", "size": "n"})))
    A("\n- C≥%d by year (last 30 years with data):\n\n" % c_min + _md_table(ev["date_min"].dt.year.value_counts().sort_index().tail(30)))
    pz = positive_zone_days(ev, deg)
    A(f"\n- Positive zone-days ({deg}° cells, C≥{c_min}): **{len(pz)}**; "
      f"distinct dates: **{pz['date'].nunique() if len(pz) else 0}**; storm clusters (≤3 d): **{storm_clusters(pz['date']) if len(pz) else 0}**.")

    A("\n## 4. Candidate regions\n")
    A(f"Square windows of {pc['candidate_windows_deg']}° slid in {pc['window_step_deg']}° steps over {deg}° zone centres; "
      "greedy non-overlapping top windows per size. No state polygons (no geopandas); bbox is the region unit.\n")
    rank_by = pc.get("rank_by", "pos_zone_days")
    no_eq = rank_by == "pos_zone_days_no_eq"
    pz_rank = positive_zone_days(ev[~ev["Inventory"].isin(EQ_INVENTORIES)], deg) if no_eq else pz
    A(f"Ranked by `{rank_by}`.\n")
    regions: list[Region] = []
    for w in pc["candidate_windows_deg"]:
        for (a0, a1, o0, o1, _) in rank_windows(pz_rank, w, pc["window_step_deg"], pc["top_k_regions"]):
            regions.append(region_stats(clean, (a0, a1, o0, o1), w, c_min, c_alt, min_year, deg))
    regions.sort(key=lambda r: getattr(r, rank_by), reverse=True)
    rt = pd.DataFrame([asdict(r) for r in regions])
    if not rt.empty:
        A(_md_table(rt.set_index("lat0")))
    best_info: dict[str, Any] = {}
    A("\n## 5. Proposal (for CP1 confirmation)\n")
    start = dt.date(min_year, 1, 1)
    proposals = []
    for r in regions[:5]:
        sub = clean[in_bbox(clean, r.bbox())]
        rev = dated_positives(sub, c_min, min_year)
        if no_eq:
            rev = rev[~rev["Inventory"].isin(EQ_INVENTORIES)]
        rpz = positive_zone_days(rev, deg)
        sp = propose_splits(rpz, tuple(pc["split_fracs"]), pc["gap_days"], start)
        ok = sp is not None and getattr(r, rank_by) >= pc["min_positive_zone_days"] and sp.counts["test"] >= pc["min_test_zone_days"]
        proposals.append((r, sp, ok, rev, rpz))
    chosen = next((p for p in proposals if p[2]), proposals[0] if proposals else None)
    if chosen is None:
        A("**No region with dated positives found. Cannot propose.**")
    else:
        r, sp, ok, rev, rpz = chosen
        A(f"- Inventories in region positives: {rev['Inventory'].value_counts().to_dict()}; families: {rev['type_family'].value_counts().to_dict()}.")
        A(f"- **Region bbox**: lat [{r.lat0}, {r.lat1}), lon [{r.lon0}, {r.lon1}) ({r.window_deg}° window).")
        A(f"- Positive zone-days C≥{c_min}: {r.pos_zone_days} (C≥{c_alt}: {r.pos_zone_days_c5}; excl. EQ-triggered inventories: {r.pos_zone_days_no_eq}); "
          f"fall-family zone-days: {r.fall_zone_days}; storm clusters: {r.storm_clusters}.")
        A(f"- Meets heuristic (≥{pc['min_positive_zone_days']} total, ≥{pc['min_test_zone_days']} test): **{'yes' if ok else 'NO'}**.")
        if r.fall_zone_days < pc["min_positive_zone_days"]:
            A("- Fall-family too small for its own P/R → main P/R on all types; fall reported as subset (§6.2 rule 3).")
        if sp:
            A(f"- **Splits** (chronological, {sp.gap_days}-day gaps, ~{pc['split_fracs']} of positive zone-days):\n")
            st = pd.DataFrame({"start": [sp.train[0], sp.val[0], sp.test[0]], "end": [sp.train[1], sp.val[1], sp.test[1]],
                               "pos_zone_days": [sp.counts[k] for k in ("train", "val", "test")],
                               "storm_clusters": [sp.clusters[k] for k in ("train", "val", "test")]},
                              index=pd.Index(["train", "val", "test"], name="split"))
            A(_md_table(st))
            A(f"\n  Positive zone-days lost in gaps: {sp.lost_in_gaps}. Split counts use `{rank_by}` positives.")
            sub = clean[in_bbox(clean, r.bbox())]
            eqpz = positive_zone_days(dated_positives(sub[sub["Inventory"].isin(EQ_INVENTORIES)], c_min, min_year), deg)
            if len(eqpz):
                ed = pd.to_datetime(eqpz["date"])
                eqc = {k: int(((ed >= pd.Timestamp(getattr(sp, k)[0])) & (ed <= pd.Timestamp(getattr(sp, k)[1]))).sum()) for k in ("train", "val", "test")}
                A(f"  EQ-triggered zone-days in region (extra, per split): {eqc}; dates: {sorted(ed.dt.strftime('%Y-%m-%d').unique().tolist())[:15]}")
            fsub = rev[rev["type_family"] == "fall"]
            fpz = positive_zone_days(fsub, deg)
            if len(fpz):
                fd = pd.to_datetime(fpz["date"])
                fc = {k: int(((fd >= pd.Timestamp(getattr(sp, k)[0])) & (fd <= pd.Timestamp(getattr(sp, k)[1]))).sum()) for k in ("train", "val", "test")}
                A(f"  Fall-family zone-days per split: {fc}")
            yr = pd.to_datetime(rpz["date"]).dt.year.value_counts().sort_index()
            A("\n  Region positive zone-days by year:\n\n" + _md_table(yr))
        best_info = {"region": asdict(r), "splits": asdict(sp) if sp else None, "meets_heuristic": ok}
        A("\n### Other top candidates' split check\n")
        rows = [{"bbox": f"[{p[0].lat0},{p[0].lat1})×[{p[0].lon0},{p[0].lon1})", "rank_val": getattr(p[0], rank_by),
                 "fall_zd": p[0].fall_zone_days, "main_inventory": p[3]["Inventory"].value_counts().index[0] if len(p[3]) else "",
                 "train": "–".join(p[1].train) if p[1] else "", "val": "–".join(p[1].val) if p[1] else "",
                 "test": "–".join(p[1].test) if p[1] else "", "test_pos": p[1].counts["test"] if p[1] else None,
                 "test_clusters": p[1].clusters["test"] if p[1] else None, "ok": p[2]} for p in proposals]
        A(_md_table(pd.DataFrame(rows).set_index("bbox")))
    A("\n## 6. Caveats\n")
    A("- Dates are local time except EQ inventories (UTC); day-level matching tolerates ±1 d.")
    A("- Reporting density changes over decades (more recent events reported) → split counts not stationary.")
    A("- Inventory `Notes` are untrusted free text; never used in prompts.")
    summary = {"n_clean": len(clean), "n_exact_cmin": len(ev), "n_pos_zone_days": len(pz), "proposal": best_info,
               "regions": [asdict(r) for r in regions]}
    return "\n".join(md) + "\n", summary
