"use strict";
/* PianoLens local app. No external requests: everything comes from this server. */

const $ = (s, el = document) => el.querySelector(s);
const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
};
const pct = x => (x == null ? "-" : (100 * x).toFixed(1) + "%");

/* ---------------------------------------------------------------- theme */
(function theme() {
  const root = document.documentElement;
  try { const t = localStorage.getItem("pl-theme"); if (t) root.dataset.theme = t; } catch (e) { /* private mode */ }
  document.addEventListener("DOMContentLoaded", () => {
    const b = $("#theme"); if (!b) return;
    b.onclick = () => {
      const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem("pl-theme", root.dataset.theme); } catch (e) { /* ignore */ }
    };
  });
})();

async function api(url, opts = {}) {
  const r = await fetch(url, opts);
  let d = null;
  try { d = await r.json(); } catch (e) { d = { error: r.statusText }; }
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}

/* ---------------------------------------------------------------- home */
function initHome() {
  const list = $("#pieces"), q = $("#q"), pid = $("#piece_id"), chosen = $("#chosen");
  let pieces = [];
  const norm = s => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[.,"()]/g, " ");
  function render() {
    const toks = norm(q.value).split(/\s+/).filter(Boolean);
    const hits = [];
    for (const p of pieces) {
      if (toks.every(t => p._s.includes(t))) hits.push(p);
      if (hits.length >= 150) break;
    }
    list.replaceChildren();
    if (!hits.length) { list.append(h("p", { class: "muted", style: null }, "No supported piece matches. You can upload a score below.")); return; }
    for (const p of hits) {
      const refs = p.n_references ? `${p.n_references} references` : "no expert references";
      const el = h("div", { class: "piece", role: "option", tabindex: "0", "aria-selected": String(p.piece_id === pid.value) },
        h("div", { class: "t" }, h("span", { class: "c" }, p.composer), " ", p.title),
        h("div", { class: "r" }, refs + (p.n_asap ? ` · ${p.n_asap} ASAP` : "")));
      const pick = () => {
        pid.value = p.piece_id;
        chosen.replaceChildren("Chosen: ", h("b", {}, `${p.composer}, ${p.title}`), ` (${refs})`);
        list.querySelectorAll(".piece").forEach(x => x.setAttribute("aria-selected", String(x === el)));
      };
      el.onclick = pick;
      el.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } };
      list.append(el);
    }
  }
  api("/api/pieces").then(d => {
    pieces = d.map(p => ({ ...p, _s: norm(`${p.composer} ${p.title} ${p.piece_id}`) }));
    render();
  }).catch(e => { list.replaceChildren(h("p", { class: "muted" }, "Could not load pieces: " + e.message)); });
  q.addEventListener("input", render);

  const perf = $("#perf");
  perf.addEventListener("change", () => {
    const names = [...perf.files].map(f => f.name.toLowerCase());
    const midi = names.length && names.every(n => /\.midi?$/.test(n));
    const audio = names.length && names.every(n => /\.(wav|mp3|m4a|flac|aac|ogg)$/.test(n));
    $("#kind-audio").hidden = !audio; $("#kind-midi").hidden = !midi;
    $("#form-msg").textContent = names.length && !midi && !audio ? "Use all audio or all MIDI files." : "";
  });

  $("#new").addEventListener("submit", async e => {
    e.preventDefault();
    const msg = $("#form-msg"), go = $("#go");
    if (!pid.value && !$("#score").files.length) { msg.textContent = "Choose a piece from the list, or upload its score."; return; }
    if (!perf.files.length) { msg.textContent = "Add a recording or a MIDI file."; return; }
    go.disabled = true; msg.textContent = "Uploading...";
    try {
      const d = await api("/api/jobs", { method: "POST", body: new FormData(e.target) });
      location.href = d.url;
    } catch (err) { msg.textContent = err.message; go.disabled = false; }
  });
}

/* ---------------------------------------------------------------- history */
function initHistory() {
  document.querySelectorAll("[data-delete]").forEach(b => {
    b.onclick = async () => {
      if (!confirm("Delete this analysis and its uploaded files?")) return;
      await api(`/api/jobs/${b.dataset.delete}/delete`, { method: "POST" });
      b.closest("li").remove();
    };
  });
}

