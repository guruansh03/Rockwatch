"""RockWatch live dashboard (Streamlit). Reads the run's sqlite bus; writes only operator actions
(alerts.ack, agents.control fault injection). Launch via `rockwatch run-demo --scenario <name>`.
Ground-truth overlay (truth.events) is shown only for days that have closed."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rockwatch.config import load_config, repo_path  # noqa: E402
from rockwatch.dashboard import data as D  # noqa: E402
from rockwatch.schemas import Envelope  # noqa: E402

st.set_page_config(page_title="RockWatch-FuseGuard", layout="wide")
CFG = load_config()
FOOTER = ("Data: USGS *Landslide Inventories across the United States* v3.0 (DOI 10.5066/P14AJF8I, CC0); USGS DS746 Yosemite rock falls; "
          "USGS ComCat earthquakes. **Weather data by Open-Meteo.com** (CC BY 4.0). "
          "**US natural-slope / road-cut data — not mine performance. Precision is a lower bound (unreported events). "
          "Lead time in days; no time-of-failure prediction.**")


def pick_run() -> Path | None:
    env = os.getenv("ROCKWATCH_RUN_DIR")
    if env:
        return Path(env)
    runs = sorted(p for p in repo_path("data/runs").glob("*") if (p / "bus.sqlite").exists())
    return runs[-1] if runs else None


@st.cache_resource
def get_bus(path: str):
    from rockwatch.bus.sqlite_bus import SqliteBus
    return SqliteBus(path)


@st.cache_data
def get_zones(region: str) -> pd.DataFrame:
    import json
    proc = repo_path(CFG["paths"]["processed"]) / region
    z = pd.read_parquet(proc / "zones.parquet")
    miss = set(json.loads((proc / "build_summary.json").read_text(encoding="utf-8"))["zones_missing_weather"])
    return z[~z["zone_id"].isin(miss)].reset_index(drop=True)


run = pick_run()
st.title("RockWatch-FuseGuard — multi-agent landslide/rockfall early warning (historical replay)")
if run is None:
    st.warning("No run found. Start one with `python -m rockwatch run-demo --scenario dev_val`.")
    st.stop()
info = D.run_info(run)
bus = get_bus(str(run / "bus.sqlite"))
zones = get_zones(info["region"])
st.caption(f"Run `{run.name}` · region {info['region']} · {info['start']} → {info['end']} · {info['speed']} s/sim-day · LLM {info.get('llm', 'off')}")

with st.sidebar:
    st.header("Controls")
    live = st.toggle("Auto-refresh (2 s)", value=os.getenv("ROCKWATCH_AUTOREFRESH", "1") == "1")
    show_truth = st.toggle("Show ground-truth events (closed days)", value=True)
    st.divider()
    st.subheader("Fault injection")
    reg = {r["agent_id"]: r for r in bus.registry()}
    target = "sensor_rain_0"
    c1, c2 = st.columns(2)
    if c1.button("Kill RainSensor", help="terminate sensor_rain_0 → supervisor marks stale, fusion degraded"):
        try:
            os.kill(reg[target]["pid"], signal.SIGTERM)
            st.toast(f"killed {target}")
        except (KeyError, ProcessLookupError, OSError) as e:
            st.error(f"kill failed: {e}")
    if c2.button("Restart it"):
        p = subprocess.Popen(reg[target]["cmd"], cwd=str(ROOT))
        bus.bump_restart(target, p.pid)
        bus.publish(Envelope(topic="quality.flags", agent_id="dashboard", kind="agent_restarted", payload={"agent_id": target, "new_pid": p.pid}))
        st.toast(f"restarted {target} (pid {p.pid})")
    off = st.toggle("LLM offline", value=False, help="verifier → deterministic fallback; composer → template")
    if st.session_state.get("_llm_off") != off:
        st.session_state["_llm_off"] = off
        bus.publish(Envelope(topic="agents.control", agent_id="dashboard", kind="llm_offline", payload={"on": off}))
    dz = st.selectbox("Drop a zone's sensor data", ["(none)"] + list(zones["zone_id"]))
    if st.session_state.get("_drop") != dz:
        prev = st.session_state.get("_drop")
        if prev and prev != "(none)":
            bus.publish(Envelope(topic="agents.control", agent_id="dashboard", kind="drop_zone", payload={"zone_id": prev, "on": False}))
        if dz != "(none)":
            bus.publish(Envelope(topic="agents.control", agent_id="dashboard", kind="drop_zone", payload={"zone_id": dz, "on": True}))
        st.session_state["_drop"] = dz


def banner():
    state = D.latest_state(bus)
    day = state.sim_date if state else None
    stale = D.stale_agents(bus)
    deg = D.degraded_today(bus, day)
    cols = st.columns(4)
    cols[0].metric("Sim day", day or "—")
    lv = pd.Series(state.payload["levels"]).value_counts() if state else pd.Series(dtype=int)
    cols[1].metric("Zones L2+", int(lv[lv.index >= 2].sum()) if len(lv) else 0, help="L2 Warning: restrict access below slopes")
    cols[2].metric("Unacked L2+", len(state.payload.get("unacked", [])) if state else 0)
    cols[3].metric("Degraded zone-risks today", deg)
    if stale:
        st.error(f"DEGRADED: stale agents {stale} — dependent evidence missing; fusion uses remaining modalities.")
    return state


def tab_map(state):
    import pydeck as pdk
    zt = D.zone_table(zones, state, CFG["zones"]["deg"])
    layers = [pdk.Layer("PolygonLayer", zt, get_polygon="polygon", get_fill_color="color", get_line_color=[60, 60, 60], line_width_min_pixels=1,
                        pickable=True, stroked=True)]
    if show_truth and state:
        tm = D.truth_markers(bus, state.sim_date, 14, zones)
        if len(tm):
            layers.append(pdk.Layer("ScatterplotLayer", tm, get_position="[lon, lat]", get_radius=2500, get_fill_color=[20, 20, 200, 220], pickable=True))
    view = pdk.ViewState(latitude=float(zones["lat"].mean()), longitude=float(zones["lon"].mean()), zoom=7)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=None,
                             tooltip={"text": "{zone_id}\n{label}\np={p}"}))
    st.caption("Colours: green L0 · yellow L1 Watch · orange L2 Warning · red L3 Alarm. Blue dots: inventory events of closed days (last 14).")


def tab_zone(state):
    import plotly.graph_objects as go
    zid = st.selectbox("Zone", list(zones["zone_id"]), key="zone_sel")
    df = D.zone_series(bus, zid)
    if df.empty:
        st.info("no data yet")
        return
    fig = go.Figure()
    fig.add_bar(x=df["date"], y=df["P1"], name="P1 (mm)")
    fig.add_bar(x=df["date"], y=df["P3"], name="P3 (mm)")
    fig.add_scatter(x=df["date"], y=df["P15"], name="P15 (mm)", mode="lines")
    if "seattle_P3_threshold_mm" in df:
        fig.add_scatter(x=df["date"], y=df["seattle_P3_threshold_mm"], name="Seattle CT: P3 needed (designed for Seattle)", line={"dash": "dash"})
    fig.update_layout(height=320, barmode="group", margin={"t": 30})
    st.plotly_chart(fig, use_container_width=True)
    c = [x for x in df.columns if x.startswith("c_")]
    if c:
        last = df.dropna(subset=["p"]).iloc[-1]
        st.subheader(f"Why — per-modality contributions (log-odds) on {last['date'].date()}  ·  p = {last['p']:.3f}  ·  L{int(last['level'])}")
        st.bar_chart(pd.Series({k[2:]: last[k] for k in c}))
        f2 = go.Figure()
        f2.add_scatter(x=df["date"], y=df["p"], name="p (calibrated)")
        th = load_model_thresholds(info["region"])
        for k in ("t1", "t2", "t3"):
            if th.get(k):
                f2.add_hline(y=th[k], line_dash="dot", annotation_text=k)
        f2.update_layout(height=260, margin={"t": 20})
        st.plotly_chart(f2, use_container_width=True)


@st.cache_data
def load_model_thresholds(region):
    import json
    m = json.loads((repo_path(CFG["paths"]["processed"]) / region / "models" / "full.json").read_text(encoding="utf-8"))
    return {k: v for k, v in m["thresholds"].items() if k in ("t1", "t2", "t3", "l3_enabled")}


def tab_alerts(state):
    feed = D.alerts_feed(bus)
    if not feed:
        st.info("no alerts yet")
    unacked = set(state.payload.get("unacked", [])) if state else set()
    eps = state.payload.get("episodes", {}) if state else {}
    for a in feed[:25]:
        pl = a["payload"]
        lvl = pl.get("to", pl.get("level"))
        with st.container(border=True):
            st.markdown(f"**{a['date']} · zone {a['zone_id']} · {a['kind']} → {D.LEVEL_NAMES.get(lvl, lvl)}**"
                        + (f" · p={pl['p']:.3f}" if pl.get("p") is not None else ""))
            m = a["message"]
            if m:
                st.markdown(f"_{m.get('headline')}_  \n{m.get('body')}  \nActions: " + "; ".join(m.get("actions", [])) + f"  \n`source: {m.get('source')}`")
            v = a["verifier"]
            if v and v.get("decision") not in (None, "PASS"):
                st.markdown(f"Verifier: **{v.get('decision')}** ({v.get('verifier', v.get('mode'))}) L{v.get('level_in')}→L{v.get('level_out')}"
                            + (f" — {v.get('rationale')}" if v.get("rationale") else ""))
            z = a["zone_id"]
            if z in unacked and eps.get(z) and st.button("Ack", key=f"ack_{a['seq']}"):
                bus.publish(Envelope(topic="alerts.ack", agent_id="dashboard", zone_id=z, sim_date=a["date"],
                                     payload={"episode_id": eps[z]["id"], "by": "operator"}))
                st.toast(f"acked {eps[z]['id']}")


def tab_agents(state):
    st.dataframe(D.agent_table(bus), use_container_width=True, hide_index=True)
    st.subheader("LLM call log")
    st.dataframe(D.llm_log(bus), use_container_width=True, hide_index=True)


def tab_eval():
    reps = sorted(p for p in repo_path(CFG["paths"]["reports"]).glob("eval_*") if (p / "metrics.md").exists())
    live = bus.read("dashboard", ["eval.live"], latest=True)
    if live:
        st.subheader("Live running metrics (this replay — illustrative only)")
        st.json({k: v for k, v in live[0].payload.items()})
    if not reps:
        st.info("no evaluation reports yet (`rockwatch eval --split val`)")
        return
    sel = st.selectbox("Report", [p.name for p in reps][::-1])
    rp = repo_path(CFG["paths"]["reports"]) / sel
    st.markdown((rp / "metrics.md").read_text(encoding="utf-8"))
    c1, c2 = st.columns(2)
    if (rp / "pr_curve.png").exists():
        c1.image(str(rp / "pr_curve.png"))
    if (rp / "lead_days.png").exists():
        c2.image(str(rp / "lead_days.png"))
    if (rp / "ablation.md").exists():
        st.markdown((rp / "ablation.md").read_text(encoding="utf-8"))


def tab_ask():
    from rockwatch.agents.llm_analyst import AnalystStore, answer
    from rockwatch.llm.runtime import LLMRuntime
    q = st.text_input("Ask the analyst (answers only from logged records, with record ids)")
    use_llm = st.toggle("Use LLM provider (else record lookup only)", value=info.get("llm") == "on")
    if q:
        try:
            rt = LLMRuntime(CFG, "writer") if use_llm and not st.session_state.get("_llm_off") else None
        except Exception as e:  # noqa: BLE001
            st.warning(f"LLM unavailable ({e}); record lookup only")
            rt = None
        a = answer(rt, AnalystStore(bus, CFG), q)
        st.markdown(a["answer"])
        st.caption(f"source: {a['source']} · citations: {a.get('citations')}")


def body():
    state = banner()
    t = st.tabs(["Map", "Zone detail", "Alerts", "Agents", "Evaluation", "Ask Analyst"])
    with t[0]:
        tab_map(state)
    with t[1]:
        tab_zone(state)
    with t[2]:
        tab_alerts(state)
    with t[3]:
        tab_agents(state)
    with t[4]:
        tab_eval()
    with t[5]:
        tab_ask()


if live:
    st.fragment(run_every=2)(body)()
else:
    body()
st.divider()
st.markdown(FOOTER)
