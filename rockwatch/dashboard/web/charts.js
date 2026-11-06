/* Small dependency-free SVG charts with purposeful motion (draw-in, grow, smooth updates). */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const LV = () => [css("--l0"), css("--l1"), css("--l2"), css("--l3")];

  function s(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function lin(d0, d1, r0, r1) {
    const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
    const f = (v) => r0 + (v - d0) * k;
    f.inv = (px) => d0 + (px - r0) / (k || 1);
    return f;
  }
  function nice(max) {
    if (!(max > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(max)));
    for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= max) return m * p;
    return 10 * p;
  }
  const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : Number(v).toFixed(d);
  const shortDate = (d) => d ? d.slice(5) : "";

  function frame(el, h, m) {
    el.innerHTML = "";
    const w = Math.max(280, el.clientWidth || 600);
    const svg = s("svg", { viewBox: `0 0 ${w} ${h}`, height: h, role: "img" }, el);
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    el.appendChild(tip);
    return { svg, w, h, m, iw: w - m.l - m.r, ih: h - m.t - m.b, tip };
  }
  function yAxis(f, y, ticks, fmtv) {
    const g = s("g", { class: "axis" }, f.svg), gg = s("g", { class: "grid" }, f.svg);
    ticks.forEach((t) => {
      const yy = y(t);
      s("line", { x1: f.m.l, x2: f.w - f.m.r, y1: yy, y2: yy }, gg);
      s("text", { x: f.m.l - 6, y: yy + 3, "text-anchor": "end" }, g).textContent = fmtv ? fmtv(t) : t;
    });
  }
  function xLabels(f, days, x, every) {
    const g = s("g", { class: "axis" }, f.svg);
    const last = days.length - 1;
    days.forEach((d, i) => {
      const keep = i % every === 0 ? (i === last || last - i >= every / 2 || last % every === 0) : (i === last && last % every >= every / 2);
      if (!keep) return;
      s("text", { x: x(i), y: f.h - f.m.b + 14, "text-anchor": "middle" }, g).textContent = shortDate(d);
    });
  }
  function drawPath(svg, d, attrs, animate) {
    const p = s("path", Object.assign({ d, fill: "none" }, attrs), svg);
    if (animate) {
      const len = p.getTotalLength ? p.getTotalLength() : 0;
      if (len) { p.style.setProperty("--len", len); p.classList.add("draw"); }
    }
    return p;
  }
  function hover(f, n, x, onIdx, onClick) {
    const line = s("line", { class: "cursor-line", y1: f.m.t, y2: f.h - f.m.b, opacity: 0 }, f.svg);
    const hit = s("rect", { x: f.m.l, y: f.m.t, width: f.iw, height: f.ih, fill: "transparent" }, f.svg);
    hit.addEventListener("mousemove", (ev) => {
      const r = f.svg.getBoundingClientRect(), sx = f.w / r.width;
      const px = (ev.clientX - r.left) * sx;
      let i = Math.round(x.inv(px)); i = Math.max(0, Math.min(n - 1, i));
      line.setAttribute("x1", x(i)); line.setAttribute("x2", x(i)); line.setAttribute("opacity", 1);
      const html = onIdx(i);
      if (!html) return;
      f.tip.innerHTML = html;
      f.tip.classList.add("is-on");
      const tx = (x(i) / sx) + 12, max = r.width - f.tip.offsetWidth - 4;
      f.tip.style.left = Math.min(tx, max) + "px"; f.tip.style.top = "6px";
    });
    hit.addEventListener("mouseleave", () => { line.setAttribute("opacity", 0); f.tip.classList.remove("is-on"); });
    if (onClick) {
      hit.style.cursor = "pointer";
      hit.addEventListener("click", (ev) => {
        const r = f.svg.getBoundingClientRect();
        const i = Math.max(0, Math.min(n - 1, Math.round(x.inv((ev.clientX - r.left) * f.w / r.width))));
        onClick(i);
      });
    }
  }
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* Level timeline. Multi-zone: stacked zones per level (L0 faint). Single zone: level columns + daily p with thresholds.
     Reported events (closed days only) as ◆ on a row above the plot. Click a day → opts.onPick(day). */
  function timeline(el, hist, opts = {}) {
    if (!hist.length) { el.innerHTML = '<div class="chart-empty">waiting for the first closed day…</div>'; return; }
    const single = !!opts.single, th = opts.th || {};
    const f = frame(el, 186, { t: 22, r: single ? 46 : 10, b: 22, l: 38 });
    const total = Math.max(hist.length, opts.total || 0), n = hist.length;
    const slot = f.iw / Math.max(total, 1), bw = Math.max(2, Math.min(16, slot * 0.74));
    const x = lin(0, Math.max(total - 1, 1), f.m.l + slot / 2, f.w - f.m.r - slot / 2);
    const lv = LV(), animate = !el.dataset.drawn, muted = css("--muted"), truthC = css("--truth"), ink = css("--ink");
    const vi = opts.view ? hist.findIndex((h) => h.day === opts.view) : -1;
    if (vi >= 0) s("rect", { x: x(vi) - slot / 2, y: f.m.t - 18, width: slot, height: f.ih + 18, fill: css("--accent"), opacity: 0.12, rx: 2 }, f.svg);
    if (single) {
      const pm = Math.max(0.01, ...hist.map((h) => h.pmax || 0), th.t3 ? th.t3 * 1.25 : 0);
      const maxP = nice(pm), y = lin(0, maxP, f.h - f.m.b, f.m.t);
      yAxis(f, y, [0, maxP / 2, maxP], (v) => v.toFixed(maxP < 0.1 ? 3 : 2));
      hist.forEach((h, i) => {
        const r = s("rect", { x: x(i) - slot / 2 + 0.5, y: f.m.t, width: Math.max(1, slot - 1), height: f.ih, fill: lv[h.max || 0], opacity: (h.max || 0) ? 0.30 : 0.10, class: "bar" }, f.svg);
        if (animate) { r.classList.add("fade"); r.style.animationDelay = i * 6 + "ms"; }
      });
      const close = th.t2 && th.t3 && Math.abs(th.t3 - th.t2) < 0.01 * th.t2;
      [["t1", lv[1]], ["t2", lv[2]], ["t3", lv[3]]].forEach(([k, c]) => {
        if (th[k] === null || th[k] === undefined || th[k] > maxP) return;
        s("line", { x1: f.m.l, x2: f.w - f.m.r, y1: y(th[k]), y2: y(th[k]), stroke: c, "stroke-dasharray": "3 3", "stroke-width": 1 }, f.svg);
        if (close && k === "t3") return;
        s("text", { x: f.w - f.m.r + 4, y: y(th[k]) + 3, fill: c, "font-size": 10, "font-family": css("--mono") }, f.svg).textContent = close && k === "t2" ? "t2≈t3" : k;
      });
      const pts = hist.map((h, i) => h.pmax === null || h.pmax === undefined ? null : `${x(i)},${y(Math.min(h.pmax, maxP))}`);
      const d = pts.reduce((a, p) => { if (p === null) { a.pen = "M"; return a; } a.d += a.pen + p + " "; a.pen = "L"; return a; }, { d: "", pen: "M" }).d;
      if (d) drawPath(f.svg, d, { stroke: ink, "stroke-width": 1.6, "stroke-linejoin": "round" }, animate);
    } else {
      const maxN = Math.max(1, ...hist.map((h) => h.n)), y = lin(0, maxN, f.h - f.m.b, f.m.t);
      yAxis(f, y, [0, Math.round(maxN / 2), maxN]);
      hist.forEach((h, i) => {
        let base = 0;
        [["l1", lv[1], 0.9], ["l2", lv[2], 0.95], ["l3", lv[3], 1], ["l0", lv[0], 0.16]].forEach(([k, c, op]) => {
          const v = h[k]; if (!v) return;
          const r = s("rect", { x: x(i) - bw / 2, y: y(base + v), width: bw, height: y(base) - y(base + v), fill: c, opacity: op, rx: 1.5, class: "bar" }, f.svg);
          if (animate || i === n - 1) { r.classList.add("grow"); r.style.animationDelay = (animate ? i * 10 : 0) + "ms"; }
          base += v;
        });
      });
    }
    hist.forEach((h, i) => {
      if (!h.truth) return;
      const g = s("g", { class: animate || i === n - 1 ? "fade" : "" }, f.svg);
      s("rect", { x: x(i) - 3.5, y: 4, width: 7, height: 7, fill: truthC, transform: `rotate(45 ${x(i)} ${7.5})` }, g);
      if (h.truth > 1) s("text", { x: x(i) + 6, y: 11, "font-size": 9, "font-family": css("--mono"), fill: truthC }, g).textContent = h.truth;
    });
    xLabels(f, hist.map((h) => h.day).concat(Array(total - n).fill("")), x, Math.max(1, Math.ceil(total / 8)));
    hover(f, n, x, (i) => {
      const h = hist[i];
      const lvTxt = single ? `L${h.max}${h.pmax !== null && h.pmax !== undefined ? " · p " + fmt(h.pmax, 4) : ""}` : `L1 ${h.l1} · L2 ${h.l2} · L3 ${h.l3} / ${h.n}`;
      return `${esc(h.day)}<br>${lvTxt}${h.truth ? `<br><span style="color:${truthC}">◆ ${h.truth} reported event${h.truth > 1 ? "s" : ""}</span>` : ""}<br><span style="color:${muted}">click to view this day</span>`;
    }, opts.onPick ? (i) => opts.onPick(hist[i].day) : null);
    el.dataset.drawn = "1";
  }

  /* Replay track: one segment per sim-day coloured by the highest level, ◆ reported events, playhead. */
  function track(el, hist, opts = {}) {
    const total = Math.max(1, opts.total || hist.length);
    el.innerHTML = "";
    const w = Math.max(280, el.clientWidth || 600), h = 38;
    const svg = s("svg", { viewBox: `0 0 ${w} ${h}`, height: h, class: "track-svg" }, el);
    const tip = document.createElement("div"); tip.className = "chart-tip"; el.appendChild(tip);
    const segW = w / total, lv = LV(), sunk = css("--sunk"), truthC = css("--truth");
    s("rect", { x: 0, y: 16, width: w, height: 12, rx: 3, fill: sunk }, svg);
    hist.forEach((d, i) => {
      s("rect", { x: i * segW + 0.25, y: 16, width: Math.max(0.5, segW - 0.5), height: 12, fill: lv[d.max || 0], opacity: (d.max || 0) ? 0.95 : 0.28 }, svg);
      if (d.truth) s("rect", { x: i * segW + segW / 2 - 3, y: 4, width: 6, height: 6, fill: truthC, transform: `rotate(45 ${i * segW + segW / 2} 7)` }, svg);
    });
    const head = s("g", { class: "playhead" }, svg);
    s("line", { x1: 0, x2: 0, y1: 12, y2: 33, stroke: css("--ink"), "stroke-width": 2 }, head);
    s("circle", { cx: 0, cy: 34, r: 3.4, fill: css("--ink") }, head);
    let cur = -2;
    const place = (i) => { cur = i; head.style.transform = `translateX(${i * segW + segW / 2}px)`; head.style.opacity = i >= 0 ? 1 : 0; };
    place(opts.view ? hist.findIndex((d) => d.day === opts.view) : hist.length - 1);
    const idx = (ev) => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(hist.length - 1, Math.floor((ev.clientX - r.left) / r.width * total))); };
    let drag = false;
    const pick = (ev) => { if (!hist.length) return; const i = idx(ev); if (i === cur) return; place(i); if (opts.onPick) opts.onPick(hist[i].day, i === hist.length - 1); };
    svg.addEventListener("pointerdown", (ev) => { drag = true; svg.setPointerCapture(ev.pointerId); pick(ev); });
    svg.addEventListener("pointermove", (ev) => {
      if (drag) pick(ev);
      if (!hist.length) return;
      const r = svg.getBoundingClientRect(), i = idx(ev), d = hist[i];
      tip.innerHTML = `${esc(d.day)} · L${d.max}${d.truth ? ` · <span style="color:${truthC}">◆ ${d.truth}</span>` : ""}`;
      tip.classList.add("is-on");
      tip.style.left = Math.min(ev.clientX - r.left + 10, r.width - tip.offsetWidth - 4) + "px"; tip.style.top = "-30px";
    });
    svg.addEventListener("pointerup", () => { drag = false; });
    svg.addEventListener("pointerleave", () => { tip.classList.remove("is-on"); });
  }

  /* Rain: P1 bars, P3 line, Seattle P3-needed dashed line. */
  function rain(el, rows, view) {
    rows = rows.filter((r) => r.date);
    if (!rows.length) { el.innerHTML = '<div class="chart-empty">no rain evidence yet</div>'; return; }
    const f = frame(el, 250, { t: 10, r: 10, b: 22, l: 36 });
    const n = rows.length;
    const maxV = nice(Math.max(5, ...rows.map((r) => Math.max(r.P1 || 0, r.P3 || 0, Math.min(r.seattle_P3_threshold_mm || 0, 250)))));
    const slot = f.iw / n, bw = Math.max(2, Math.min(14, slot * 0.6));
    const x = lin(0, Math.max(n - 1, 1), f.m.l + slot / 2, f.w - f.m.r - slot / 2), y = lin(0, maxV, f.h - f.m.b, f.m.t);
    yAxis(f, y, [0, maxV / 2, maxV], (v) => v + " mm");
    const ink2 = css("--ink-2"), acc = css("--accent"), l3 = css("--l3");
    rows.forEach((r, i) => {
      if (r.P1 === null || r.P1 === undefined) return;
      const b = s("rect", { x: x(i) - bw / 2, y: y(r.P1), width: bw, height: Math.max(0, y(0) - y(r.P1)), fill: acc, opacity: 0.35, rx: 1, class: "bar grow" }, f.svg);
      b.style.animationDelay = i * 8 + "ms";
      if (r.rain_quality && r.rain_quality !== "ok") s("circle", { cx: x(i), cy: y(0) - 3, r: 2.5, fill: l3 }, f.svg);
    });
    const path = (key) => rows.map((r, i) => (r[key] === null || r[key] === undefined) ? null : `${x(i)},${y(Math.max(0, Math.min(r[key], maxV)))}`)
      .reduce((a, p) => { if (p === null) { a.pen = "M"; return a; } a.d += a.pen + p + " "; a.pen = "L"; return a; }, { d: "", pen: "M" }).d;
    drawPath(f.svg, path("seattle_P3_threshold_mm"), { stroke: l3, "stroke-width": 1.4, "stroke-dasharray": "5 4", opacity: 0.85 }, false);
    drawPath(f.svg, path("P3"), { stroke: ink2, "stroke-width": 1.8, "stroke-linejoin": "round" }, true);
    const vi = view ? rows.findIndex((r) => r.date === view) : -1;
    if (vi >= 0) s("line", { x1: x(vi), x2: x(vi), y1: f.m.t, y2: f.h - f.m.b, stroke: css("--accent"), "stroke-width": 1.5, "stroke-dasharray": "2 2" }, f.svg);
    xLabels(f, rows.map((r) => r.date), x, Math.max(1, Math.ceil(n / 8)));
    hover(f, n, x, (i) => { const r = rows[i]; return `${esc(r.date)}<br>P1 ${fmt(r.P1, 1)} · P3 ${fmt(r.P3, 1)} · P15 ${fmt(r.P15, 1)} mm<br>Seattle needs P3 ≥ ${fmt(r.seattle_P3_threshold_mm, 1)} mm`; });
  }

  /* Probability with thresholds and level-coloured markers. */
  function prob(el, rows, th, view) {
    rows = rows.filter((r) => r.p !== null && r.p !== undefined);
    if (!rows.length) { el.innerHTML = '<div class="chart-empty">no fused risk yet</div>'; return; }
    const f = frame(el, 200, { t: 12, r: 44, b: 22, l: 44 });
    const n = rows.length;
    const maxP = nice(Math.max(...rows.map((r) => r.p), th && th.t3 ? th.t3 * 1.15 : 0, 0.01));
    const x = lin(0, Math.max(n - 1, 1), f.m.l, f.w - f.m.r), y = lin(0, maxP, f.h - f.m.b, f.m.t);
    yAxis(f, y, [0, maxP / 2, maxP], (v) => v.toFixed(maxP < 0.1 ? 3 : 2));
    const ink = css("--ink"), lv = LV(), muted = css("--muted");
    [["t1", lv[1]], ["t2", lv[2]], ["t3", lv[3]]].forEach(([k, c]) => {
      if (!th || th[k] === null || th[k] === undefined || th[k] > maxP) return;
      s("line", { x1: f.m.l, x2: f.w - f.m.r, y1: y(th[k]), y2: y(th[k]), stroke: c, "stroke-dasharray": "3 3", "stroke-width": 1 }, f.svg);
      const t = s("text", { x: f.w - f.m.r + 4, y: y(th[k]) + 3, fill: c, "font-size": 10, "font-family": css("--mono") }, f.svg); t.textContent = k;
    });
    const d = rows.map((r, i) => `${i ? "L" : "M"}${x(i)},${y(r.p)}`).join(" ");
    const area = s("path", { d: `${d} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`, fill: ink, "fill-opacity": 0.06, class: "fade" }, f.svg);
    area.style.animationDelay = "300ms";
    drawPath(f.svg, d, { stroke: ink, "stroke-width": 1.8, "stroke-linejoin": "round" }, true);
    rows.forEach((r, i) => {
      const c = s("circle", { cx: x(i), cy: y(r.p), r: r.level >= 2 ? 3.2 : 2.2, fill: lv[r.level || 0] || muted, class: "fade" }, f.svg);
      c.style.animationDelay = 400 + i * 10 + "ms";
    });
    const vi = view ? rows.findIndex((r) => r.date === view) : -1;
    if (vi >= 0) s("line", { x1: x(vi), x2: x(vi), y1: f.m.t, y2: f.h - f.m.b, stroke: css("--accent"), "stroke-width": 1.5, "stroke-dasharray": "2 2" }, f.svg);
    xLabels(f, rows.map((r) => r.date), x, Math.max(1, Math.ceil(n / 8)));
    hover(f, n, x, (i) => { const r = rows[i]; return `${esc(r.date)}<br>p ${fmt(r.p, 4)} · L${r.level ?? "—"}`; });
  }

  /* Diverging horizontal bars: per-modality log-odds contribution. */
  function contrib(el, c) {
    const keys = ["rain", "thermal", "seismic", "susceptibility", "context"].filter((k) => c && c[k] !== undefined && c[k] !== null);
    if (!keys.length) { el.innerHTML = '<div class="chart-empty">no contributions yet</div>'; return; }
    const rowH = 30, f = frame(el, keys.length * rowH + 18, { t: 4, r: 58, b: 14, l: 104 });
    const lim = Math.max(0.5, ...keys.map((k) => Math.abs(c[k])));
    const x = lin(-lim, lim, f.m.l, f.w - f.m.r - 8);
    s("line", { x1: x(0), x2: x(0), y1: f.m.t, y2: f.h - f.m.b, stroke: css("--rule-2") }, f.svg);
    const pos = css("--l2"), neg = css("--l0"), ink2 = css("--ink-2"), mono = css("--mono");
    keys.forEach((k, i) => {
      const v = c[k], yy = f.m.t + i * rowH + 6;
      s("text", { x: f.m.l - 10, y: yy + 12, "text-anchor": "end", fill: ink2, "font-size": 12 }, f.svg).textContent = k;
      const x0 = x(Math.min(0, v)), w = Math.max(1, Math.abs(x(v) - x(0)));
      const r = s("rect", { x: x0, y: yy, width: w, height: 16, rx: 2, fill: v >= 0 ? pos : neg, class: "growx" }, f.svg);
      r.style.transformOrigin = v >= 0 ? "left" : "right"; r.style.animationDelay = i * 60 + "ms";
      const t = s("text", { x: f.w - 4, y: yy + 12, "text-anchor": "end", "font-size": 11, "font-family": mono, fill: v >= 0 ? pos : neg, class: "fade" }, f.svg);
      t.textContent = (v >= 0 ? "+" : "") + v.toFixed(2); t.style.animationDelay = 300 + i * 60 + "ms";
    });
  }

  /* Horizontal bars with optional CI whiskers (baselines). */
  function hbars(el, rows, opts = {}) {
    rows = rows.filter((r) => r.v !== null && r.v !== undefined);
    if (!rows.length) { el.innerHTML = '<div class="chart-empty">no data</div>'; return; }
    const rowH = 30, f = frame(el, rows.length * rowH + 24, { t: 4, r: 60, b: 20, l: 230 });
    const max = opts.max || nice(Math.max(...rows.map((r) => Math.max(r.v, r.hi || 0))));
    const x = lin(0, max, f.m.l, f.w - f.m.r);
    yAxis({ ...f, svg: f.svg }, () => 0, []);
    const g = s("g", { class: "axis" }, f.svg);
    [0, max / 2, max].forEach((t) => { s("text", { x: x(t), y: f.h - 4, "text-anchor": "middle" }, g).textContent = opts.pct ? Math.round(t * 100) + "%" : t.toFixed(2); });
    const ink = css("--ink"), ink2 = css("--ink-2"), muted = css("--muted"), mono = css("--mono"), rule = css("--rule-2");
    rows.forEach((r, i) => {
      const yy = f.m.t + i * rowH + 5;
      s("text", { x: f.m.l - 10, y: yy + 13, "text-anchor": "end", fill: r.main ? ink : ink2, "font-size": 12, "font-weight": r.main ? 600 : 400 }, f.svg).textContent = r.label;
      s("rect", { x: f.m.l, y: yy, width: f.iw, height: 18, fill: rule, opacity: 0.25, rx: 2 }, f.svg);
      const b = s("rect", { x: f.m.l, y: yy, width: Math.max(1, x(r.v) - f.m.l), height: 18, rx: 2, fill: r.main ? ink : muted, opacity: r.main ? 1 : 0.55, class: "growx" }, f.svg);
      b.style.transformOrigin = "left"; b.style.animationDelay = i * 50 + "ms";
      if (r.lo !== undefined && r.hi !== undefined && r.lo !== null) {
        const wy = yy + 9, c = r.main ? css("--l2") : ink2;
        s("line", { x1: x(r.lo), x2: x(r.hi), y1: wy, y2: wy, stroke: c, "stroke-width": 1.5, class: "fade" }, f.svg);
        s("line", { x1: x(r.lo), x2: x(r.lo), y1: wy - 5, y2: wy + 5, stroke: c, "stroke-width": 1.5, class: "fade" }, f.svg);
        s("line", { x1: x(r.hi), x2: x(r.hi), y1: wy - 5, y2: wy + 5, stroke: c, "stroke-width": 1.5, class: "fade" }, f.svg);
      }
      const t = s("text", { x: Math.max(x(r.v), r.hi !== undefined && r.hi !== null ? x(r.hi) : 0) + 6, y: yy + 13, "font-size": 11, "font-family": mono, fill: ink2, class: "fade" }, f.svg);
      t.textContent = opts.pct ? (r.v * 100).toFixed(1) + "%" : r.v.toFixed(3);
    });
  }

  window.RWCharts = { timeline, track, rain, prob, contrib, hbars, fmt };
})();
