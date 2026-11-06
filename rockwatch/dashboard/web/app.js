/* RockWatch control room — client. Polls the local API; renders map, timeline, alerts, zone detail,
   agents/faults, evaluation and analyst. All untrusted text (LLM output, inventory-derived fields) is set
   via textContent. */
(function () {
  "use strict";
  const C = window.RWCharts;
  const $ = (q, r = document) => r.querySelector(q);
  const $$ = (q, r = document) => Array.from(r.querySelectorAll(q));
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const LEVEL = ["L0 Normal", "L1 Watch", "L2 Warning", "L3 Alarm"];
  const S = { run: null, meta: null, state: null, prevLevels: {}, seq: -1, tab: "overview", zone: null, hist: [],
              alerts: [], filter: "all", metric: "recall_at", report: null, reports: [], polling: null, lastAgents: 0,
              seenAlerts: new Set(), firstAlerts: true, hb: {}, view: null, base: "terrain", group: true };
  try { S.base = localStorage.getItem("rw-base") || "terrain"; S.group = localStorage.getItem("rw-group") !== "0"; } catch (e) { /* storage may be blocked */ }
  const dayDiff = (a, b) => (Date.parse(b) - Date.parse(a)) / 864e5;
  const thClose = (th) => !!(th && th.t2 && th.t3 && Math.abs(th.t3 - th.t2) < 0.01 * th.t2);

  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.textContent = text; return e; }
  async function api(path, body) {
    const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    const r = await fetch(path, opt);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  }
  const q = (o) => "?" + new URLSearchParams(Object.fromEntries(Object.entries(o).filter(([, v]) => v !== null && v !== undefined))).toString();
  const pct = (v) => v === null || v === undefined ? "—" : (v * 100).toFixed(1) + "%";

  /* ---------------- toasts ---------------- */
  function toast(text, kind = "") {
    const t = el("div", "toast " + kind);
    t.append(el("span", "bar"), el("span", "", text));
    $("#toasts").appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, 4200);
  }

  /* ---------------- animated numbers ---------------- */
  function tween(node, to, format) {
    const from = parseFloat(node.dataset.v || "0");
    node.dataset.v = to;
    if (to === null || to === undefined || Number.isNaN(to)) { node.textContent = "—"; return; }
    if (from === to) { node.textContent = format(to); return; }
    const t0 = performance.now(), dur = 520;
    const kpi = node.closest(".kpi"); if (kpi) { kpi.classList.remove("bump"); void kpi.offsetWidth; kpi.classList.add("bump"); }
    const step = (t) => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); node.textContent = format(from + (to - from) * e); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  /* ---------------- theme ---------------- */
  function setTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("rw-theme", t); } catch (e) { /* storage may be blocked */ }
    renderTrack();
    if (S.hist.length) renderTimeline(true);
    if (S.tab === "zone") loadZone();
    if (S.tab === "eval" && S.report) renderReport(S.report);
    paintZones(true);
  }
  $("#themeBtn").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  try { const t = localStorage.getItem("rw-theme"); if (t) document.documentElement.dataset.theme = t; else if (matchMedia("(prefers-color-scheme: dark)").matches) document.documentElement.dataset.theme = "dark"; } catch (e) { /* ignore */ }

  /* ---------------- tabs ---------------- */
  function moveInk() {
    const b = $(`.tabs button[data-tab="${S.tab}"]`), ink = $("#tabInk");
    if (!b) return;
    ink.style.left = b.offsetLeft + "px"; ink.style.width = b.offsetWidth + "px";
  }
  function setTab(t) {
    S.tab = t;
    $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === t)));
    $$(".view").forEach((v) => v.classList.toggle("is-active", v.id === "view-" + t));
    moveInk();
    if (t === "overview") { setTimeout(() => map.leaflet && map.leaflet.invalidateSize(), 60); renderTimeline(true); }
    if (t === "zone") loadZone();
    if (t === "alerts") renderFeed();
    if (t === "agents") loadAgents();
    if (t === "eval") loadReports();
    if (t === "analyst") $("#askInput").focus();
  }
  $$(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
  $$("[data-goto]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.goto)));
  window.addEventListener("resize", debounce(() => { moveInk(); renderTimeline(true); renderTrack(); if (S.tab === "zone") loadZone(); if (S.tab === "eval" && S.report) renderReport(S.report); }, 200));
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea")) return;
    const k = ["overview", "zone", "alerts", "agents", "eval", "analyst"][parseInt(e.key, 10) - 1];
    if (k) { setTab(k); e.preventDefault(); }
    if (e.key === " ") { togglePause(); e.preventDefault(); }
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") { stepView(e.key === "ArrowLeft" ? -1 : 1); e.preventDefault(); }
    if (e.key === "Escape" && S.view) { setView(null); e.preventDefault(); }
  });
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  /* ---------------- map (Leaflet, SVG fallback) ---------------- */
  const map = {
    leaflet: null, cells: {}, truth: null, tiles: null,
    init() {
      const host = $("#map");
      host.innerHTML = ""; this.cells = {};
      const zs = S.meta.zones, d = S.meta.deg;
      if (window.L) {
        if (this.leaflet) this.leaflet.remove();
        const m = L.map(host, { zoomControl: true, attributionControl: true, preferCanvas: false, zoomSnap: 0.25 });
        this.leaflet = m;
        this.setTiles();
        const bounds = [];
        zs.forEach((z) => {
          let r;
          if (S.meta.single_zone) {
            // DS746 has no coordinates: the whole valley is one zone — drawn as a ~4 km disc at its centroid, not a grid cell
            r = L.circle([z.lat, z.lon], { radius: 4000, weight: 2, color: css("--l0"), fillOpacity: 0.35, fillColor: css("--l0"), className: "zone-cell" }).addTo(m);
            r._single = true;
            L.marker([z.lat, z.lon], { icon: L.divIcon({ className: "zone-label", html: `<span>${S.meta.region_name.split(",")[0]} · single zone</span>`, iconSize: [0, 0] }), interactive: false, keyboard: false }).addTo(m);
            const dl = 9000 / 111320, dn = dl / Math.cos(z.lat * Math.PI / 180);   // ~9 km frame around the disc
            bounds.push([z.lat - dl, z.lon - dn], [z.lat + dl, z.lon + dn]);
          } else {
            const b = [[z.lat - d / 2, z.lon - d / 2], [z.lat + d / 2, z.lon + d / 2]];
            bounds.push(...b);
            r = L.rectangle(b, { weight: 1, color: css("--surface"), fillOpacity: 0.55, fillColor: css("--l0"), className: "zone-cell" }).addTo(m);
          }
          r.bindTooltip(() => this.tip(z), { className: "zone-tip", sticky: true, direction: "top", opacity: 1 });
          r.on("click", () => { S.zone = z.zone_id; setTab("zone"); });
          this.cells[z.zone_id] = r;
        });
        this.truth = L.layerGroup().addTo(m);
        m.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
      } else {
        this.svgFallback(host, zs, d);
      }
    },
    setTiles() {
      $$("#baseSeg button").forEach((b) => b.classList.toggle("is-on", b.dataset.base === S.base));
      $("#map").classList.toggle("base-off", S.base === "off");
      if (!this.leaflet) return;
      if (this.tiles) { this.leaflet.removeLayer(this.tiles); this.tiles = null; }
      const cfg = BASES[S.base];
      $("#basemapCredit").textContent = cfg ? "Basemap: " + cfg.credit : "Basemap off";
      if (!cfg) return;
      let ok = 0, bad = 0;
      // keyless providers (no API key); attribution shown in the map corner and footer
      const t = L.tileLayer(cfg.url, { subdomains: cfg.sub || "abc", maxZoom: cfg.max, attribution: cfg.credit });
      t.on("tileload", () => { ok++; });
      t.on("tileerror", () => {
        bad++;
        if (!ok && bad === 6 && this.tiles === t) {
          const next = S.base === "terrain" ? "streets" : "off";
          toast(`${cfg.label} basemap unreachable — ${next === "off" ? "showing zones only" : "switching to " + BASES[next].label}`, "err");
          setBase(next, false);
        }
      });
      this.tiles = t.addTo(this.leaflet);
      t.bringToBack();
    },
    tip(z) {
      const st = S.state || {}, lv = (st.levels || {})[z.zone_id] || 0, p = (st.p || {})[z.zone_id];
      return `<b>${z.zone_id}</b> · ${LEVEL[lv]}<br>p = <b>${p === undefined || p === null ? "—" : p.toFixed(4)}</b>${z.n_prior >= 0 ? `<br>${z.n_prior} prior inventory features` : ""}`;
    },
    svgFallback(host, zs, d) {
      const NS = "http://www.w3.org/2000/svg";
      const lats = zs.map((z) => z.lat), lons = zs.map((z) => z.lon);
      const pad = d, x0 = Math.min(...lons) - pad, x1 = Math.max(...lons) + pad, y0 = Math.min(...lats) - pad, y1 = Math.max(...lats) + pad;
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", `0 0 ${(x1 - x0) * 100} ${(y1 - y0) * 100}`); svg.setAttribute("class", "svgmap");
      zs.forEach((z) => {
        const r = document.createElementNS(NS, "rect");
        r.setAttribute("x", (z.lon - d / 2 - x0) * 100); r.setAttribute("y", (y1 - z.lat - d / 2) * 100);
        r.setAttribute("width", d * 100 - 2); r.setAttribute("height", d * 100 - 2); r.setAttribute("rx", 2);
        r.setAttribute("class", "zone-cell"); r.style.fill = css("--l0");
        r.addEventListener("click", () => { S.zone = z.zone_id; setTab("zone"); });
        const t = document.createElementNS(NS, "title"); t.textContent = z.zone_id; r.appendChild(t);
        svg.appendChild(r); this.cells[z.zone_id] = { svg: r };
      });
      host.appendChild(svg);
      const note = el("div", "hint", "Basemap unavailable offline — showing zone grid only."); note.style.padding = "6px"; host.appendChild(note);
    },
    paint(levels, force) {
      const cols = [css("--l0"), css("--l1"), css("--l2"), css("--l3")];
      Object.entries(this.cells).forEach(([zid, cell]) => {
        const lv = levels[zid] || 0, prev = S.prevLevels[zid] || 0;
        if (!force && lv === prev && cell._painted) return;
        cell._painted = true;
        const fill = cols[lv], op = lv === 0 ? 0.35 : 0.72;
        if (cell.svg) { cell.svg.style.fill = fill; cell.svg.style.fillOpacity = op; }
        else if (cell._single) cell.setStyle({ fillColor: fill, fillOpacity: lv === 0 ? 0.3 : 0.6, color: fill, weight: 2 });
        else cell.setStyle({ fillColor: fill, fillOpacity: op, color: lv >= 2 ? cols[lv] : css("--surface"), weight: lv >= 2 ? 1.5 : 1 });
        if (!force && lv > prev && lv >= 2) this.pulse(zid, cols[lv]);
        const pathEl = cell.getElement && cell.getElement();
        if (pathEl && !cell._single) pathEl.classList.toggle("is-selected", zid === S.zone);
      });
    },
    pulse(zid, color) {
      if (!this.leaflet) return;
      const z = S.meta.zones.find((x) => x.zone_id === zid); if (!z) return;
      const icon = L.divIcon({ className: "pulse-icon", html: `<span style="--c:${color}"></span><span style="--c:${color}"></span>`, iconSize: [0, 0] });
      const m = L.marker([z.lat, z.lon], { icon, interactive: false, keyboard: false }).addTo(this.leaflet);
      setTimeout(() => m.remove(), 3600);
    },
    async truthLayer() {
      if (!this.leaflet || !this.truth) return;
      if (!$("#truthToggle").checked) { this.truth.clearLayers(); this._truthKey = ""; return; }
      const ev = await api("/api/truth" + q({ run: S.run, days: 14, day: S.view })).catch(() => []);
      const key = ev.map((e) => e.zone + e.date).join("|");
      if (key === this._truthKey) return;
      const seen = new Set((this._truthKey || "").split("|"));
      this._truthKey = key; this.truth.clearLayers();
      const by = {};
      ev.forEach((e) => { if (e.lat === null) return; (by[e.zone] = by[e.zone] || { e, list: [], fresh: false }).list.push(e); if (!seen.has(e.zone + e.date)) by[e.zone].fresh = true; });
      Object.values(by).forEach(({ e, list, fresh }) => {
        const n = list.length;
        const icon = L.divIcon({ className: "truth-icon", html: `<i${fresh ? "" : ' style="animation:none"'}></i>${n > 1 ? `<b>${n}</b>` : ""}`, iconSize: [16, 16], iconAnchor: [8, 8] });
        const rows = list.slice(-6).reverse().map((x) => `${x.date} · ${x.type || "unknown type"}`).join("<br>");
        L.marker([e.lat, e.lon], { icon, keyboard: false, zIndexOffset: 500 })
          .bindTooltip(`<b>${e.zone}</b> · ${n} reported event${n > 1 ? "s" : ""} (last 14 days)<br>${rows}`, { className: "zone-tip", direction: "top" }).addTo(this.truth);
      });
    },
  };
  const BASES = {
    terrain: { label: "Terrain", url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", sub: "abc", max: 17,
               credit: "© OpenStreetMap contributors, SRTM · style © OpenTopoMap (CC-BY-SA)" },
    streets: { label: "Streets", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", sub: "abc", max: 19, credit: "© OpenStreetMap contributors" },
  };
  function setBase(b, persist = true) {
    S.base = BASES[b] ? b : "off";
    if (persist) { try { localStorage.setItem("rw-base", S.base); } catch (e) { /* ignore */ } }
    map.setTiles();
  }
  $$("#baseSeg button").forEach((b) => b.addEventListener("click", () => setBase(b.dataset.base)));
  function paintZones(force) { if (S.state && S.meta) map.paint(S.state.levels || {}, force); }
  $("#truthToggle").addEventListener("change", () => map.truthLayer());

  /* ---------------- run lifecycle ---------------- */
  S.follow = !new URLSearchParams(location.search).get("run");   // no explicit run → follow the newest run
  async function refreshRuns() {
    const runs = await api("/api/runs").catch(() => null);
    if (!runs || !runs.length) return;
    const sel = $("#runSelect");
    const sig = runs.map((r) => r.name + (r.finished ? "1" : "0")).join("|");
    if (sig !== S.runSig) { const cur = sel.value; fillRuns(runs); sel.value = cur; }
    if (S.follow && runs[0].name !== S.run) { toast(`New run ${runs[0].name} — switching`, "ok"); sel.value = runs[0].name; openRun(runs[0].name); }
  }
  setInterval(refreshRuns, 4000);
  async function loadRuns(select) {
    const runs = await api("/api/runs");
    const sel = $("#runSelect");
    fillRuns(runs);
    if (!runs.length) { setStatus("error", "no runs"); $("#map").innerHTML = '<div class="chart-empty">No replay runs yet. Start one with <code>python -m rockwatch run-demo --scenario dev_val</code>.</div>'; return; }
    const want = select || new URLSearchParams(location.search).get("run") || runs[0].name;
    sel.value = runs.some((r) => r.name === want) ? want : runs[0].name;
    await openRun(sel.value);
  }
  function runLabel(r) {
    const m = /_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})\d{2}$/.exec(r.name);
    const when = m ? ` · run ${m[2]}-${m[3]} ${m[4]}:${m[5]}` : "";
    return `${r.region_short || r.region} · ${r.start} → ${(r.end || "").slice(5)}${when}${r.finished ? "" : " · LIVE"}`;
  }
  function fillRuns(runs) {
    const sel = $("#runSelect"); sel.innerHTML = "";
    S.runSig = runs.map((r) => r.name + (r.finished ? "1" : "0")).join("|");
    runs.forEach((r) => { const o = el("option", "", runLabel(r)); o.value = r.name; o.title = `${r.name} · scenario ${r.scenario} · ${r.speed} s/day · LLM ${r.llm}`; sel.appendChild(o); });
  }
  $("#runSelect").addEventListener("change", (e) => { S.follow = false; openRun(e.target.value); });

  async function openRun(name) {
    S.run = name; S.seq = -1; S.prevLevels = {}; S.hist = []; S.seenAlerts = new Set(); S.firstAlerts = true; S.view = null;
    $("#timeline").dataset.drawn = "";
    if (!S.follow) history.replaceState(null, "", "?run=" + encodeURIComponent(name));
    S.meta = await api("/api/meta" + q({ run: name }));
    $("#regionName").textContent = S.meta.region_name;
    $("#kpiZones").textContent = `of ${S.meta.zones.length} zones`;
    $("#mapSub").textContent = S.meta.single_zone ? "single valley zone (DS746 rockfalls carry no coordinates) · level after hysteresis" : `${S.meta.zones.length} zones of ${S.meta.deg}° · level after hysteresis`;
    $("#trackStart").textContent = S.meta.info.start.slice(5); $("#trackEnd").textContent = S.meta.info.end.slice(5);
    $("#runSelect").title = `${name} · ${S.meta.split_of_run} split`;
    $("#timelineSub").textContent = S.meta.single_zone ? "daily p (line) over the level of each day · ◆ reported events · click a day" : "zones per level each sim-day · ◆ reported events · click a day";
    const th = S.meta.thresholds || {}, tn = $("#thNote");
    tn.hidden = !thClose(th);
    if (thClose(th)) tn.textContent = `For this region t2 (${th.t2.toFixed(4)}) ≈ t3 (${th.t3.toFixed(4)}). A day above t2 becomes L3 when corroborated (≥ 2 dynamic modalities positive, or a verifier CONFIRM); without corroboration it stays L2 — so L2 is rare here.`;
    $("#footBanner").textContent = S.meta.banner + " Lead time in days; no time-of-failure prediction.";
    $("#askLlm").checked = S.meta.info.llm === "on";
    const zs = $("#zoneSelect"), dz = $("#dropZone");
    zs.innerHTML = ""; dz.innerHTML = '<option value="">none</option>';
    [...S.meta.zones].sort((a, b) => b.n_prior - a.n_prior).forEach((z) => {
      const o = el("option", "", z.n_prior >= 0 ? `${z.zone_id}  (${z.n_prior})` : z.zone_id); o.value = z.zone_id; zs.appendChild(o);
      const o2 = el("option", "", z.zone_id); o2.value = z.zone_id; dz.appendChild(o2);
    });
    if (!S.zone || !S.meta.zones.some((z) => z.zone_id === S.zone)) S.zone = zs.value;
    zs.value = S.zone;
    map.init();
    await tick(true);
    if (S.polling) clearInterval(S.polling);
    S.polling = setInterval(() => tick(false), 1000);
  }

  function setStatus(s, label) {
    const p = $("#statusPill"); p.dataset.s = s; $(".label", p).textContent = label || s;
    $("#playBtn").classList.toggle("is-paused", s === "paused");
    $("#playBtn").disabled = s === "finished" || s === "error";
  }

  async function tick(first, repaint) {
    let st;
    try { st = await api("/api/state" + q({ run: S.run, day: S.view })); }
    catch (e) { setStatus("error", "offline"); return; }
    S.state = st;
    setStatus(st.status, st.status);
    $("#simDate").textContent = st.day || "—";
    const total = S.meta.days_total;
    $("#simIndex").textContent = `day ${st.day_index || 0} / ${total}`;
    $("#liveBtn").hidden = !S.view;
    $("#viewLabel").textContent = S.view ? `viewing ${S.view}` : "";
    document.body.classList.toggle("is-viewing", !!S.view);
    speedUi(st);
    const recall = st.live_eval ? st.live_eval.recall_at : null;
    [["n_l2", st.n_l2], ["n_l3", st.n_l3], ["unacked", (st.unacked || []).length], ["degraded", st.degraded], ["llm_calls", st.llm_calls], ["recall", recall]].forEach(([k, v]) => {
      const n = $(`[data-kpi="${k}"]`); tween(n, v, n.dataset.format === "pct" ? pct : (x) => Math.round(x).toString());
    });
    $("[data-kpi=n_l2]").closest(".kpi").classList.toggle("is-hot", st.n_l2 > 0);
    $("[data-kpi=n_l3]").closest(".kpi").classList.toggle("is-hot", st.n_l3 > 0);
    $("[data-kpi=degraded]").closest(".kpi").classList.toggle("is-bad", st.degraded > 0);
    $("#kpiStale").textContent = st.stale.length ? `stale: ${st.stale.join(", ")}` : st.degraded ? "agents healthy · gaps in evidence windows" : "all agents healthy";
    const le = st.live_eval;
    $("#kpiRecall").textContent = le && le.event_days ? `${le.tp_at} of ${le.event_days} event-days caught` : "no reported events yet";
    if (le && le.alert_day_fraction !== null && le.alert_day_fraction !== undefined) {
      const f = le.alert_day_fraction, rnd = 1 - Math.pow(1 - f, 2);
      $("#kpiRecall2").textContent = `${pct(f)} alert-days · random ≈ ${pct(rnd)}`;
      $("#kpiRecall2").title = "Expected recall (at) of independent random alerts raised on the same share of zone-days: 1 − (1 − f)²";
    } else $("#kpiRecall2").textContent = "";
    llmPill(st);
    $("#llmOffline").checked = !!st.llm_offline;
    banner(st);
    const changed = st.seq !== S.seq;
    if (changed || first || repaint) {
      map.paint(st.levels || {}, first || repaint || !!S.view);
      S.prevLevels = Object.assign({}, st.levels || {});
      if (changed || first) {
        S.seq = st.seq;
        const [hist, alerts] = await Promise.all([api("/api/history" + q({ run: S.run })), api("/api/alerts" + q({ run: S.run, limit: 400 }))]);
        S.hist = hist; S.alerts = alerts;
      }
      renderTimeline(first); renderMiniFeed(); renderTrack();
      if (S.tab === "alerts") renderFeed();
      if (changed || first) notifyNew(S.alerts);
      if (S.tab === "zone") loadZone();
      map.truthLayer();
    }
    if (S.tab === "agents" && Date.now() - S.lastAgents > 1800) loadAgents();
  }

  /* ---------------- replay track, day inspection, speed ---------------- */
  function renderTrack() { if (S.meta) C.track($("#track"), S.hist, { total: S.meta.days_total, view: S.view, onPick: (d, last) => setView(last ? null : d, true) }); }
  const reloadView = debounce(() => tick(false, true), 90);
  function setView(day, fromTrack) {
    if (day === S.view) return;
    S.view = day;
    if (!fromTrack) renderTrack();
    renderTimeline(true);
    reloadView();
  }
  function stepView(dlt) {
    if (!S.hist.length) return;
    let i = S.view ? S.hist.findIndex((h) => h.day === S.view) : S.hist.length - 1;
    i = Math.max(0, Math.min(S.hist.length - 1, i + dlt));
    setView(i === S.hist.length - 1 ? null : S.hist[i].day);
  }
  $("#liveBtn").addEventListener("click", () => setView(null));
  function llmPill(st) {
    const info = S.meta.info || {}, setup = S.meta.llm_setup || {}, seen = st.llm_model_seen;
    let k, label, tip;
    if (info.llm !== "on") { k = "off"; label = "OFF"; tip = "Run started with --llm off: deterministic verifier level, template messages."; }
    else if (seen) {
      const pv = st.llm_provider_seen || (/^mock/.test(seen) ? "mock" : /^claude/.test(seen) ? "anthropic" : "ollama");
      k = pv === "mock" ? "mock" : "claude";
      label = { mock: "MOCK", anthropic: "CLAUDE", groq: "GROQ", ollama: "LOCAL" }[pv] || pv.toUpperCase();
      tip = `Model in this run's call log: ${seen}` + (k === "mock" ? " — rule-based stand-in, not a real LLM." : ` (${pv})`);
    } else {
      const pv = setup.provider || "mock", keyed = pv === "anthropic" || pv === "groq";
      k = keyed ? (setup.key_set ? "claude" : "warn") : pv === "ollama" ? "claude" : "mock";
      label = keyed && !setup.key_set ? "NO KEY" : ({ mock: "MOCK", anthropic: "CLAUDE", groq: "GROQ", ollama: "LOCAL" }[pv] || pv.toUpperCase());
      tip = `Configured provider: ${pv}${setup.verifier ? " · " + setup.verifier : ""}${keyed && !setup.key_set ? " — API key missing in .env" : ""}`;
    }
    if (st.llm_offline) { k = "warn"; label += " · OFFLINE"; }
    S.llmKind = k;
    const p = $("#llmPill"); p.dataset.k = k; p.title = tip; $("b", p).textContent = label;
    $("#kpiLlm").textContent = st.llm_offline ? "LLM offline (fallback)" : k === "mock" ? "mock provider · not a real LLM" : k === "off" ? "LLM disabled for this run" : "verifier · composer";
  }
  function speedUi(st) {
    const live = st.status === "live" || st.status === "paused" || st.status === "starting";
    $("#speedSeg").classList.toggle("is-disabled", !live);
    $$("#speedSeg button").forEach((b) => {
      const v = speedFor(parseFloat(b.dataset.mult), st);
      b.disabled = !live;
      b.classList.toggle("is-on", Math.abs(v - st.speed) < 1e-6);
      b.title = `${v.toFixed(2)} s per sim-day`;
    });
    $("#trackHint").textContent = live ? `${st.speed.toFixed(2)} s per sim-day · click or drag to inspect a closed day · ← → step · Esc latest`
                                       : "replay finished · click or drag to inspect any day · ← → step · Esc latest";
  }
  const speedFor = (mult, st) => Math.max(0.75, Math.min(4, st.launch_speed / mult));
  $$("#speedSeg button").forEach((b) => b.addEventListener("click", async () => {
    if (!S.state) return;
    const v = speedFor(parseFloat(b.dataset.mult), S.state);
    const r = await api("/api/control", { run: S.run, kind: "speed", payload: { s: v } }).catch((e) => ({ ok: false, error: e.message }));
    toast(r.ok ? `Replay speed ${b.dataset.mult}× — ${v.toFixed(2)} s per sim-day` : r.error, r.ok ? "ok" : "err");
    tick(false);
  }));

  function banner(st) {
    const b = $("#banner"), msgs = [];
    if (st.stale.length) msgs.push(`DEGRADED — stale agents: ${st.stale.join(", ")}. Dependent evidence is missing; fusion runs on the remaining modalities.`);
    if (st.llm_offline) msgs.push("LLM offline — verifier uses the deterministic level, messages use the fixed template.");
    if (st.dropped && st.dropped.length) msgs.push(`Sensor data dropped for ${st.dropped.join(", ")}.`);
    if (!b.firstChild) b.appendChild(el("div"));
    if (msgs.length) b.firstChild.textContent = msgs.join("  ·  ");
    b.classList.toggle("is-on", msgs.length > 0);
  }

  async function togglePause() {
    if (!S.state || S.state.status === "finished") return;
    const kind = S.state.status === "paused" ? "resume" : "pause";
    await api("/api/control", { run: S.run, kind });
    toast(kind === "pause" ? "Replay paused" : "Replay resumed", "ok");
    tick(false);
  }
  $("#playBtn").addEventListener("click", togglePause);

  /* ---------------- overview ---------------- */
  function renderTimeline(full) {
    if (!S.meta || !(S.tab === "overview" || full)) return;
    C.timeline($("#timeline"), S.hist, { single: S.meta.single_zone, th: S.meta.thresholds, total: S.meta.days_total, view: S.view,
                                          onPick: (d) => setView(S.hist.length && d === S.hist[S.hist.length - 1].day ? null : d) });
  }
  function groupAlerts(items) {
    // collapse runs of L0↔L1 changes in one zone (≤ 7 days apart, no L2+ in between) into one "watch period"
    if (!S.group) return items.map((a) => ({ a }));
    const open = {}, out = [], rn = {};
    [...items].reverse().forEach((a) => {
      if (a.kind === "renotify") {   // one card per day for all re-notifications
        const g = rn[a.date];
        if (g) { g.items.push(a); g.key = a.seq; g.lv = Math.max(g.lv, a.to || 0); return; }
        const ng = { renotify: true, date: a.date, items: [a], key: a.seq, lv: a.to || 0 };
        rn[a.date] = ng; out.push(ng); return;
      }
      const low = (a.kind === "escalate" || a.kind === "deescalate") && Math.max(a.from || 0, a.to || 0) <= 1;
      if (!low) { open[a.zone] = null; out.push({ a, key: a.seq }); return; }
      const g = open[a.zone];
      if (g && dayDiff(g.last, a.date) <= 7) { g.items.push(a); g.last = a.date; g.key = a.seq; if (a.p !== null && a.p > g.pmax) g.pmax = a.p; return; }
      const ng = { group: true, zone: a.zone, first: a.date, last: a.date, items: [a], pmax: a.p || 0, key: a.seq };
      open[a.zone] = ng; out.push(ng);
    });
    return out.map((x) => ((x.group || x.renotify) && x.items.length === 1 ? { a: x.items[0], key: x.key } : x)).sort((x, y) => y.key - x.key);
  }
  const visibleAlerts = () => (S.view ? S.alerts.filter((a) => a.date <= S.view) : S.alerts);
  function alertLine(a) {
    const lv = a.to || 0;
    if (a.kind === "renotify") return `re-notify · unacknowledged L${lv}`;
    if (a.kind === "deescalate") return `L${a.from} → L${lv} de-escalated`;
    return `L${a.from} → L${lv} ${LEVEL[lv].split(" ")[1]}${a.p !== null ? " · p " + a.p.toFixed(3) : ""}`;
  }
  function renderMiniFeed() {
    const ol = $("#miniFeed"); ol.innerHTML = "";
    const items = groupAlerts(visibleAlerts()).slice(0, 14);
    if (!items.length) { ol.appendChild(el("li", "hint", "No alerts yet.")); return; }
    items.forEach((it) => {
      if (it.group) {
        const li = el("li", "is-group");
        if (!S.firstAlerts && it.items.some((x) => !S.seenAlerts.has(x.seq))) li.classList.add("enter");
        li.append(el("span", "when", `${it.first.slice(5)}–${it.first.slice(5, 7) === it.last.slice(5, 7) ? it.last.slice(8) : it.last.slice(5)}`));
        const w = el("span", "what"); w.append(el("strong", "mono", it.zone + "  "));
        w.append(document.createTextNode(`watch period · ${it.items.length} L0↔L1 changes${it.pmax ? " · peak p " + it.pmax.toFixed(3) : ""}`)); li.append(w);
        li.append(el("span", "level-chip l1 ghost", "L1"));
        li.addEventListener("click", () => { S.zone = it.zone; setTab("zone"); });
        ol.appendChild(li); return;
      }
      if (it.renotify) {
        const li = el("li", "is-group");
        if (S.view && it.date === S.view) li.classList.add("is-today");
        li.append(el("span", "when", it.date.slice(5)));
        const w = el("span", "what"); w.append(document.createTextNode(`re-notify · ${it.items.length} zones still unacknowledged`)); li.append(w);
        li.append(el("span", "level-chip l" + it.lv, "L" + it.lv));
        li.addEventListener("click", () => setTab("alerts"));
        ol.appendChild(li); return;
      }
      const a = it.a, li = el("li");
      if (S.view && a.date === S.view) li.classList.add("is-today");
      if (!S.seenAlerts.has(a.seq) && !S.firstAlerts) li.classList.add("enter");
      li.append(el("span", "when", a.date.slice(5)));
      const w = el("span", "what"); w.append(el("strong", "mono", a.zone + "  ")); w.append(document.createTextNode(alertLine(a))); li.append(w);
      li.append(el("span", "level-chip l" + (a.to || 0), "L" + (a.to || 0)));
      li.addEventListener("click", () => { S.zone = a.zone; setTab("zone"); });
      ol.appendChild(li);
    });
  }
  function notifyNew(alerts) {
    const fresh = alerts.filter((a) => !S.seenAlerts.has(a.seq));
    if (!S.firstAlerts) fresh.filter((a) => a.kind === "escalate" && a.to >= 2).slice(0, 3)
      .forEach((a) => toast(`${a.zone}: escalated to ${LEVEL[a.to]}${a.p !== null ? ` (p ${a.p.toFixed(3)})` : ""}`, a.to >= 3 ? "l3" : ""));
    alerts.forEach((a) => S.seenAlerts.add(a.seq));
    S.firstAlerts = false;
    const n = (S.state.unacked || []).length;
    $("#alertCount").textContent = n ? String(n) : "";
  }

  /* ---------------- alerts ---------------- */
  $$("#view-alerts .seg button").forEach((b) => b.addEventListener("click", () => {
    $$("#view-alerts .seg button").forEach((x) => x.classList.toggle("is-on", x === b)); S.filter = b.dataset.filter; S.feedLimit = 20; renderFeed();
  }));
  function renderFeed() {
    const ol = $("#feed"); ol.innerHTML = "";
    const unacked = new Set(S.state ? S.state.unacked : []);
    const eps = S.state ? S.state.episodes : {};
    let items = visibleAlerts();
    if (S.filter === "unacked") items = items.filter((a) => unacked.has(a.zone) && eps[a.zone] && a.episode_id === eps[a.zone].id);
    if (S.filter === "escalate") items = items.filter((a) => a.kind === "escalate");
    if (!items.length) { ol.appendChild(el("li", "empty", "Nothing to show for this filter.")); return; }
    const lvc = [css("--l0"), css("--l1"), css("--l2"), css("--l3")];
    let rows = S.filter === "all" ? groupAlerts(items) : items.map((a) => ({ a }));
    const total = rows.length;
    rows = rows.slice(0, S.feedLimit || 20);
    rows.forEach((it, i) => {
      if (it.group) { ol.append(groupCard(it, i)); return; }
      if (it.renotify) { ol.append(renotifyCard(it, i)); return; }
      const a = it.a;
      const lv = a.to || 0, li = el("li", `alert-card l${lv} enter${a.kind === "escalate" ? "" : " compact"}`); li.style.animationDelay = Math.min(i, 10) * 25 + "ms";
      li.append(el("div", "stripe"));
      const body = el("div", "alert-body"), top = el("div", "alert-top");
      top.append(el("span", "level-chip l" + lv, "L" + lv), el("strong", "mono", a.zone), el("span", "meta", `${a.date} · ${a.kind}${a.p !== null ? " · p " + a.p.toFixed(4) : ""}`));
      body.append(top);
      if (a.message) {
        body.append(el("div", "alert-head", a.message.headline || ""), el("p", "alert-text", a.message.body || ""));
        const ul = el("ul", "actions-list"); (a.message.actions || []).forEach((t) => ul.append(el("li", "", t))); body.append(ul);
      } else {
        body.append(el("p", "alert-text", alertLine(a)));
      }
      const vb = a.verifier && a.verifier.verifier === "fallback_budget";
      if (a.kind === "escalate" && a.verifier && a.verifier.decision && a.verifier.decision !== "PASS" && !vb) {
        const v = el("div", "verifier");
        const vk = a.verifier.verifier || a.verifier.mode || "llm";
        v.append(el("span", "", "Verifier "), el("b", "", a.verifier.decision), el("span", "", `  (${vk === "llm" && S.llmKind === "mock" ? "mock LLM" : vk}) L${a.verifier.level_in} → L${a.verifier.level_out}`));
        if (a.verifier.rationale) { v.append(el("br")); v.append(el("span", "", a.verifier.rationale)); }
        body.append(v);
      }
      const cs = Object.entries(a.contributions || {}).filter(([, v]) => v !== null).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1])).slice(0, 4);
      if (cs.length && a.kind === "escalate") {
        const dr = el("div", "drivers"); dr.append(el("span", "", "drivers"));
        cs.forEach(([k, v]) => { const sp = el("span", v >= 0 ? "up" : "down"); sp.append(el("b", "", (v >= 0 ? "▲ " : "▼ ") + k), document.createTextNode(` ${v >= 0 ? "+" : ""}${v.toFixed(2)}`)); dr.append(sp); });
        body.append(dr);
      }
      li.append(body);
      const side = el("div", "alert-side");
      const open = eps[a.zone] && a.episode_id === eps[a.zone].id;
      if (a.message) side.append(el("span", "tag" + (a.message.source === "llm" ? (S.llmKind === "mock" ? " is-warn" : " is-ok") : ""),
                                    a.message.source === "llm" ? (S.llmKind === "mock" ? "mock-LLM message" : "LLM message") : "template"));
      if (a.kind === "escalate" && vb) side.append(el("span", "tag", "verifier: daily budget"));
      if (open && unacked.has(a.zone)) {
        const btn = el("button", "btn btn-primary", "Acknowledge");
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          const r = await api("/api/ack", { run: S.run, zone: a.zone }).catch((e) => ({ ok: false, error: e.message }));
          if (r.ok) { toast(`Acknowledged ${r.episode_id}`, "ok"); btn.textContent = "Acknowledged"; } else { toast(r.error || "ack failed", "err"); btn.disabled = false; }
        });
        side.append(btn);
      } else if (open) side.append(el("span", "tag is-ok", "acknowledged"));
      li.append(side);
      ol.append(li);
    });
    if (total > rows.length) {
      const more = el("button", "btn more", `Show ${Math.min(20, total - rows.length)} more of ${total - rows.length}`);
      more.addEventListener("click", () => { S.feedLimit = (S.feedLimit || 20) + 20; renderFeed(); });
      ol.append(more);
    }
  }

  function groupCard(g, i) {
    const li = el("li", "alert-card l1 group enter compact"); li.style.animationDelay = Math.min(i, 10) * 25 + "ms";
    li.append(el("div", "stripe"));
    const body = el("div", "alert-body"), top = el("div", "alert-top");
    top.append(el("span", "level-chip l1 ghost", "L1"), el("strong", "mono", g.zone), el("span", "meta", `${g.first} → ${g.last} · watch period`));
    body.append(top);
    const up = g.items.filter((x) => x.to === 1).length;
    body.append(el("p", "alert-text", `${g.items.length} level changes between L0 Normal and L1 Watch (${up} up, ${g.items.length - up} down)${g.pmax ? ` · peak p ${g.pmax.toFixed(4)}` : ""}. No L2+ in between.`));
    const det = el("details", "group-detail"), sm = el("summary", "", "show changes");
    det.append(sm);
    const ul = el("ul");
    g.items.slice().reverse().forEach((x) => ul.append(el("li", "mono", `${x.date}  ${alertLine(x)}`)));
    det.append(ul); body.append(det);
    li.append(body);
    const side = el("div", "alert-side"); side.append(el("span", "tag", "grouped")); li.append(side);
    return li;
  }
  function renotifyCard(g, i) {
    const li = el("li", `alert-card l${g.lv} group enter compact`); li.style.animationDelay = Math.min(i, 10) * 25 + "ms";
    li.append(el("div", "stripe"));
    const body = el("div", "alert-body"), top = el("div", "alert-top");
    top.append(el("span", "level-chip l" + g.lv, "L" + g.lv), el("strong", "", "Re-notification"), el("span", "meta", `${g.date} · ${g.items.length} zones`));
    body.append(top);
    body.append(el("p", "alert-text", `Open L2+ episodes still unacknowledged after ${S.meta.renotify_days} sim-days:`));
    const zl = el("div", "zone-list");
    g.items.forEach((x) => { const b = el("button", "zone-tag mono", x.zone); b.type = "button"; b.addEventListener("click", () => { S.zone = x.zone; setTab("zone"); }); zl.append(b); });
    body.append(zl); li.append(body);
    const side = el("div", "alert-side"); side.append(el("span", "tag", "grouped")); li.append(side);
    return li;
  }
  $("#groupToggle").checked = S.group;
  $("#groupToggle").addEventListener("change", (e) => {
    S.group = e.target.checked; S.feedLimit = 20;
    try { localStorage.setItem("rw-group", S.group ? "1" : "0"); } catch (err) { /* ignore */ }
    renderFeed(); renderMiniFeed();
  });

  /* ---------------- zone ---------------- */
  $("#zoneSelect").addEventListener("change", (e) => { S.zone = e.target.value; loadZone(); paintZones(true); });
  async function loadZone() {
    if (!S.zone || !S.run) return;
    $("#zoneSelect").value = S.zone;
    const z = await api("/api/zone" + q({ run: S.run, zone: S.zone, day: S.view })).catch(() => null);
    if (!z) return;
    const lv = S.state && S.state.levels ? (S.state.levels[S.zone] || 0) : 0;
    const chip = $("#zoneLevel"); chip.className = "level-chip l" + lv; chip.textContent = LEVEL[lv];
    $("#zoneP").textContent = z.last ? z.last.p.toFixed(4) : "—";
    const meta = S.meta.zones.find((x) => x.zone_id === S.zone);
    $("#zonePrior").textContent = meta && meta.n_prior >= 0 ? meta.n_prior : "n/a";
    const qn = $("#zoneQuality"); qn.innerHTML = "";
    const qual = z.quality || {};
    const bad = Object.entries(qual).filter(([, v]) => v !== "ok");
    qn.append(el("span", bad.length ? "q-" + bad[0][1] : "q-ok", bad.length ? bad.map(([k, v]) => `${k} ${v}`).join(", ") : "all ok"));
    C.rain($("#rainChart"), z.series, S.view);
    C.prob($("#pChart"), z.series, S.meta.thresholds, S.view);
    const last = z.last || {};
    $("#contribSub").textContent = `per-modality contribution, log-odds · ${last.date || "—"}`;
    C.contrib($("#contribChart"), { rain: last.c_rain, thermal: last.c_thermal, seismic: last.c_seismic, susceptibility: last.c_susceptibility, context: last.c_context });
    const vn = $("#verifierNote"); vn.innerHTML = "";
    if (z.verifier && z.verifier.decision && z.verifier.decision !== "PASS") {
      vn.append(el("strong", "", `Verifier ${z.verifier.decision}`), document.createTextNode(` · L${z.verifier.level_in} → L${z.verifier.level_out}`));
      if (z.verifier.rationale) { vn.append(el("br")); vn.append(el("span", "", z.verifier.rationale)); }
    } else vn.append(el("span", "hint", "Verifier runs on L2+ candidates only."));
    const ev = $("#evidenceTable"); ev.innerHTML = "";
    ["rain", "thermal", "seismic", "susceptibility", "context"].forEach((g) => {
      const e = z.evidence[g]; if (!e) return;
      const box = el("div", "ev-group"), h = el("h3");
      h.append(el("span", "", g), el("span", "mono q-" + e.quality, `${e.contribution >= 0 ? "+" : ""}${e.contribution.toFixed(2)} · ${e.quality}`));
      const dl = el("dl");
      Object.entries(e.features).forEach(([k, v]) => { dl.append(el("dt", "", k), el("dd", "", v === null ? "—" : (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2)))); });
      box.append(h, dl); ev.append(box);
    });
    paintZones(true);
  }

  /* ---------------- agents & faults ---------------- */
  async function loadAgents() {
    S.lastAgents = Date.now();
    const d = await api("/api/agents" + q({ run: S.run })).catch(() => null);
    if (!d) return;
    const g = $("#agentGrid"); g.innerHTML = "";
    const finished = S.state && S.state.status === "finished";
    $(".faults").classList.toggle("is-disabled", finished);
    ["#killBtn", "#restartBtn", "#llmOffline", "#dropZone"].forEach((q2) => { $(q2).disabled = finished; });
    $("#faultSub").textContent = finished ? "replay finished — start a live run to inject faults" : "demonstrate degraded operation";
    d.agents.forEach((a) => {
      const stale = a.supervisor === "STALE";
      const card = el("div", "agent" + (stale ? " is-stale" : finished ? " is-stopped" : ""));
      if (!stale && S.hb[a.agent] !== undefined && a.last_heartbeat_s !== null && a.last_heartbeat_s < S.hb[a.agent]) card.classList.add("beat");
      S.hb[a.agent] = a.last_heartbeat_s;
      card.append(el("span", "hb"), el("span", "name", a.agent));
      card.append(el("span", "meta", `pid ${a.pid} · ${a.restarts ? a.restarts + " restart · " : ""}${a.last_heartbeat_s === null ? "no heartbeat" : finished ? "stopped" : a.last_heartbeat_s.toFixed(1) + " s ago"}${stale ? " · STALE" : ""}`));
      g.append(card);
    });
    const tb = $("#llmTable tbody"); tb.innerHTML = "";
    if (!d.llm.length) { const tr = el("tr"); const td = el("td", "hint", "No LLM calls in this run (start with --llm on)."); td.colSpan = 9; tr.append(td); tb.append(tr); }
    d.llm.forEach((r) => {
      const tr = el("tr");
      [r.date, r.zone, r.task, r.model, r.outcome, r.cached ? "yes" : "no"].forEach((v) => tr.append(el("td", "", v ?? "—")));
      tr.append(el("td", "num", `${r.in_tok ?? 0} / ${r.out_tok ?? 0}`), el("td", "num", r.latency_s === null ? "—" : r.latency_s.toFixed(2) + " s"), el("td", "", r.violations || "—"));
      tb.append(tr);
    });
  }
  async function agentAction(action) {
    const r = await api("/api/agent", { run: S.run, agent: "sensor_rain_0", action }).catch((e) => ({ ok: false, error: e.message }));
    toast(r.ok ? (action === "kill" ? "sensor_rain_0 killed — watch the supervisor flag it" : `sensor_rain_0 restarted (pid ${r.pid})`) : r.error, r.ok ? (action === "kill" ? "l3" : "ok") : "err");
    setTimeout(loadAgents, 400);
  }
  $("#killBtn").addEventListener("click", () => agentAction("kill"));
  $("#restartBtn").addEventListener("click", () => agentAction("restart"));
  $("#llmOffline").addEventListener("change", async (e) => {
    await api("/api/control", { run: S.run, kind: "llm_offline", payload: { on: e.target.checked } });
    toast(e.target.checked ? "LLM marked offline — deterministic fallback" : "LLM back online", e.target.checked ? "" : "ok");
  });
  let dropped = "";
  $("#dropZone").addEventListener("change", async (e) => {
    if (dropped) await api("/api/control", { run: S.run, kind: "drop_zone", payload: { zone_id: dropped, on: false } });
    dropped = e.target.value;
    if (dropped) await api("/api/control", { run: S.run, kind: "drop_zone", payload: { zone_id: dropped, on: true } });
    toast(dropped ? `Dropping sensor data for ${dropped}` : "Zone data restored", dropped ? "" : "ok");
  });

  /* ---------------- evaluation ---------------- */
  async function loadReports() {
    S.reports = await api("/api/reports").catch(() => []);
    const sel = $("#reportSelect"), cur = sel.value; sel.innerHTML = "";
    if (!S.reports.length) { $("#reportHint").textContent = "No reports yet — run `python -m rockwatch eval --split val`."; return; }
    S.reports.forEach((r) => { const o = el("option", "", `${r.name}${r.partial ? "  · partial data" : ""}${r.llm === "on" ? "  · LLM on" : ""}`); o.value = r.name; sel.append(o); });
    sel.value = S.reports.some((r) => r.name === cur) ? cur : S.reports[0].name;
    openReport(sel.value);
  }
  $("#reportSelect").addEventListener("change", (e) => openReport(e.target.value));
  $$("#view-eval .seg button").forEach((b) => b.addEventListener("click", () => {
    $$("#view-eval .seg button").forEach((x) => x.classList.toggle("is-on", x === b)); S.metric = b.dataset.metric; if (S.report) renderReport(S.report);
  }));
  async function openReport(name) {
    const r = await api("/api/report" + q({ name })).catch(() => null);
    if (!r) return;
    S.report = r; renderReport(r);
  }
  function renderReport(r) {
    const m = r.metrics, rw = m.rockwatch;
    $("#reportHint").textContent = `region ${m.region} · ${m.split} · ${m.period[0]} → ${m.period[1]} · LLM verifier ${m.llm_verifier} · git ${(m.git_hash || "").slice(0, 8)}`;
    const w = $("#reportWarn"), notes = [];
    if (m.data_coverage && m.data_coverage.partial) notes.push(`Partial data: ${m.data_coverage.zones_missing_weather} of ${m.data_coverage.zones_total} zones lacked weather — smoke test, not a result.`);
    if (m.split === "val") notes.push("Validation split: thresholds and baseline cut-offs were tuned here, so these numbers are optimistic.");
    notes.push(m.banner);
    w.textContent = notes.join("  ·  "); w.classList.toggle("is-on", true);
    const k = S.metric, isPct = k === "alert_day_fraction";
    const ci = (x) => (x.ci95 && x.ci95[k]) ? x.ci95[k] : [undefined, undefined];
    const rows = [{ label: "RockWatch (full fusion)", v: rw[k], lo: ci(rw)[0], hi: ci(rw)[1], main: true }];
    const names = { B1_P1_threshold: "B1 · daily rain ≥ q", B2_seattle_ct_designed_for_seattle: "B2 · Seattle threshold", B3_seasonal_climatology: "B3 · seasonal climatology",
      B4_random_matched_rate: "B4 · random, same alert rate", B5_rain_only: "B5 · rain-only model" };
    Object.entries(m.baselines).forEach(([key, b]) => rows.push({ label: names[key] || key, v: b[k], lo: ci(b)[0], hi: ci(b)[1] }));
    C.hbars($("#baselineChart"), rows, { pct: isPct, max: 1 });
    const th = m.thresholds, dl = $("#thresholdList"); dl.innerHTML = "";
    [["t1", th.t1, th.rule_t1], ["t2", th.t2, th.rule_t2], ["t3", th.t3, th.rule_t3 + (th.l3_enabled ? "" : " (L3 disabled)")]].forEach(([a, v, rule]) => {
      dl.append(el("dt", "", `${a} = ${v === null || v === undefined ? "—" : Number(v).toFixed(4)}`), el("dd", "", rule || ""));
    });
    dl.append(el("dt", "", "episodes"), el("dd", "", `${rw.n_episodes} (${rw.episodes_tp} matched) · ${rw.n_event_days} event-days`));
    const cols = [["recall_before", "Recall before"], ["recall_at", "Recall at"], ["precision_episode", "Prec. episode"], ["precision_day", "Prec. day"], ["f1_at", "F1 at"], ["false_alarms_per_zone_year", "FA / zone-yr"], ["alert_day_fraction", "Alert-day frac."]];
    const at = $("#ablationTable"); at.innerHTML = "";
    const thead = el("thead"), hr = el("tr"); hr.append(el("th", "", "Model")); cols.forEach(([, l]) => hr.append(el("th", "num", l))); hr.append(el("th", "num", "Val AP")); thead.append(hr); at.append(thead);
    const tb = el("tbody");
    Object.entries(m.ablations).forEach(([name, a]) => {
      const tr = el("tr", name === "full" ? "is-main" : ""); tr.append(el("td", "", name));
      cols.forEach(([c]) => tr.append(el("td", "num", C.fmt(a[c], 3)))); tr.append(el("td", "num", C.fmt(a.val_ap, 3))); tb.append(tr);
    });
    at.append(tb);
    const bt = $("#breakdownTable"); bt.innerHTML = "";
    const h2 = el("thead"), r2 = el("tr"); ["Subset", "Event-days", "Recall before", "Recall at"].forEach((t, i) => r2.append(el("th", i ? "num" : "", t))); h2.append(r2); bt.append(h2);
    const b2 = el("tbody");
    Object.entries(m.breakdowns || {}).forEach(([n, v]) => { const tr = el("tr"); tr.append(el("td", "", n.replace(/_/g, " ")), el("td", "num", v.n), el("td", "num", C.fmt(v.recall_before, 3)), el("td", "num", C.fmt(v.recall_at, 3))); b2.append(tr); });
    bt.append(b2);
    const fig = $("#figures"); fig.innerHTML = "";
    r.images.forEach((src) => { const img = el("img"); img.src = src; img.alt = src.split("/").pop(); img.loading = "lazy"; fig.append(img); });
  }

  /* ---------------- analyst ---------------- */
  const SUGGEST = ["Which alerts were raised in the last week?", "Explain the latest alert", "What are the latest evaluation metrics?", "When will the slope fail?"];
  SUGGEST.forEach((t) => { const b = el("button", "", t); b.type = "button"; b.addEventListener("click", () => { $("#askInput").value = t; $("#askForm").requestSubmit(); }); $("#suggest").append(b); });
  $("#askForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    let text = $("#askInput").value.trim(); if (!text) return;
    if (/latest alert/i.test(text) && S.alerts[0]) text = `Explain zone ${S.alerts[0].zone} on ${S.alerts[0].date}`;
    $("#askInput").value = "";
    const chat = $("#chat");
    chat.append(el("li", "msg q", text));
    const wait = el("li", "msg a typing"); wait.append(el("i"), el("i"), el("i")); chat.append(wait); chat.scrollTop = chat.scrollHeight;
    const a = await api("/api/ask", { run: S.run, question: text, llm: $("#askLlm").checked }).catch((err) => ({ answer: "Request failed: " + err.message, citations: [], source: "error" }));
    wait.remove();
    const li = el("li", "msg a"); li.append(document.createTextNode(a.answer || ""));
    const src = el("span", "src", `source: ${a.source}${a.warning ? " · " + a.warning : ""}`);
    (a.citations || []).slice(0, 8).forEach((c) => src.append(el("span", "cite", c)));
    li.append(src); chat.append(li); chat.scrollTop = chat.scrollHeight;
  });

  /* ---------------- boot ---------------- */
  moveInk();
  map.setTiles();
  loadRuns().catch((e) => { setStatus("error", "offline"); toast("Cannot reach the RockWatch API: " + e.message, "err"); });
})();
