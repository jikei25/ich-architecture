/* Shared page behaviour: theme toggle, scroll progress, contents scrollspy,
   architecture diagram focus / zoom / expand, cross-links between flow sections
   and diagrams, back-to-top. Loaded before sequence.js (which uses ICHPan). */
(function () {
  "use strict";
  var root = document.documentElement;

  /* drag-to-pan for scrollable diagram areas (mouse only; touch scrolls natively) */
  window.ICHPan = function (el) {
    var down = false, moved = false, sx, sy, sl, st;
    el.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      if (el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight) return;
      down = true; moved = false; sx = e.clientX; sy = e.clientY; sl = el.scrollLeft; st = el.scrollTop;
    });
    window.addEventListener("pointermove", function (e) {
      if (!down) return;
      var dx = e.clientX - sx, dy = e.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) > 5) { moved = true; el.classList.add("panning"); }
      if (moved) { el.scrollLeft = sl - dx; el.scrollTop = st - dy; }
    });
    window.addEventListener("pointerup", function () {
      if (!down) return;
      down = false; el.classList.remove("panning");
      if (moved) { el.dataset.panned = "1"; setTimeout(function () { delete el.dataset.panned; }, 0); }
    });
  };

  function ready(fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); }

  ready(function () {
    /* ---------- theme ---------- */
    var themeBtn = document.querySelector(".theme-btn");
    var THEMES = ["auto", "light", "dark"], ICON = { auto: "◐", light: "☀", dark: "☾" }, NAME = { auto: "Auto", light: "Light", dark: "Dark" };
    function currentTheme() { return root.getAttribute("data-theme") || "auto"; }
    function paintTheme() {
      if (!themeBtn) return;
      var t = currentTheme();
      themeBtn.innerHTML = ICON[t] + ' <span class="tl">' + NAME[t] + "</span>";
      themeBtn.title = "Theme: " + NAME[t] + " (click to change)";
      themeBtn.setAttribute("aria-label", themeBtn.title);
    }
    if (themeBtn) themeBtn.addEventListener("click", function () {
      var t = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
      if (t === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", t);
      try { if (t === "auto") localStorage.removeItem("ich-theme"); else localStorage.setItem("ich-theme", t); } catch (e) {}
      paintTheme();
    });
    paintTheme();

    /* ---------- section anchors ---------- */
    var heads = Array.prototype.slice.call(document.querySelectorAll("h2.sec[id]"));
    heads.forEach(function (hd) {
      var a = document.createElement("a");
      a.className = "hlink"; a.href = "#" + hd.id; a.textContent = "#"; a.setAttribute("aria-label", "Link to this section");
      hd.appendChild(a);
    });

    /* ---------- scroll progress, scrollspy, back to top ---------- */
    var bar = document.querySelector(".progress span");
    var links = {};
    Array.prototype.forEach.call(document.querySelectorAll("nav.toc a[href^='#']"), function (a) { links[a.getAttribute("href").slice(1)] = a; });
    var toTop = document.createElement("button");
    toTop.type = "button"; toTop.className = "totop"; toTop.textContent = "↑"; toTop.title = "Back to top"; toTop.setAttribute("aria-label", "Back to top");
    toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    document.body.appendChild(toTop);
    var lastActive = null, ticking = false;
    function onScroll() {
      ticking = false;
      var y = window.scrollY, max = document.documentElement.scrollHeight - window.innerHeight;
      if (bar) bar.style.width = (max > 0 ? Math.min(100, (y / max) * 100) : 0) + "%";
      toTop.classList.toggle("show", y > 900);
      var cur = null;
      for (var i = 0; i < heads.length; i++) { if (heads[i].getBoundingClientRect().top < 140) cur = heads[i].id; else break; }
      if (y >= max - 4 && heads.length) cur = heads[heads.length - 1].id;
      if (cur !== lastActive) {
        if (lastActive && links[lastActive]) links[lastActive].classList.remove("active");
        if (cur && links[cur]) links[cur].classList.add("active");
        lastActive = cur;
      }
    }
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
    onScroll();

    /* ---------- architecture diagram ---------- */
    var svg = document.getElementById("arch");
    var fig = svg && svg.closest(".figure");
    var focusBtns = Array.prototype.slice.call(document.querySelectorAll(".focusbar button[data-f]"));
    var cap = document.querySelector(".focuscap");
    function focus(f) {
      if (!svg) return;
      if (f) svg.setAttribute("data-focus", f); else svg.removeAttribute("data-focus");
      var on = null;
      focusBtns.forEach(function (b) { var m = b.getAttribute("data-f") === (f || ""); b.setAttribute("aria-pressed", m ? "true" : "false"); if (m) on = b; });
      if (cap) {
        var desc = on && on.getAttribute("data-desc"), sec = on && on.getAttribute("data-sec");
        cap.innerHTML = desc ? desc + (sec ? ' <a href="#' + sec + '">Read the steps ↓</a>' : "") : "";
        cap.classList.toggle("show", !!desc);
      }
    }
    window.ICHFocus = focus;
    focusBtns.forEach(function (b) { b.addEventListener("click", function () { focus(b.getAttribute("data-f")); }); });
    if (svg) {
      var scroller = svg.closest(".figscroll");
      svg.addEventListener("click", function (e) {
        if (scroller && scroller.dataset.panned) return;
        var g = e.target.closest("[data-g]");
        if (!g) return;
        var f = g.getAttribute("data-g");
        focus(svg.getAttribute("data-focus") === f ? "" : f);
      });
      if (scroller) window.ICHPan(scroller);
    }

    if (fig && svg) {
      var tools = document.createElement("div");
      tools.className = "figtools";
      var zoom = null, NATURAL = svg.viewBox.baseVal.width || 1840;
      var mkb = function (label, title, fn) {
        var b = document.createElement("button"); b.type = "button"; b.textContent = label; b.title = title; b.setAttribute("aria-label", title);
        b.addEventListener("click", fn); tools.appendChild(b); return b;
      };
      var applyZoom = function () {
        if (zoom == null) { svg.style.width = ""; svg.style.minWidth = ""; bFit.textContent = "Fit"; }
        else { svg.style.width = Math.round(NATURAL * zoom) + "px"; svg.style.minWidth = "0"; bFit.textContent = Math.round(zoom * 100) + "%"; }
      };
      var curZoom = function () { return zoom == null ? svg.getBoundingClientRect().width / NATURAL : zoom; };
      mkb("−", "Zoom out", function () { zoom = Math.max(0.4, curZoom() / 1.25); applyZoom(); });
      var bFit = mkb("Fit", "Fit to width", function () { zoom = null; applyZoom(); });
      mkb("+", "Zoom in", function () { zoom = Math.min(2.5, curZoom() * 1.25); applyZoom(); });
      var bMax = mkb("⤢ Expand", "Expand to full screen", function () { toggleMax(); });
      var toggleMax = function (force) {
        var on = force != null ? force : !fig.classList.contains("is-max");
        fig.classList.toggle("is-max", on);
        root.classList.toggle("no-scroll", on);
        bMax.textContent = on ? "✕ Close" : "⤢ Expand";
        zoom = null; applyZoom();
      };
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && fig.classList.contains("is-max")) toggleMax(false); });
      var fb = fig.querySelector(".focusbar");
      (fb || fig).appendChild(tools);
    }

    /* ---------- flow sections: jump to the diagrams ---------- */
    Array.prototype.forEach.call(document.querySelectorAll("h2.sec[data-flow], h2.sec[data-seq]"), function (hd) {
      var box = document.createElement("div");
      box.className = "jumps";
      var flow = hd.getAttribute("data-flow"), seq = hd.getAttribute("data-seq");
      if (flow && svg) {
        var b1 = document.createElement("button");
        b1.type = "button"; b1.textContent = "◎ Highlight in architecture diagram";
        b1.addEventListener("click", function () { focus(flow); document.getElementById("diagram").scrollIntoView({ behavior: "smooth", block: "start" }); });
        box.appendChild(b1);
      }
      if (seq != null) {
        var b2 = document.createElement("button");
        b2.type = "button"; b2.textContent = "⇅ Open sequence diagram";
        b2.addEventListener("click", function () { if (window.ICHSeq) window.ICHSeq.open(+seq); });
        box.appendChild(b2);
      }
      hd.insertAdjacentElement("afterend", box);
    });

    /* open a sequence tab from a link such as #sequence-2 */
    function fromHash(initial) {
      var m = /^#sequence-(\d+)$/.exec(location.hash);
      if (m && window.ICHSeq) { window.ICHSeq.open(+m[1] - 1); return; }
      // the diagrams and buttons added above shift the page, so redo the browser's initial anchor jump
      var t = initial === true && location.hash && document.getElementById(location.hash.slice(1));
      if (t) t.scrollIntoView({ block: "start" });
    }
    window.addEventListener("hashchange", fromHash);
    if (document.readyState === "complete") setTimeout(function () { fromHash(true); }, 0);
    else window.addEventListener("load", function () { setTimeout(function () { fromHash(true); }, 0); });
  });
})();
