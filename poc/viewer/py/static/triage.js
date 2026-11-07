// Triage worklist: study list from the PACS merged with AI results, live over SSE.
const LABEL = {
  NOT_RUN: "Chưa chạy AI",
  RUNNING: "AI đang phân tích",
  POSITIVE: "Nghi xuất huyết",
  NEGATIVE: "AI không thấy dấu hiệu",
  UNANALYZABLE: "Không phân tích được",
  NO_RESULT: "Không có kết quả AI",
  AI_DOWN: "AI tạm ngừng",
};
const REVIEW = { CONFIRMED: "Đã xác nhận XH", REJECTED: "Bác bỏ kết quả AI" };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const viewerUrl = (uid) => `/viewer?StudyInstanceUIDs=${encodeURIComponent(uid)}`;
let lastStudies = [];
let flashUid = null;

function aiChip(s) {
  let t = LABEL[s.ai_state] || s.ai_state;
  if (s.ai_state === "POSITIVE" && s.volume_ml != null) t += ` · ${s.volume_ml} mL`;
  if ((s.ai_state === "POSITIVE" || s.ai_state === "NEGATIVE") && !s.review) t += " · chờ xác nhận";
  return `<span class="chip ${s.ai_state}">${esc(t)}</span>`;
}

function render(data) {
  const pill = document.getElementById("ai-pill");
  pill.className = "pill " + (data.ai_online ? "on" : "off");
  pill.textContent = data.ai_online ? `AI hoạt động · ${data.model_version || ""}` : "AI tạm ngừng";
  document.getElementById("ai-banner").hidden = data.ai_online;
  lastStudies = data.studies;
  const tb = document.getElementById("studies");
  if (!data.studies.length) {
    tb.innerHTML = `<tr><td colspan="8" class="empty">Chưa có ca nào trong PACS</td></tr>`;
    return;
  }
  tb.innerHTML = data.studies.map((s) => {
    const flagged = s.ai_state === "POSITIVE" && !s.review;
    return `<tr class="${flagged ? "flag" : ""} ${s.study_uid === flashUid ? "flash" : ""}" data-uid="${esc(s.study_uid)}">
      <td>${flagged ? '<span class="prio" title="AI nâng ưu tiên">▲ ƯU TIÊN</span>' : ""}</td>
      <td><b>${esc(s.patient_name)}</b><br><span class="rev">${esc(s.patient_id)}</span></td>
      <td>${esc(s.accession)}</td>
      <td>${esc(s.time.replace(/(\d\d)(\d\d)(\d\d)/, "$1:$2:$3"))}</td>
      <td>${esc((s.modalities || []).join(", "))} · ${esc(s.instances)} ảnh</td>
      <td>${aiChip(s)}</td>
      <td><span class="rev ${esc(s.review)}">${esc(REVIEW[s.review] || "")}</span></td>
      <td><a class="btn" href="${viewerUrl(s.study_uid)}">Mở trong OHIF</a></td>
    </tr>`;
  }).join("");
}

function renderMwl(data) {
  const tb = document.getElementById("mwl");
  tb.innerHTML = data.items.length
    ? data.items.map((m) => `<tr><td>${esc(m.patient_name)}</td><td>${esc(m.patient_id)}</td><td>${esc(m.accession)}</td>
        <td>${esc(m.procedure)}</td><td>${esc(m.modality)}</td><td>${esc(m.start)}</td><td>${esc(m.status)}</td></tr>`).join("")
    : `<tr><td colspan="7" class="empty">Chưa có chỉ định nào</td></tr>`;
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
