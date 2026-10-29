"""Read-only evidence stores behind the LLM tools (§9.4). BusStore = live (bus log); PanelStore = batch eval.
Both return identical dict shapes. Neither can see ground truth; inventory Notes are never included."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from rockwatch.fusion.model import RAW_GROUPS
from rockwatch.llm.provider import ToolSpec

READER = "llm_verifier"


def _r(x, nd=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if x != x else round(x, nd)


class BusStore:
    """Live: answers from the bus log (sqlite or memory)."""

    def __init__(self, bus, ctx):
        self.bus, self.ctx = bus, ctx
        self.prior = dict(zip(ctx.zones["zone_id"], ctx.zones["n_prior_features"]))

    def zone_evidence(self, zone_id: str, date: str) -> dict[str, Any]:
        fz = self.bus.read(READER, ["risk.fused"], sim_date=date, zone_id=zone_id, latest=True)
        if not fz:
            return {"error": f"no fused risk for {zone_id} {date}"}
        f = fz[0]
        ev = self.bus.read(READER, ["evidence.rain", "evidence.thermal", "evidence.seismic", "evidence.susceptibility"], sim_date=date, zone_id=zone_id)
        cx = self.bus.read(READER, ["evidence.context"], sim_date=date, latest=True)
        feats = {e.payload["group"]: {k: _r(v) for k, v in e.payload["features"].items()} for e in ev + cx}
        ids = [f.msg_id] + [e.msg_id for e in ev + cx]
        return {"zone_id": zone_id, "date": date, "p": _r(f.payload["p"]), "logit": _r(f.payload["logit"]),
                "provisional_level": f.payload["level"], "n_dynamic_positive": f.payload["n_dyn_pos"],
                "contributions": {k: _r(v) for k, v in f.payload["contributions"].items()}, "features": feats, "evidence_ids": ids}

    def regional_extent(self, date: str) -> dict[str, Any]:
        cx = self.bus.read(READER, ["evidence.context"], sim_date=date, latest=True)
        fz = self.bus.read(READER, ["risk.fused"], sim_date=date)
        return {"date": date, "regional_extent": _r(cx[0].payload["features"]["regional_extent"]) if cx else None,
                "zones_provisional_L2plus": sum(1 for e in fz if e.payload["level"] >= 2), "zones_total": len(fz),
                "evidence_ids": [cx[0].msg_id] if cx else []}

    def zone_history(self, zone_id: str, date: str) -> dict[str, Any]:
        d0 = (pd.Timestamp(date) - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
        st = self.bus.read(READER, ["alerts.active"], kind="daily_state", date_from=d0)
        days = [e for e in st if e.sim_date < date]
        return {"zone_id": zone_id, "train_and_undated_inventory_features": int(self.prior.get(zone_id, 0)),
                "alert_days_L2plus_last_14": sum(1 for e in days if e.payload["levels"].get(zone_id, 0) >= 2),
                "evidence_ids": [e.msg_id for e in days[-3:]]}

    def data_quality(self, zone_id: str, date: str) -> dict[str, Any]:
        fz = self.bus.read(READER, ["risk.fused"], sim_date=date, zone_id=zone_id, latest=True)
        qf = self.bus.read(READER, ["quality.flags"], sim_date=date)
        stale = sorted({e.payload["agent_id"] for e in self.bus.read(READER, ["quality.flags"], kind="agent_stale")}
                       - {e.payload["agent_id"] for e in self.bus.read(READER, ["quality.flags"], kind="agent_recovered")})
        q = fz[0].payload["quality"] if fz else {}
        return {"zone_id": zone_id, "date": date, "modality_quality": q, "quality_ok": bool(q) and all(v == "ok" for v in q.values()),
                "stale_agents": stale, "evidence_ids": [e.msg_id for e in qf if e.kind == "daily"][:1]}

    def snow_context(self, zone_id: str, date: str) -> dict[str, Any]:
        d0 = (pd.Timestamp(date) - pd.Timedelta(days=6)).strftime("%Y-%m-%d")
        rn = [e for e in self.bus.read(READER, ["sensor.rain"], zone_id=zone_id, date_from=d0) if e.sim_date <= date]
        th = self.bus.read(READER, ["sensor.thermal"], zone_id=zone_id, sim_date=date, latest=True)
        snow = [e.payload.get("snowfall_sum") for e in rn]
        return {"zone_id": zone_id, "date": date, "snowfall_cm_7d": _r(sum(x for x in snow if x is not None)) if snow else None,
                "days_reported": len(snow), "tmax_c": _r(th[0].payload.get("temperature_2m_max")) if th else None,
                "tmin_c": _r(th[0].payload.get("temperature_2m_min")) if th else None, "evidence_ids": [e.msg_id for e in rn[-2:]] + [e.msg_id for e in th]}


class PanelStore:
    """Batch: answers from the feature panel + model predictions + provisional levels."""

    def __init__(self, panel: pd.DataFrame, pred: pd.DataFrame, raw: np.ndarray, ndyn: np.ndarray, ctx):
        self.P = panel.assign(**{c: pred[c].to_numpy() for c in pred.columns}, raw=raw, ndyn=ndyn).set_index(["zone_id", "date"]).sort_index()
        self.ctx = ctx
        self.prior = dict(zip(ctx.zones["zone_id"], ctx.zones["n_prior_features"]))
        self.groups = list(ctx.model.groups)
        self.by_date = self.P.reset_index().groupby("date")

    def _row(self, z, d):
        return self.P.loc[(z, pd.Timestamp(d))]

    def zone_evidence(self, zone_id, date):
        try:
            r = self._row(zone_id, date)
        except KeyError:
            return {"error": f"no data for {zone_id} {date}"}
        feats = {g: {c: _r(r[c]) for c in RAW_GROUPS[g]} for g in self.groups}
        ids = [f"panel:{zone_id}:{date}:fused"] + [f"panel:{zone_id}:{date}:{g}" for g in self.groups]
        return {"zone_id": zone_id, "date": date, "p": _r(r["p"]), "logit": _r(r["logit"]), "provisional_level": int(r["raw"]),
                "n_dynamic_positive": int(r["ndyn"]), "contributions": {g: _r(r[f"c_{g}"]) for g in self.groups}, "features": feats,
                "evidence_ids": ids}

    def regional_extent(self, date):
        try:
            g = self.by_date.get_group(pd.Timestamp(date))
        except KeyError:
            return {"error": f"no data for {date}"}
        return {"date": date, "regional_extent": _r(g["regional_extent"].iloc[0]), "zones_provisional_L2plus": int((g["raw"] >= 2).sum()),
                "zones_total": int(len(g)), "evidence_ids": [f"panel:region:{date}:context"]}

    def zone_history(self, zone_id, date):
        d = pd.Timestamp(date)
        try:
            s = self.P.loc[zone_id]
        except KeyError:
            return {"error": f"unknown zone {zone_id}"}
        w = s[(s.index >= d - pd.Timedelta(days=14)) & (s.index < d)]
        return {"zone_id": zone_id, "train_and_undated_inventory_features": int(self.prior.get(zone_id, 0)),
                "alert_days_L2plus_last_14": int((w["raw"] >= 2).sum()), "evidence_ids": [f"panel:{zone_id}:history"]}

    def data_quality(self, zone_id, date):
        try:
            r = self._row(zone_id, date)
        except KeyError:
            return {"error": f"no data for {zone_id} {date}"}
        bad = int(r.get("wx_missing", 0))
        q = {g: ("degraded" if bad and g in ("rain", "thermal") else "ok") for g in self.groups}
        return {"zone_id": zone_id, "date": date, "modality_quality": q, "quality_ok": not bad, "stale_agents": [],
                "evidence_ids": [f"panel:{zone_id}:{date}:quality"]}

    def snow_context(self, zone_id, date):
        w = self.ctx.weather.get(zone_id)
        if w is None:
            return {"error": f"unknown zone {zone_id}"}
        d = pd.Timestamp(date)
        h = w[(w.index > d - pd.Timedelta(days=7)) & (w.index <= d)]
        return {"zone_id": zone_id, "date": date, "snowfall_cm_7d": _r(h["snowfall_sum"].sum()), "days_reported": int(len(h)),
                "tmax_c": _r(w.loc[d, "temperature_2m_max"]) if d in w.index else None,
                "tmin_c": _r(w.loc[d, "temperature_2m_min"]) if d in w.index else None, "evidence_ids": [f"panel:{zone_id}:{date}:snow"]}


def bundle(store, zone_id: str, date: str) -> dict[str, Any]:
    """All five tool results in one dict (pre-bundled evidence for non-tool providers, guardrail reference, cache key)."""
    b = {"zone_evidence": store.zone_evidence(zone_id, date), "regional": store.regional_extent(date),
         "history": store.zone_history(zone_id, date), "quality": store.data_quality(zone_id, date),
         "snow": store.snow_context(zone_id, date)}
    ids = []
    for v in b.values():
        ids += v.get("evidence_ids", [])
    ze = b["zone_evidence"]
    b["evidence_ids"] = ids
    b["p"] = ze.get("p")
    b["contributions"] = ze.get("contributions", {})
    b["quality_ok"] = b["quality"].get("quality_ok", False)
    return b


def tools(store) -> list[ToolSpec]:
    zd = {"type": "object", "properties": {"zone": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"}},
          "required": ["zone", "date"]}
    return [
        ToolSpec("get_zone_evidence", "Fused risk, per-modality contributions (log-odds) and features for a zone-day.", zd,
                 lambda zone, date: store.zone_evidence(zone, date)),
        ToolSpec("get_regional_extent", "How many zones are elevated on a date; regional rain extent.",
                 {"type": "object", "properties": {"date": {"type": "string"}}, "required": ["date"]},
                 lambda date: store.regional_extent(date)),
        ToolSpec("get_zone_history", "Training-period/undated inventory feature count and L2+ alert days in the previous 14 days.", zd,
                 lambda zone, date: store.zone_history(zone, date)),
        ToolSpec("get_data_quality", "Per-modality data quality and stale agents for a zone-day.", zd,
                 lambda zone, date: store.data_quality(zone, date)),
        ToolSpec("get_snow_context", "Snowfall in the last 7 days and today's Tmax/Tmin for a zone.", zd,
                 lambda zone, date: store.snow_context(zone, date)),
    ]