/* ---------------------------------------------------------------- job */
function initJob() {
  const id = document.body.dataset.job;
  const prog = $("#progress"), res = $("#results"), acts = $("#job-actions");
  let timer = 0, shown = false;
  async function poll() {
    let d;
    try { d = await api(`/api/jobs/${id}`); } catch (e) { prog.hidden = false; prog.textContent = e.message; return; }
    const st = d.status;
    renderActions(st.state);
    if (st.state === "done") {
      prog.hidden = true;
      if (!shown) { shown = true; renderResults(res, d.results); }
      return;
    }
    renderProgress(prog, st);
    if (st.state === "running" || st.state === "queued") timer = setTimeout(poll, 1000);
  }
  function renderActions(state) {
    acts.replaceChildren();
    if (state === "running" || state === "queued") {
      acts.append(h("button", { type: "button", class: "ghost", onclick: async () => { await api(`/api/jobs/${id}/cancel`, { method: "POST" }); clearTimeout(timer); poll(); } }, "Cancel"));
    } else {
      if (state === "stopped") acts.append(h("button", { type: "button", class: "ghost", onclick: async () => { await api(`/api/jobs/${id}/override`, { method: "POST" }); poll(); } }, "Analyse anyway"));
      else if (state !== "done") acts.append(h("button", { type: "button", class: "ghost", onclick: async () => { await api(`/api/jobs/${id}/retry`, { method: "POST" }); poll(); } }, "Run again"));
      acts.append(h("button", { type: "button", class: "ghost danger", onclick: async () => {
        if (!confirm("Delete this analysis and its uploaded files?")) return;
        await api(`/api/jobs/${id}/delete`, { method: "POST" }); location.href = "/history";
      } }, "Delete"));
    }
  }
  poll();
}

