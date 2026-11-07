// In-viewer AI panel for OHIF, injected by the proxy into OHIF's index.html.
// PoC shortcut: the production version is an OHIF extension (a panel module
// plus UINotificationService). The behaviour is the same:
//   * show the AI state of the open study (never styled like a negative),
//   * let the radiologist confirm or reject the AI result,
//   * alert when another study is flagged,
//   * tell the radiologist when the AI mask arrives after the study was opened,
//     because OHIF reads the series list only once, when the study opens.
(() => {
  const API = "/triage/api";
  const LABEL = {
    NOT_RUN: ["Chưa chạy AI", "#9aa0c0"],
    RUNNING: ["AI đang phân tích…", "#93c5fd"],
    POSITIVE: ["Nghi xuất huyết não", "#f87171"],
    NEGATIVE: ["AI không thấy dấu hiệu xuất huyết", "#6ee7b7"],
    UNANALYZABLE: ["Không phân tích được: thiếu chuỗi CT trục lát mỏng", "#fbbf24"],
    NO_RESULT: ["Không có kết quả AI (lỗi hoặc quá hạn)", "#fbbf24"],
    AI_DOWN: ["AI tạm ngừng", "#fbbf24"],
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const css = `
#ich-ai{position:fixed;right:16px;bottom:16px;z-index:99999;width:340px;font:13px/1.45 system-ui,sans-serif;color:#e8eaf6;
  background:#171b2e;border:1px solid #2a3050;border-radius:12px;box-shadow:0 10px 30px #000a}
#ich-ai .hd{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-bottom:1px solid #2a3050;font-weight:600}
#ich-ai .bd{padding:10px 12px}
#ich-ai .st{font-weight:700;font-size:14px}
#ich-ai .meta{color:#9aa0c0;font-size:12px;margin-top:4px}
#ich-ai .tag{display:inline-block;margin-top:6px;padding:2px 8px;border-radius:999px;background:#33270d;color:#fbbf24;font-size:11.5px;font-weight:600}
#ich-ai .acts{display:flex;gap:8px;margin-top:10px}
#ich-ai button,#ich-ai a.b{flex:1;border:0;border-radius:8px;padding:7px 8px;font:inherit;font-weight:600;cursor:pointer;text-align:center;text-decoration:none}
#ich-ai .ok{background:#7f1d1d;color:#fee2e2}#ich-ai .no{background:#2b3563;color:#e8eaf6}
#ich-ai .new{margin-top:10px;padding:8px;border-radius:8px;background:#14223f;color:#93c5fd}
#ich-ai .hint{margin-top:8px;color:#9aa0c0;font-size:12px}
#ich-ai a{color:#93c5fd}
#ich-ai-toast{position:fixed;right:372px;bottom:16px;z-index:99999;width:300px;font:13px/1.45 system-ui,sans-serif;color:#e8eaf6;
  background:#171b2e;border:1px solid #f87171;border-left:6px solid #f87171;border-radius:10px;padding:10px 12px;box-shadow:0 10px 30px #000a}`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  let box, uid, segAtOpen = null, current = null;

  const studyUid = () => new URLSearchParams(location.search).get("StudyInstanceUIDs");

  function ensureBox() {
    if (box) return box;
    box = document.createElement("div");
    box.id = "ich-ai";
    document.body.appendChild(box);
    return box;
  }

  function render(s, extra = "") {
    const [label, color] = LABEL[s.ai_state] || [s.ai_state, "#9aa0c0"];
    const reviewable = (s.ai_state === "POSITIVE" || s.ai_state === "NEGATIVE") && !s.review;
    const vol = s.ai_state === "POSITIVE" && s.volume_ml != null ? ` · ${s.volume_ml} mL` : "";
    const review = s.review === "CONFIRMED" ? "Bác sĩ đã xác nhận" : s.review === "REJECTED" ? "Bác sĩ đã bác bỏ kết quả AI" : "";
    ensureBox().innerHTML = `
      <div class="hd"><span>Kết quả AI · ${esc(s.patient_name)}</span><a href="/triage/" title="Danh sách ưu tiên">Danh sách ↗</a></div>
      <div class="bd">
        <div class="st" style="color:${color}">${esc(label)}${esc(vol)}</div>
        ${reviewable ? '<span class="tag">CHƯA XÁC NHẬN · chỉ hỗ trợ, không phải kết luận</span>' : ""}
        ${review ? `<div class="meta"><b>${esc(review)}</b></div>` : ""}
        ${s.model_version ? `<div class="meta">Mô hình ${esc(s.model_version)} · tiền xử lý ${esc(s.preprocessing_hash || "")}</div>` : ""}
        ${s.ai_state === "POSITIVE" && s.seg_series_uid && segAtOpen ? '<div class="hint">Lớp phủ mặc định tắt. Bật: nhấn đúp thumbnail <b>SEG</b> “AI ICH mask” ở panel trái.</div>' : ""}
        ${extra}
        ${reviewable ? `<div class="acts"><button class="ok" data-d="CONFIRMED">Xác nhận</button><button class="no" data-d="REJECTED">Bác bỏ</button></div>` : ""}
      </div>`;
    box.querySelectorAll("button[data-d]").forEach((b) => b.onclick = () => review(b.dataset.d));
  }

  async function load() {
    const u = studyUid();
    if (!u) { if (box) box.remove(); box = null; uid = null; return; }
    try {
      const r = await fetch(`${API}/studies/${encodeURIComponent(u)}`);
      if (!r.ok) return;
      current = await r.json();
      if (u !== uid) { uid = u; segAtOpen = current.seg_series_uid; }
      const late = current.seg_series_uid && !segAtOpen
        ? '<div class="new">Mask AI vừa về PACS sau khi ca được mở. OHIF chỉ đọc danh sách chuỗi lúc mở ca. <a href="#" id="ich-reload">Tải lại ca</a> để thấy chuỗi SEG.</div>'
        : "";
      render(current, late);
      const rl = document.getElementById("ich-reload");
      if (rl) rl.onclick = (e) => { e.preventDefault(); location.reload(); };
    } catch (e) { console.warn("ICH AI panel", e); }
  }

  async function review(decision) {
    await fetch(`${API}/studies/${encodeURIComponent(uid)}/review`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }),
    });
    load();
  }

  async function alertOther(ev) {
    const r = await fetch(`${API}/studies/${encodeURIComponent(ev.study_uid)}`);
    if (!r.ok) return;
    const s = await r.json();
    document.getElementById("ich-ai-toast")?.remove();
    const t = document.createElement("div");
    t.id = "ich-ai-toast";
    t.innerHTML = `<b style="color:#f87171">Ca nghi xuất huyết mới</b><br>${esc(s.patient_name)} · ${esc(s.accession)}
      <div style="margin-top:6px"><a style="color:#93c5fd" href="/viewer?StudyInstanceUIDs=${encodeURIComponent(s.study_uid)}">Mở ca</a></div>`;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 15000);
  }

  const es = new EventSource(`${API}/events`);
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.study_uid && ev.study_uid === uid) return load();
    if (ev.type === "result" && ev.state === "POSITIVE" && !ev.seg_series_uid && ev.study_uid !== uid) alertOther(ev);
    if (ev.type === "ai_status") load();
  };

  // OHIF is a single-page app: follow route changes.
  let last = "";
  setInterval(() => { if (location.href !== last) { last = location.href; load(); } }, 700);
  setInterval(load, 5000);
})();
