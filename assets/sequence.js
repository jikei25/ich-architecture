/* Sequence diagram renderer.
   Diagrams are plain data (see sequences-s1.js / sequences-s2.js) and are drawn
   as inline SVG so they follow the page theme. Each widget has tabs, a sticky
   participant header, step-through (click an arrow or use the arrow keys),
   zoom and an expanded view. Mount point: <div class="sq" data-seq="s1"></div>

   Step types:
     {t:"msg", from, to, label, detail?, style?, ret?}   style: crit|ai|res|ui|flow|bak|rest
     {t:"note", over:"id" | ["idA","idB"], text, kind?}   kind: warn
     {t:"sep", label}                                     full-width section divider
     {t:"alt"|"opt"|"loop"|"par"|"break", label} ... {t:"else", label} ... {t:"end"}
*/
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var G = { colW: 132, gap: 22, pad: 18, line: 15, band: 26, boxH: 56 };
  var F = {
    msg: '500 12px Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
    name: '700 13px Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
    tag: '700 10.5px Inter, system-ui, -apple-system, "Segoe UI", sans-serif'
  };
  var FRAMES = { alt: 1, opt: 1, loop: 1, par: 1, "break": 1 };
  var STYLES = {
    crit: "Clinical critical path",
    ai: "AI triage (best-effort)",
    res: "Research / annotation",
    ui: "User action in a UI",
    flow: "Internal data flow",
    bak: "Backup, one-way",
    rest: "Retrieve / restore"
  };
  var uid = 0;

  var cv = document.createElement("canvas").getContext("2d");
  function tw(s, f) { cv.font = f || F.msg; return cv.measureText(s).width; }
  function wrap(s, max, f) {
    var out = [], cur = "";
    String(s).split(/\s+/).forEach(function (w) {
      var t = cur ? cur + " " + w : w;
      if (cur && tw(t, f) > max) { out.push(cur); cur = w; } else cur = t;
    });
    if (cur) out.push(cur);
    return out;
  }
  function widest(lines, f) { return lines.reduce(function (m, l) { return Math.max(m, tw(l, f)); }, 0); }
  function mk(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, parent, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }

  /* ---------- layout ---------- */
  function layout(d) {
    var P = d.participants, idx = {}, n = P.length, need = [], i;
    P.forEach(function (p, k) { idx[p.id] = k; });
    for (i = 0; i < n; i++) need[i] = G.colW + G.gap;
    var tail = G.colW / 2 + G.pad;
    d.steps.forEach(function (s) {
      if (s.t !== "msg") return;
      var a = idx[s.from], b = idx[s.to];
      if (a == null || b == null) throw new Error("Unknown participant in " + d.id + ": " + s.from + " -> " + s.to);
      if (a === b) {
        var w = Math.min(tw(s.label) + 62, 190);
        if (a === n - 1) tail = Math.max(tail, w); else need[a] = Math.max(need[a], w);
      } else if (Math.abs(a - b) === 1) {
        var l = Math.min(a, b);
        need[l] = Math.max(need[l], Math.min(tw(s.label) + 40, 212));
      }
    });
    var xs = [], x = G.pad + G.colW / 2;
    for (i = 0; i < n; i++) { xs.push(x); x += need[i]; }
    var W = Math.ceil(xs[n - 1] + tail);

    var y = 20, rows = [], frames = [], stack = [], path = [], num = 0;
    function ext(lo, hi) { stack.forEach(function (f) { f.lo = Math.min(f.lo, lo); f.hi = Math.max(f.hi, hi); }); }

    d.steps.forEach(function (s) {
      var lines, r;
      if (s.t === "msg") {
        num++;
        var ia = idx[s.from], ib = idx[s.to], a = xs[ia], b = xs[ib];
        r = { t: "msg", n: num, s: s, y0: y, path: path.slice() };
        if (ia === ib) {
          var room = (ia === n - 1 ? tail : need[ia]) - 62;
          lines = wrap(s.label, Math.max(170, room));
          r.self = true; r.x = a; r.lines = lines;
          r.h = Math.max(30, lines.length * G.line + 10);
          y += r.h + 16;
          ext(a - 12, a + 46 + widest(lines));
        } else {
          lines = wrap(s.label, Math.max(110, Math.abs(b - a) - 34));
          r.x1 = a; r.x2 = b; r.lines = lines;
          r.ay = y + lines.length * G.line + 8;
          y = r.ay + 20;
          var mid = (a + b) / 2, lw = widest(lines);
          ext(Math.min(a, b, mid - lw / 2) - 12, Math.max(a, b, mid + lw / 2) + 4);
        }
        rows.push(r);
      } else if (s.t === "note") {
        var ids = [].concat(s.over).map(function (id) {
          if (idx[id] == null) throw new Error("Unknown participant in note: " + id);
          return idx[id];
        });
        var x0 = xs[Math.min.apply(null, ids)] - G.colW / 2 + 4, x1 = xs[Math.max.apply(null, ids)] + G.colW / 2 - 4;
        if (x1 - x0 < 220) { var c = (x0 + x1) / 2; x0 = c - 110; x1 = c + 110; }
        x0 = Math.max(4, x0); x1 = Math.min(W - 4, x1);
        lines = wrap(s.text, x1 - x0 - 24);
        r = { t: "note", x0: x0, x1: x1, y0: y, h: lines.length * G.line + 16, lines: lines, kind: s.kind };
        rows.push(r); y += r.h + 16; ext(x0, x1);
      } else if (s.t === "sep") {
        rows.push({ t: "sep", y: y + 12, label: s.label }); y += 42;
      } else if (FRAMES[s.t]) {
        var f = { kind: s.t, label: s.label || "", y0: y, lo: Infinity, hi: -Infinity, secs: [] };
        stack.push(f); frames.push(f);
        path.push(s.t + (s.label ? " · " + s.label : ""));
        y += 36;
      } else if (s.t === "else") {
        var cur = stack[stack.length - 1];
        cur.secs.push({ y: y - 6, label: s.label || "" });
        path[path.length - 1] = cur.kind + (s.label ? " · " + s.label : "");
        y += 30;
      } else if (s.t === "end") {
        var e = stack.pop(); path.pop();
        if (!isFinite(e.lo)) { e.lo = xs[0]; e.hi = xs[n - 1]; }
        e.y1 = y - 4; y += 14;
        e.x0 = Math.max(4, e.lo - 14); e.x1 = Math.min(W - 4, e.hi + 14);
        var minW = tw(e.kind.toUpperCase(), F.tag) + 26 + tw("[" + e.label + "]") + 20;
        e.secs.forEach(function (sc) { minW = Math.max(minW, tw("[" + sc.label + "]") + 24); });
        if (e.x1 - e.x0 < minW) e.x1 = Math.min(W - 4, e.x0 + minW);
        ext(e.x0, e.x1);
      }
    });
    if (stack.length) throw new Error("Unclosed fragment in " + d.id);
    return { idx: idx, xs: xs, W: W, H: y + 10, rows: rows, frames: frames, count: num };
  }

  /* contiguous runs of participants that share a group */
  function runs(d, L) {
    var out = [], P = d.participants, n = P.length;
    P.forEach(function (p, i) {
      var last = out[out.length - 1];
      if (last && last.g === p.group) last.b = i; else out.push({ g: p.group, a: i, b: i });
    });
    out.forEach(function (r) {
      r.x0 = r.a === 0 ? 6 : (L.xs[r.a - 1] + L.xs[r.a]) / 2 + 2;
      r.x1 = r.b === n - 1 ? L.W - 6 : (L.xs[r.b] + L.xs[r.b + 1]) / 2 - 2;
      r.info = (d.groups && d.groups[r.g]) || null;
    });
    return out;
  }

  /* ---------- drawing ---------- */
  function drawHead(d, L, R) {
    var H = G.band + G.boxH + 24;
    var svg = mk("svg", { xmlns: NS, viewBox: "0 0 " + L.W + " " + H, "aria-hidden": "true", "class": "sq-svg" });
    mk("rect", { x: 0, y: 0, width: L.W, height: H, "class": "sq-bg" }, svg);
    R.forEach(function (r) {
      if (!r.info) return;
      var g = mk("g", { "class": "sqc-" + r.info.color + (r.info.site ? " sq-siteband" : "") }, svg);
      mk("rect", { x: r.x0, y: 6, width: r.x1 - r.x0, height: G.band - 6, rx: 8, "class": "sq-band" }, g);
      var label = r.info.label, max = r.x1 - r.x0 - 16;
      while (label.length > 4 && tw(label, F.tag) > max) label = label.slice(0, -2).replace(/\s+$/, "") + "…";
      mk("text", { x: r.x0 + 10, y: 6 + (G.band - 6) / 2, "class": "sq-bandt", "dominant-baseline": "central" }, g, label.toUpperCase());
    });
    d.participants.forEach(function (p, i) {
      var cx = L.xs[i], y = G.band + 12, x0 = cx - G.colW / 2;
      var g = mk("g", { "class": "sq-p sqc-" + p.color, "data-id": p.id }, svg);
      mk("title", {}, g, p.name + (p.sub ? " — " + p.sub : ""));
      mk("rect", { x: x0, y: y, width: G.colW, height: G.boxH, rx: 11, "class": "sq-pbox" + (p.kind === "actor" ? " actor" : "") }, g);
      var tx = cx, avail = G.colW - 16;
      if (p.kind === "actor") {
        var ix = x0 + 15, iy = y + 18;
        mk("circle", { cx: ix, cy: iy, r: 4.5, "class": "sq-icon" }, g);
        mk("path", { d: "M" + (ix - 7) + " " + (iy + 16) + " Q" + ix + " " + (iy + 3) + " " + (ix + 7) + " " + (iy + 16), "class": "sq-icon" }, g);
        tx = cx + 9; avail = G.colW - 34;
      }
      if (p.kind === "ui") {
        mk("rect", { x: x0 + 6, y: y - 8, width: 28, height: 16, rx: 8, "class": "sq-tagbg" }, g);
        mk("text", { x: x0 + 20, y: y, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-tagt" }, g, "UI");
      }
      var size = tw(p.name, F.name) > avail ? 11.5 : 13;
      mk("text", { x: tx, y: y + 22, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-pname", style: "font-size:" + size + "px" }, g, p.name);
      if (p.sub) mk("text", { x: tx, y: y + 40, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-psub" }, g, p.sub);
    });
    return { svg: svg, H: H };
  }

  function drawBody(d, L, R) {
    var id = "sq" + (++uid);
    var svg = mk("svg", { xmlns: NS, viewBox: "0 0 " + L.W + " " + L.H, "class": "sq-svg", role: "img", "aria-label": d.title });
    var defs = mk("defs", {}, svg);
    Object.keys(STYLES).forEach(function (st) {
      var m1 = mk("marker", { id: id + "-" + st, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 10, markerHeight: 10, markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, defs);
      mk("path", { d: "M0.5 1 L9.5 5 L0.5 9 Z", "class": "sq-mk sqs-" + st }, m1);
      var m2 = mk("marker", { id: id + "-" + st + "-r", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 10, markerHeight: 10, markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, defs);
      mk("path", { d: "M1.5 1.5 L9 5 L1.5 8.5", "class": "sq-mko sqs-" + st }, m2);
    });
    mk("rect", { x: 0, y: 0, width: L.W, height: L.H, "class": "sq-bg" }, svg);

    var cols = mk("g", { "class": "sq-cols" }, svg);
    R.forEach(function (r) {
      if (!r.info) return;
      var g = mk("g", { "class": "sqc-" + r.info.color }, cols);
      mk("rect", { x: r.x0, y: 0, width: r.x1 - r.x0, height: L.H, "class": "sq-col" + (r.info.site ? " site" : "") }, g);
    });
    d.participants.forEach(function (p, i) {
      mk("line", { x1: L.xs[i], y1: 0, x2: L.xs[i], y2: L.H, "class": "sq-life sqc-" + p.color }, svg);
    });

    var fr = mk("g", { "class": "sq-frames" }, svg);
    L.frames.forEach(function (f) {
      var g = mk("g", { "class": "sq-frame k-" + f.kind }, fr);
      mk("rect", { x: f.x0, y: f.y0, width: f.x1 - f.x0, height: f.y1 - f.y0, rx: 6, "class": "sq-fbox" }, g);
      var tag = f.kind.toUpperCase(), tgw = tw(tag, F.tag) + 18;
      mk("path", { d: "M" + f.x0 + " " + (f.y0 + 6) + " Q" + f.x0 + " " + f.y0 + " " + (f.x0 + 6) + " " + f.y0 + " H" + (f.x0 + tgw) + " V" + (f.y0 + 14) + " L" + (f.x0 + tgw - 7) + " " + (f.y0 + 21) + " H" + f.x0 + " Z", "class": "sq-ftag" }, g);
      mk("text", { x: f.x0 + 8, y: f.y0 + 11, "dominant-baseline": "central", "class": "sq-ftagt" }, g, tag);
      if (f.label) mk("text", { x: f.x0 + tgw + 8, y: f.y0 + 12, "dominant-baseline": "central", "class": "sq-flabel" }, g, "[" + f.label + "]");
      f.secs.forEach(function (sc) {
        mk("line", { x1: f.x0, y1: sc.y, x2: f.x1, y2: sc.y, "class": "sq-fsep" }, g);
        if (sc.label) mk("text", { x: f.x0 + 10, y: sc.y + 15, "dominant-baseline": "central", "class": "sq-flabel" }, g, "[" + sc.label + "]");
      });
    });

    var msgs = mk("g", { "class": "sq-msgs" }, svg), nodes = [];
    L.rows.forEach(function (r) {
      if (r.t === "sep") {
        var g = mk("g", { "class": "sq-sep" }, msgs);
        mk("line", { x1: 8, y1: r.y, x2: L.W - 8, y2: r.y, "class": "sq-sepline" }, g);
        var w = tw(r.label, F.tag) + 26, cx = Math.min(Math.max(L.W / 2, w / 2 + 12), L.W - w / 2 - 12);
        mk("rect", { x: cx - w / 2, y: r.y - 11, width: w, height: 22, rx: 11, "class": "sq-seppill" }, g);
        mk("text", { x: cx, y: r.y, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-sept" }, g, r.label.toUpperCase());
        return;
      }
      if (r.t === "note") {
        var gn = mk("g", { "class": "sq-note" + (r.kind ? " " + r.kind : "") }, msgs);
        mk("path", { d: "M" + r.x0 + " " + r.y0 + " H" + (r.x1 - 10) + " L" + r.x1 + " " + (r.y0 + 10) + " V" + (r.y0 + r.h) + " H" + r.x0 + " Z", "class": "sq-notebox" }, gn);
        r.lines.forEach(function (l, k) {
          mk("text", { x: (r.x0 + r.x1) / 2, y: r.y0 + 8 + G.line / 2 + k * G.line, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-notet" }, gn, l);
        });
        return;
      }
      var s = r.s, st = STYLES[s.style] ? s.style : "flow";
      var gm = mk("g", { "class": "sq-m sqs-" + st + (s.ret ? " ret" : ""), "data-n": r.n, "data-from": s.from, "data-to": s.to, tabindex: "-1" }, msgs);
      var mref = "url(#" + id + "-" + st + (s.ret ? "-r" : "") + ")";
      if (r.self) {
        var top = r.y0 + 6, bot = r.y0 + r.h - 2, x = r.x;
        mk("rect", { x: x - 12, y: r.y0 - 4, width: 58 + widest(r.lines), height: r.h + 10, "class": "sq-hit" }, gm);
        mk("path", { d: "M" + (x + 10) + " " + top + " H" + (x + 36) + " Q" + (x + 40) + " " + top + " " + (x + 40) + " " + (top + 4) + " V" + (bot - 4) + " Q" + (x + 40) + " " + bot + " " + (x + 36) + " " + bot + " H" + (x + 4), "class": "sq-line", "marker-end": mref }, gm);
        r.lines.forEach(function (l, k) {
          mk("text", { x: x + 48, y: r.y0 + 6 + G.line / 2 + k * G.line, "dominant-baseline": "central", "class": "sq-lbl" }, gm, l);
        });
        num(gm, x, top, r.n);
        r.focusY = r.y0; r.focusX = x + 60;
      } else {
        var dir = r.x2 > r.x1 ? 1 : -1, lo = Math.min(r.x1, r.x2), hi = Math.max(r.x1, r.x2), mid = (r.x1 + r.x2) / 2;
        mk("rect", { x: lo - 12, y: r.y0 - 4, width: hi - lo + 24, height: r.ay - r.y0 + 14, "class": "sq-hit" }, gm);
        mk("path", { d: "M" + (r.x1 + dir * 10) + " " + r.ay + " H" + (r.x2 - dir * 1.5), "class": "sq-line", "marker-end": mref }, gm);
        r.lines.forEach(function (l, k) {
          mk("text", { x: mid, y: r.y0 + G.line / 2 + 2 + k * G.line, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-lbl" }, gm, l);
        });
        num(gm, r.x1, r.ay, r.n);
        r.focusY = r.y0; r.focusX = mid;
      }
      nodes[r.n] = gm;
    });
    return { svg: svg, nodes: nodes };
  }
  function num(g, x, y, n) {
    mk("circle", { cx: x, cy: y, r: 9.5, "class": "sq-num" }, g);
    mk("text", { x: x, y: y + 0.5, "text-anchor": "middle", "dominant-baseline": "central", "class": "sq-numt" }, g, n);
  }

  /* ---------- widget ---------- */
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function Widget(root, list) {
    this.root = root; this.list = list; this.cur = 0; this.active = 0; this.zoom = null; this.timer = null;
    root.tabIndex = 0;
    root.innerHTML = "";
    var self = this;
    if (list.length > 1) {
      var tabs = h("div", "sq-tabs", root); tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Sequence diagrams");
      this.tabs = list.map(function (d, i) {
        var b = h("button", "sq-tab", tabs, "<b>" + esc(d.tab || d.title) + "</b>" + (d.ui ? '<span class="sq-uichip">incl. UI</span>' : ""));
        b.type = "button"; b.setAttribute("role", "tab");
        b.addEventListener("click", function () { self.show(i); });
        return b;
      });
    }
    this.summary = h("p", "sq-summary", root);
    var bar = h("div", "sq-toolbar", root);
    var nav = h("div", "sq-nav", bar);
    this.bPrev = btn(nav, "←", "Previous step (←)", function () { self.step(-1); });
    this.bPlay = btn(nav, "▶ Play", "Play the sequence step by step", function () { self.togglePlay(); });
    this.bNext = btn(nav, "→", "Next step (→)", function () { self.step(1); });
    this.bAll = btn(nav, "Show all", "Show every step (Esc)", function () { self.stop(); self.setActive(0); });
    this.count = h("span", "sq-count", nav);
    var zm = h("div", "sq-zoom", bar);
    btn(zm, "−", "Zoom out", function () { self.setZoom(self.zoom / 1.2); });
    this.bZoom = btn(zm, "100%", "Fit to width", function () { self.setZoom(self.fit()); });
    btn(zm, "+", "Zoom in", function () { self.setZoom(self.zoom * 1.2); });
    this.bMax = btn(zm, "⤢ Expand", "Expand to full screen", function () { self.toggleMax(); });
    this.detail = h("div", "sq-detail", root); this.detail.setAttribute("aria-live", "polite");
    this.vp = h("div", "sq-viewport", root);
    this.head = h("div", "sq-head", this.vp);
    this.body = h("div", "sq-bodywrap", this.vp);
    this.legend = h("div", "sq-legend", root);
    var det = h("details", "sq-list", root);
    this.listSum = h("summary", "", det);
    this.ol = h("ol", "", det);

    this.body.addEventListener("click", function (ev) {
      if (self.vp.dataset.panned) return;
      var g = ev.target.closest && ev.target.closest(".sq-m");
      if (!g) return;
      var n = +g.getAttribute("data-n");
      self.stop(); self.setActive(self.active === n ? 0 : n);
    });
    this.head.addEventListener("mouseover", function (ev) {
      var p = ev.target.closest && ev.target.closest(".sq-p"); self.hover(p ? p.getAttribute("data-id") : null);
    });
    this.head.addEventListener("mouseleave", function () { self.hover(null); });
    root.addEventListener("keydown", function (ev) {
      if (ev.target.closest("summary,button") && (ev.key === " " || ev.key === "Enter")) return;
      if (ev.key === "ArrowRight") { self.stop(); self.step(1); ev.preventDefault(); }
      else if (ev.key === "ArrowLeft") { self.stop(); self.step(-1); ev.preventDefault(); }
      else if (ev.key === "Escape") { if (self.root.classList.contains("is-max")) self.toggleMax(); else { self.stop(); self.setActive(0); } }
    });
    if (window.ICHPan) window.ICHPan(this.vp);
    this.show(0);
  }
  function btn(parent, label, title, fn) {
    var b = h("button", "", parent, esc(label)); b.type = "button"; b.title = title; b.setAttribute("aria-label", title);
    b.addEventListener("click", fn); return b;
  }

  Widget.prototype.show = function (i) {
    var d = this.list[i], self = this;
    this.stop(); this.cur = i; this.active = 0;
    if (this.tabs) this.tabs.forEach(function (b, k) { b.setAttribute("aria-selected", k === i ? "true" : "false"); });
    this.summary.innerHTML = d.summary || "";
    var L = layout(d), R = runs(d, L);
    var hd = drawHead(d, L, R), bd = drawBody(d, L, R);
    this.L = L; this.d = d; this.nodes = bd.nodes; this.headH = hd.H;
    this.head.innerHTML = ""; this.head.appendChild(hd.svg); this.headSvg = hd.svg;
    this.body.innerHTML = ""; this.body.appendChild(bd.svg); this.bodySvg = bd.svg;

    var used = {};
    L.rows.forEach(function (r) { if (r.t === "msg") used[STYLES[r.s.style] ? r.s.style : "flow"] = 1; });
    var lg = Object.keys(STYLES).filter(function (k) { return used[k]; }).map(function (k) {
      return '<span><svg width="34" height="10" aria-hidden="true"><line x1="1" y1="5" x2="27" y2="5" class="sq-line sqs-' + k + '"/><path d="M25 1 L33 5 L25 9 Z" class="sq-mk sqs-' + k + '"/></svg>' + STYLES[k] + "</span>";
    });
    lg.push('<span><svg width="34" height="10" aria-hidden="true"><line x1="1" y1="5" x2="33" y2="5" class="sq-line" style="stroke:var(--muted)"/></svg>Solid: request / push</span>');
    lg.push('<span><svg width="34" height="10" aria-hidden="true"><line x1="1" y1="5" x2="33" y2="5" class="sq-line" style="stroke:var(--muted);stroke-dasharray:5 4"/></svg>Dashed: response / result shown</span>');
    lg.push('<span><span class="sq-uikey">UI</span>User interface</span>');
    this.legend.innerHTML = lg.join("");

    var P = {}; d.participants.forEach(function (p) { P[p.id] = p.name; });
    this.listSum.textContent = "All " + L.count + " steps as text";
    this.ol.innerHTML = "";
    this.items = [];
    L.rows.forEach(function (r) {
      if (r.t === "sep") { h("li", "sq-li-sep", self.ol, esc(r.label)); return; }
      if (r.t !== "msg") return;
      var li = h("li", "sq-li sqs-" + (STYLES[r.s.style] ? r.s.style : "flow"), self.ol,
        '<button type="button"><span class="sq-li-n">' + r.n + '</span><span class="sq-li-txt"><span class="sq-li-who">' + esc(P[r.s.from]) + " → " + esc(P[r.s.to]) +
        "</span><b>" + esc(r.s.label) + "</b>" + (r.s.detail ? "<span>" + esc(r.s.detail) + "</span>" : "") + "</span></button>");
      li.querySelector("button").addEventListener("click", function () {
        self.stop(); self.setActive(r.n);
        var top = self.root.getBoundingClientRect().top;
        if (top < 0 || top > window.innerHeight * 0.6) self.root.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      self.items[r.n] = li;
    });
    this.rows = L.rows.filter(function (r) { return r.t === "msg"; });
    var keep = this.zoom;
    this.zoom = null;
    this.setZoom(keep || this.defaultZoom());
    this.setActive(0);
  };

  Widget.prototype.fit = function () { return Math.min(1, (this.vp.clientWidth - 2) / this.L.W); };
  Widget.prototype.defaultZoom = function () { var f = this.fit(); return f >= 1 ? 1 : Math.max(f, 0.8); };
  Widget.prototype.setZoom = function (z) {
    z = Math.max(0.35, Math.min(2, z || 1));
    this.zoom = z;
    var W = Math.round(this.L.W * z);
    this.headSvg.setAttribute("width", W); this.headSvg.setAttribute("height", Math.round(this.headH * z));
    this.bodySvg.setAttribute("width", W); this.bodySvg.setAttribute("height", Math.round(this.L.H * z));
    this.bZoom.textContent = Math.round(z * 100) + "%";
  };

  Widget.prototype.setActive = function (n) {
    var self = this, total = this.L.count;
    n = Math.max(0, Math.min(total, n));
    this.active = n;
    this.bodySvg.classList.toggle("has-active", n > 0);
    this.nodes.forEach(function (g, k) { if (g) g.classList.toggle("on", k === n); });
    this.items.forEach(function (li, k) { if (li) li.classList.toggle("on", k === n); });
    var r = n ? this.rows[n - 1] : null;
    Array.prototype.forEach.call(this.headSvg.querySelectorAll(".sq-p"), function (p) {
      var id = p.getAttribute("data-id");
      p.classList.toggle("on", !!r && (id === r.s.from || id === r.s.to));
    });
    this.headSvg.classList.toggle("has-active", !!r);
    this.count.textContent = n ? "Step " + n + " / " + total : total + " steps";
    this.bPrev.disabled = n <= 1 && n !== 0 ? true : false;
    this.bNext.disabled = n >= total;
    if (!r) {
      this.detail.innerHTML = '<span class="sq-hint">Click a numbered arrow, or press <kbd>→</kbd> to walk through the sequence one step at a time. Hover a participant to see only its messages.</span>';
      return;
    }
    var P = {}; this.d.participants.forEach(function (p) { P[p.id] = p.name; });
    var ctx = r.path.length ? '<span class="sq-ctx">' + r.path.map(esc).join(" › ") + "</span>" : "";
    this.detail.innerHTML = '<span class="sq-dn sqs-' + (STYLES[r.s.style] ? r.s.style : "flow") + '">' + n + '</span><div><div class="sq-dwho">' + esc(P[r.s.from]) + " → " + esc(P[r.s.to]) + ctx +
      '</div><b>' + esc(r.s.label) + "</b>" + (r.s.detail ? '<p>' + esc(r.s.detail) + "</p>" : "") + "</div>";
    // bring the active arrow into view inside the diagram viewport
    var z = this.zoom, vp = this.vp, hh = this.headH * z;
    var top = r.focusY * z, fx = r.focusX * z, to = { top: vp.scrollTop, left: vp.scrollLeft };
    if (top < vp.scrollTop + hh + 10 || top > vp.scrollTop + vp.clientHeight - 60) to.top = Math.max(0, top - hh - 30);
    if (fx < vp.scrollLeft + 40 || fx > vp.scrollLeft + vp.clientWidth - 40) to.left = Math.max(0, fx - vp.clientWidth / 2);
    if (to.top !== vp.scrollTop || to.left !== vp.scrollLeft) vp.scrollTo({ top: to.top, left: to.left, behavior: "smooth" });
    var li = this.items[n];
    if (li && li.parentNode && li.closest("details").open) {
      var lr = li.getBoundingClientRect(), olr = this.ol.getBoundingClientRect();
      if (lr.top < olr.top || lr.bottom > olr.bottom) this.ol.scrollTop += lr.top - olr.top - 8;
    }
  };
  Widget.prototype.step = function (dlt) {
    var n = this.active + dlt;
    if (this.active === 0 && dlt < 0) n = this.L.count;
    this.setActive(Math.max(1, Math.min(this.L.count, n)));
  };
  Widget.prototype.hover = function (id) {
    this.bodySvg.classList.toggle("has-hover", !!id);
    this.nodes.forEach(function (g) {
      if (g) g.classList.toggle("hov", !!id && (g.getAttribute("data-from") === id || g.getAttribute("data-to") === id));
    });
  };
  Widget.prototype.togglePlay = function () {
    if (this.timer) { this.stop(); return; }
    var self = this;
    if (this.active >= this.L.count) this.setActive(0);
    this.bPlay.textContent = "❚❚ Pause";
    var tick = function () {
      if (self.active >= self.L.count) { self.stop(); return; }
      self.setActive(self.active + 1);
    };
    tick();
    this.timer = setInterval(tick, 2600);
  };
  Widget.prototype.stop = function () {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    if (this.bPlay) this.bPlay.textContent = "▶ Play";
  };
  Widget.prototype.toggleMax = function () {
    var on = !this.root.classList.contains("is-max");
    this.root.classList.toggle("is-max", on);
    document.documentElement.classList.toggle("no-scroll", on);
    this.bMax.textContent = on ? "✕ Close" : "⤢ Expand";
    this.setZoom(on ? Math.max(this.fit(), 0.8) : this.defaultZoom());
    if (on) this.root.focus();
  };

  function init() {
    var data = window.SEQ || {};
    var widgets = [];
    Array.prototype.forEach.call(document.querySelectorAll(".sq[data-seq]"), function (root) {
      var list = data[root.getAttribute("data-seq")];
      if (!list || !list.length) return;
      try { var w = new Widget(root, list); root._sq = w; widgets.push(w); }
      catch (e) { root.innerHTML = '<p class="sq-error">Could not draw the sequence diagram: ' + esc(e.message) + "</p>"; if (window.console) console.error(e); }
    });
    // text widths depend on the web font; redraw once it has loaded
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      widgets.forEach(function (w) { var a = w.active; w.show(w.cur); if (a) w.setActive(a); });
    });
    window.ICHSeq = { open: function (tab) {
      var w = widgets[0]; if (!w) return;
      if (tab != null && tab !== w.cur) w.show(tab);
      w.root.scrollIntoView({ behavior: "smooth", block: "start" });
    } };
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
