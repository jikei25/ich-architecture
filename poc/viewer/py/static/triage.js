// Triage worklist: study list from the PACS merged with AI results, live over SSE.
const LABEL = {
  NOT_RUN: "Chờ AI phân tích",
  RUNNING: "AI đang phân tích",
  POSITIVE: "Nghi xuất huyết",
  NEGATIVE: "AI không thấy dấu hiệu",
  UNANALYZABLE: "Không phân tích được",
  NO_RESULT: "Không có kết quả AI",
  AI_DOWN: "AI tạm ngừng",
};
const REVIEW = { CONFIRMED: "Bác sĩ đã xác nhận XH", REJECTED: "Bác sĩ bác bỏ kết quả AI" };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const viewerUrl = (uid) => `/viewer?StudyInstanceUIDs=${encodeURIComponent(uid)}`;
const hhmm = (t) => String(t || "").replace(/^(\d\d)(\d\d)(\d\d).*/, "$1:$2:$3");
let lastStudies = [];
let lastHtml = { studies: "", mwl: "" };
let flashUid = null;

function aiChip(s) {
  let t = LABEL[s.ai_state] || s.ai_state;
  if (s.ai_state === "POSITIVE" && s.volume_ml != null) t += ` · ${s.volume_ml} mL`;
  if ((s.ai_state === "POSITIVE" || s.ai_state === "NEGATIVE") && !s.review) t += " · chờ xác nhận";
  return `<span class="chip ${s.ai_state}">${esc(t)}</span>`;
}

// Re-render only when the content changed, so rows don't flicker and links
// stay clickable between the 4 s refreshes.
function setRows(id, html) {
  if (lastHtml[id] === html) return;
  lastHtml[id] = html;
  document.getElementById(id).innerHTML = html;
}

function render(data) {
  const pill = document.getElementById("ai-pill");
  pill.className = "pill " + (data.ai_online ? "on" : "off");
  pill.textContent = data.ai_online ? `AI hoạt động · ${data.model_version || ""}` : "AI tạm ngừng";
  document.getElementById("ai-banner").hidden = data.ai_online;
  lastStudies = data.studies;
  if (!data.studies.length) {
    setRows("studies", `<tr><td colspan="5" class="empty">Chưa có ca nào trong PACS. Gửi chỉ định rồi chụp: <code>bash demo/scenarios.sh case an</code></td></tr>`);
    return;
  }
  setRows("studies", data.studies.map((s) => {
    const flagged = s.ai_state === "POSITIVE" && !s.review;
    const cls = [flagged ? "flag" : "", s.study_uid === flashUid ? "flash" : ""].join(" ").trim();
    return `<tr class="${cls}">
      <td class="who">${flagged ? '<span class="prio" title="AI nâng ưu tiên">▲ ƯU TIÊN</span>' : ""}<b>${esc(s.patient_name)}</b>
        <span class="sub2">${esc(s.patient_id)} · ${esc(s.accession)}</span></td>
      <td>${esc(hhmm(s.time))}</td>
      <td>${esc((s.modalities || []).join(", "))}<span class="sub2">${esc(s.instances)} ảnh</span></td>
      <td>${aiChip(s)}${s.review ? `<span class="rev ${esc(s.review)}">${esc(REVIEW[s.review] || "")}</span>` : ""}</td>
      <td class="act"><a class="btn" href="${viewerUrl(s.study_uid)}">Mở trong OHIF</a></td>
    </tr>`;
  }).join(""));
}

function when(start) {  // "20261108 1842" -> "08/11 18:42"
  const m = /^(\d{4})(\d\d)(\d\d) (\d\d)(\d\d)/.exec(start || "");
  return m ? `${m[3]}/${m[2]} ${m[4]}:${m[5]}` : start;
}

function renderMwl(data) {
  setRows("mwl", data.items.length
    ? data.items.map((m) => `<tr><td><b>${esc(m.patient_name)}</b><span class="sub2">${esc(m.patient_id)}</span></td>
        <td>${esc(m.accession)}</td><td>${esc(m.procedure)} · ${esc(m.modality)}</td><td>${esc(when(m.start))}</td>
        <td><span class="chip NOT_RUN">${esc(m.status)}</span></td></tr>`).join("")
    : `<tr><td colspan="5" class="empty">Chưa có chỉ định nào. Gửi chỉ định: <code>bash demo/scenarios.sh order an</code></td></tr>`);
}

async function refresh() {
  try {
    const [st, mw] = await Promise.all([fetch("api/studies"), fetch("api/mwl")]);
    render(await st.json());
    renderMwl(await mw.json());
  } catch (e) { console.warn(e); }
}

function toast(s) {
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<b>Ca nghi xuất huyết não</b> (AI, chưa xác nhận)
    <div>${esc(s.patient_name)} · ${esc(s.accession)}${s.volume_ml != null ? ` · ${esc(s.volume_ml)} mL` : ""}</div>
    <div class="row"><span class="rev">Ca đã được đưa lên đầu danh sách</span><a class="btn" href="${viewerUrl(s.study_uid)}">Mở ca</a></div>`;
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => el.remove(), 15000);
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("Ca nghi xuất huyết não", { body: `${s.patient_name} · ${s.accession}` });
  }
}

const es = new EventSource("api/events");
es.onmessage = async (m) => {
  const ev = JSON.parse(m.data);
  if (ev.type === "result" && ev.state === "POSITIVE" && !ev.seg_series_uid) {
    flashUid = ev.study_uid;
    setTimeout(() => { flashUid = null; }, 3000);
    await refresh();
    const s = lastStudies.find((x) => x.study_uid === ev.study_uid);
    if (s) toast(s);
    return;
  }
  refresh();
};

if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
refresh();
setInterval(refresh, 4000);