function fmtSec(s) { return s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`; }

function renderProgress(el, st) {
  el.hidden = false;
  const now = Date.now() / 1000;
  const items = st.steps.map(s => {
    let right = "";
    if (s.state === "running" && s.started) right = fmtSec(now - s.started);
    else if (s.state === "done" && s.started && s.ended) right = fmtSec(s.ended - s.started);
    const li = h("li", { class: "st-" + s.state }, h("span", { class: "dot" }),
      h("div", {}, s.label, s.detail ? h("div", { class: "muted small" }, s.detail) : null,
        s.state === "running" && s.progress != null ? h("div", { class: "bar-p" }, (() => { const i = h("i"); i.style.width = (100 * s.progress) + "%"; return i; })()) : null),
      h("span", { class: "muted small" }, right));
    return li;
  });
  const title = { queued: "Starting...", running: "Analysing", failed: "The analysis failed", cancelled: "Cancelled", interrupted: "Interrupted", stopped: "Is this the right piece?" }[st.state] || st.state;
  el.replaceChildren(h("h2", {}, title), h("ol", { class: "steps" }, items),
    st.message ? h("p", { class: "msg" + (["failed", "interrupted", "stopped"].includes(st.state) ? " err" : "") }, st.message) : null,
    st.state === "running" ? h("p", { class: "muted small" }, "You can leave this page; the analysis continues and appears under History.") : null);
}

/* ---------------------------------------------------------------- results */
function renderResults(el, R) {
  el.hidden = false;
  const trust = h("div", { class: "trust" }, R.trust.map(t =>
    h("div", {}, h("span", { class: "lvl " + t.level }, { trust: "Trustworthy", check: "Read with care", low: "Low confidence" }[t.level]), h("b", {}, t.what), t.why)));
  const f = R.facts, facts = h("div", { class: "facts" },
    R.transcribed
      ? h("span", { title: "Extra notes are left out: phone transcriptions add many (A-01)." }, "Wrong + missed notes ", h("b", {}, pct(f.wrong_missed_rate)))
      : h("span", {}, "Note errors ", h("b", {}, pct(f.error_rate))),
    f.tempo_bpm ? h("span", {}, "Tempo ", h("b", {}, f.tempo_bpm.toFixed(0) + " beats/min")) : null,
    h("span", {}, "Bars ", h("b", {}, f.n_bars ?? "-")),
    h("span", {}, "Expert references ", h("b", {}, f.n_references || "none")));
  const head = h("section", { class: "card" }, h("h2", {}, R.input_kind === "audio" ? "What this recording can tell you" : "What this MIDI can tell you"), trust, facts);

  const byId = Object.fromEntries(R.windows.map(w => [w.id, w]));
  const prac = h("div", {});
  if (!R.practise.length) prac.append(h("p", { class: "muted" }, "No practise items: nothing stood out beyond the expert range."));
  R.practise.forEach((p, i) => {
    const w = p.window ? byId[p.window] : null;
    prac.append(h("article", { class: "item" },
      h("div", { class: "item-head" }, h("h3", {}, `${i + 1}. ${cap(p.bars_label)}`), h("span", { class: "tier " + p.tier }, p.tier)),
      h("p", {}, p.text),
      w ? playerFor(w) : h("p", { class: "muted small" }, R.windows.length ? "No comparison clip covers these bars." : "No comparison clips for this analysis.")));
  });

  const all = h("div", {});
  if (!R.windows.length) all.append(h("p", { class: "muted" }, "No comparison passages."));
  R.windows.forEach((w, i) => {
    all.append(h("article", { class: "item" },
      h("div", { class: "item-head" }, h("h3", {}, `${i + 1}. ${cap(w.label)}`), h("span", { class: "tier " + w.tier }, w.tier)),
      h("ul", { class: "reasons" }, w.reasons.map(r => h("li", {}, r)), w.truncated ? h("li", {}, "Only the first bars of a longer flagged passage are included.") : null),
      playerFor(w)));
  });

  const frame = h("iframe", { class: "frame", src: R.report_url, title: "Full report", loading: "lazy" });
  const panels = { practise: prac, passages: all, report: h("div", {}, h("p", { class: "help" }, "The complete report with every bar, curve and confidence note. ", h("a", { href: R.report_url, target: "_blank", rel: "noopener" }, "Open it on its own page")), frame) };
  const tabs = h("div", { class: "tabs", role: "tablist" });
  const body = h("div", {});
  const names = { practise: `What to practise (${R.practise.length})`, passages: `All passages (${R.windows.length})`, report: "Full report" };
  function show(k) {
    tabs.querySelectorAll("button").forEach(b => b.setAttribute("aria-selected", String(b.dataset.k === k)));
    body.replaceChildren(panels[k]);
    if (Player.active) Player.active.pause();
  }
  for (const k of Object.keys(panels)) tabs.append(h("button", { type: "button", role: "tab", "data-k": k, onclick: () => show(k) }, names[k]));
  const help = h("p", { class: "help" }, "Each passage plays the same bars from up to four sources with about one bar before and after. Switch while playing: the position stays on the same beat. Keys: 1-4 source, space play/pause, L loop. Clips are matched in loudness.");
  el.replaceChildren(head, tabs, help, body);
  show("practise");
}
const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : "");

/* ---------------------------------------------------------------- A/B player */
const ORDER = ["user_audio", "user_render", "expert_typical", "expert_contrast"];
let ctx = null;
const audioCtx = () => (ctx ||= new (window.AudioContext || window.webkitAudioContext)());
const bufCache = new Map();
function loadBuf(url) {
  if (!bufCache.has(url)) {
    bufCache.set(url, fetch(url).then(r => { if (!r.ok) throw new Error("clip " + r.status); return r.arrayBuffer(); })
      .then(b => new Promise((res, rej) => audioCtx().decodeAudioData(b, res, rej))));
  }
  return bufCache.get(url);
}
function anchors(c, dur) {
  const a = [0].concat(c.bar_times || []).concat([dur]).filter(x => x >= 0 && x <= dur).sort((p, q) => p - q);
  const out = []; for (const x of a) if (!out.length || x > out[out.length - 1] + 1e-3) out.push(x);
  return out;
}
function mapPos(t, a, b) {
  const n = Math.min(a.length, b.length);
  if (n < 2) return t * (b[b.length - 1] / a[a.length - 1]);
  for (let i = 0; i < n - 1; i++) {
    if (t <= a[i + 1] || i === n - 2) {
      const f = Math.min(1, Math.max(0, (t - a[i]) / Math.max(1e-6, a[i + 1] - a[i])));
      return b[i] + f * (b[i + 1] - b[i]);
    }
  }
  return t;
}
class Player {
  constructor(w) {
    this.w = w; this.kinds = ORDER.filter(k => w.clips[k]);
    this.kind = this.kinds.includes("user_audio") ? "user_audio" : this.kinds[0];
    this.buffers = {}; this.src = null; this.playing = false; this.loop = true; this.t0 = 0; this.off = 0; this.raf = 0;
  }
  clip(k) { return this.w.clips[k || this.kind]; }
  dur(k) { const b = this.buffers[k || this.kind]; return b ? b.duration : this.clip(k).duration_sec; }
  async ready() { for (const k of this.kinds) if (!this.buffers[k]) this.buffers[k] = await loadBuf(this.w.clips[k].url); }
  pos() {
    if (!this.playing) return this.off;
    const p = this.off + (audioCtx().currentTime - this.t0), d = this.dur();
    return this.loop ? p % d : Math.min(p, d);
  }
  stopSrc() { if (this.src) { this.src.onended = null; try { this.src.stop(); } catch (e) { /* stopped */ } this.src = null; } }
  startAt(p) {
    const c = audioCtx(); this.stopSrc();
    const s = c.createBufferSource(); s.buffer = this.buffers[this.kind]; s.loop = this.loop; s.connect(c.destination);
    p = Math.max(0, Math.min(p, this.dur() - 1e-3));
    s.start(0, p); this.src = s; this.t0 = c.currentTime; this.off = p; this.playing = true;
    s.onended = () => { if (this.src === s) { this.playing = false; this.off = 0; this.src = null; this.render(); } };
    this.tick();
  }
  async play() {
    if (Player.active && Player.active !== this) Player.active.pause();
    Player.active = this;
    this.meta.textContent = "Loading clips...";
    try { await audioCtx().resume(); await this.ready(); } catch (e) { this.meta.textContent = "Could not load the clips: " + e.message; return; }
    this.startAt(this.off); this.render();
  }
  pause() { this.off = this.pos(); this.playing = false; this.stopSrc(); cancelAnimationFrame(this.raf); this.render(); }
  toggle() { this.playing ? this.pause() : this.play(); }
  async select(k) {
    if (!this.w.clips[k]) return;
    if (k === this.kind) { if (!this.playing) this.play(); return; }
    await this.ready();
    const p = this.pos(), a = anchors(this.clip(), this.dur()), b = anchors(this.clip(k), this.dur(k));
    const np = mapPos(p, a, b), was = this.playing;
    this.kind = k; this.off = np;
    if (was) this.startAt(np); else this.play();
    this.render();
  }
  setLoop(v) { this.loop = v; if (this.playing) this.startAt(this.pos()); this.render(); }
  seekFrac(f) { const p = f * this.dur(); if (this.playing) this.startAt(p); else { this.off = p; this.render(); } }
  tick() { cancelAnimationFrame(this.raf); const f = () => { this.renderHead(); if (this.playing) this.raf = requestAnimationFrame(f); }; f(); }
  renderHead() { this.head.style.left = (100 * this.pos() / this.dur()) + "%"; }
  render() {
    for (const k of this.kinds) this.btn[k].setAttribute("aria-pressed", String(k === this.kind));
    this.playBtn.textContent = this.playing ? "Pause" : "Play";
    this.loopBtn.setAttribute("aria-pressed", String(this.loop));
    const c = this.clip(), d = this.dur();
    this.shade.style.left = (100 * c.window_on / d) + "%";
    this.shade.style.width = (100 * (c.window_off - c.window_on) / d) + "%";
    this.bars.replaceChildren(...(c.bar_times || []).map(t => { const e = h("div", { class: "bl" }); e.style.left = (100 * t / d) + "%"; return e; }));
    const m = [];
    if (c.performer) m.push(c.performer);
    if (c.source_dataset) m.push(c.source_dataset + (c.capture_model ? " (" + c.capture_model + ")" : ""));
    if (c.distance_percentile != null) m.push("closer to the expert median than " + Math.round(100 * (1 - c.distance_percentile)) + "% of experts here");
    m.push(d.toFixed(1) + " s");
    this.meta.textContent = c.label + ": " + m.join(" · ");
    this.renderHead();
  }
  element() {
    const el = h("div", { class: "player" });
    this.btn = {};
    const row = h("div", { class: "srcs" });
    this.kinds.forEach((k, j) => {
      const b = h("button", { type: "button", class: "src", onclick: () => { Player.active = this; this.select(k); } }, h("span", { class: "k" }, String(j + 1)), this.w.clips[k].label);
      this.btn[k] = b; row.append(b);
    });
    this.playBtn = h("button", { type: "button", class: "ghost ctl", onclick: () => this.toggle() });
    this.loopBtn = h("button", { type: "button", class: "ghost ctl", onclick: () => this.setLoop(!this.loop) }, "Loop");
    row.append(this.playBtn, this.loopBtn);
    const tl = h("div", { class: "tl", title: "Click to jump" });
    this.shade = h("div", { class: "shade" }); this.bars = h("div"); this.head = h("div", { class: "head" });
    tl.append(this.shade, this.bars, this.head);
    tl.onclick = e => { const r = tl.getBoundingClientRect(); Player.active = this; this.seekFrac((e.clientX - r.left) / r.width); };
    this.meta = h("div", { class: "pmeta" });
    el.append(row, tl, this.meta);
    el.addEventListener("pointerdown", () => { if (Player.active !== this) { if (Player.active) Player.active.pause(); Player.active = this; } });
    this.render();
    return el;
  }
}
Player.active = null;
document.addEventListener("keydown", e => {
  const P = Player.active;
  if (!P || e.metaKey || e.ctrlKey || e.altKey || /INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName || "")) return;
  if (e.key === " ") { e.preventDefault(); P.toggle(); }
  else if (e.key === "l" || e.key === "L") P.setLoop(!P.loop);
  else if (/^[1-4]$/.test(e.key)) { const k = P.kinds[Number(e.key) - 1]; if (k) P.select(k); }
});

function playerFor(w) {
  const p = new Player(w);
  const wrap = h("div", {}, p.element());
  const cv = curvesFor(w.curves || {});
  if (cv) wrap.append(cv);
  return wrap;
}

/* ---------------------------------------------------------------- curves */
const SVGNS = "http://www.w3.org/2000/svg";
const s = (tag, attrs = {}) => { const e = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
function curvesFor(curves) {
  const blocks = Object.keys(curves);
  if (!blocks.length) return null;
  const box = h("div", { class: "curves" });
  for (const b of blocks) box.append(curveSvg(b, curves[b]));
  box.append(h("div", { class: "legend" }, "Solid line: you. Shaded band and dashed line: the expert range and median over these bars. Highlighted: the flagged bars. Shape is compared after removing your overall level."));
  return box;
}
function curveSvg(name, c) {
  const W = 320, H = 110, L = 30, R = 6, T = 8, B = 16;
  const xs = c.beat, n = xs.length;
  const vals = [].concat(c.target, c.lo, c.hi).filter(v => v != null && isFinite(v));
  const x0 = xs[0], x1 = xs[n - 1];
  let y0 = Math.min(...vals), y1 = Math.max(...vals); if (y1 - y0 < 1e-6) { y0 -= 1; y1 += 1; }
  const pad = 0.08 * (y1 - y0); y0 -= pad; y1 += pad;
  const X = x => L + (W - L - R) * (x - x0) / Math.max(1e-6, x1 - x0);
  const Y = y => T + (H - T - B) * (1 - (y - y0) / (y1 - y0));
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${name} curve against the expert range` });
  // flagged bars
  let i = 0;
  while (i < n) {
    if (c.flagged[i]) { let j = i; while (j + 1 < n && c.flagged[j + 1]) j++;
      const a = X(xs[i]), bx = j + 1 < n ? X(xs[j + 1]) : X(xs[j]);
      svg.append(s("rect", { class: "fl", x: a, y: T, width: Math.max(2, bx - a), height: H - T - B })); i = j + 1; } else i++;
  }
  const ok = k => c.lo[k] != null && c.hi[k] != null;
  let band = "", back = "";
  for (let k = 0; k < n; k++) if (ok(k)) band += (band ? "L" : "M") + X(xs[k]).toFixed(1) + " " + Y(c.hi[k]).toFixed(1);
  for (let k = n - 1; k >= 0; k--) if (ok(k)) back += "L" + X(xs[k]).toFixed(1) + " " + Y(c.lo[k]).toFixed(1);
  if (band) svg.append(s("path", { class: "band", d: band + back + "Z" }));
  const line = key => { let d = ""; for (let k = 0; k < n; k++) { const v = c[key][k]; if (v == null) continue; d += (d ? "L" : "M") + X(xs[k]).toFixed(1) + " " + Y(v).toFixed(1); } return d; };
  svg.append(s("path", { class: "mid", d: line("mid") }), s("path", { class: "tgt", d: line("target") }));
  svg.append(s("line", { class: "ax", x1: L, x2: W - R, y1: H - B, y2: H - B }));
  const t1 = s("text", { x: 2, y: T + 8 }); t1.textContent = y1.toFixed(name === "tempo" ? 0 : 0);
  const t2 = s("text", { x: 2, y: H - B }); t2.textContent = y0.toFixed(0);
  svg.append(t1, t2);
  // bar numbers under the axis
  let last = null;
  for (let k = 0; k < n; k++) if (c.bar[k] !== last) { last = c.bar[k]; const t = s("text", { x: X(xs[k]), y: H - 4 }); t.textContent = String(last); svg.append(t); }
  const label = name === "tempo" ? "Tempo" : name === "velocity" ? "Loudness (velocity)" : cap(name);
  return h("div", { class: "curve" }, h("h4", {}, `${label}${c.unit ? " · " + c.unit : ""}`), svg);
}

/* ---------------------------------------------------------------- boot */
document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "home") initHome();
  else if (page === "history") initHistory();
  else if (page === "job") initJob();
});
