#!/usr/bin/env bash
# Drive the PoC during a demo. Watch http://localhost:8000/triage/.
#
#   bash demo/scenarios.sh reset        empty PACS, slow AI (20 s) so there is time to talk
#   bash demo/scenarios.sh tour [act]   guided demo: prints what to look at, waits for Enter
#
#   bash demo/scenarios.sh order an     HIS/RIS sends the HL7 order (Flow 1.4)
#   bash demo/scenarios.sh scan an      scanner reads the worklist, sends images (Flow 1.1)
#   bash demo/scenarios.sh case an      both of the above
#   bash demo/scenarios.sh wait an      print the AI state until the AI has finished
#   bash demo/scenarios.sh ai-down      stop the AI service
#   bash demo/scenarios.sh ai-up        start it again
#   bash demo/scenarios.sh all          every case, unattended
#
# Patients (all synthetic):
#   an     positive       NGUYEN VAN AN   suspected bleed, flagged
#   bich   negative       TRAN THI BICH   no finding
#   cuong  unanalyzable   LE VAN CUONG    only a thick 5 mm series
#   dung   positive       PHAM THI DUNG   open it before the AI is done
#   em     positive       HOANG VAN EM    send it while the AI is down
set -euo pipefail
cd "$(dirname "$0")/.."

URL=http://localhost:8000

tools() { docker compose --progress quiet run --rm -T tools python "$@"; }

patient() {  # sets ID NAME BIRTH SEX ACC KIND
  case "$1" in
    an)    ID=BN101 NAME="NGUYEN^VAN AN"  BIRTH=19650312 SEX=M ACC=ACC2001 KIND=positive ;;
    bich)  ID=BN102 NAME="TRAN^THI BICH"  BIRTH=19800521 SEX=F ACC=ACC2002 KIND=negative ;;
    cuong) ID=BN103 NAME="LE^VAN CUONG"   BIRTH=19720909 SEX=M ACC=ACC2003 KIND=unanalyzable ;;
    dung)  ID=BN104 NAME="PHAM^THI DUNG"  BIRTH=19590101 SEX=F ACC=ACC2004 KIND=positive ;;
    em)    ID=BN105 NAME="HOANG^VAN EM"   BIRTH=19880704 SEX=M ACC=ACC2005 KIND=positive ;;
    *) echo "unknown patient: $1 (an|bich|cuong|dung|em)" >&2; exit 2 ;;
  esac
}

order() {
  patient "$1"
  echo "=== HIS/RIS sends the order for $NAME (Flow 1.4) ==="
  tools his.py --patient-id "$ID" --name "$NAME" --birth "$BIRTH" --sex "$SEX" --accession "$ACC"
}

scan() {
  patient "$1"
  echo "=== Scanner reads the worklist and sends $KIND images (Flow 1.1) ==="
  tools scanner.py --accession "$ACC" --kind "$KIND"
}

# --- Reading what the triage worklist shows -------------------------------

# Ask the triage service (from inside its container, so no curl/jq needed on
# the host). Argument: an accession number, or "online" for the AI heartbeat.
ai_state() {
  docker compose exec -T triage python - "$1" <<'PY' 2>/dev/null || echo "?"
import json, sys, urllib.request
d = json.load(urllib.request.urlopen("http://localhost:8000/api/studies", timeout=10))
if sys.argv[1] == "online":
    print("yes" if d["ai_online"] else "no")
else:
    print(next((s["ai_state"] for s in d["studies"] if s["accession"] == sys.argv[1]), "-"))
PY
}

label() {  # same wording as the triage page
  case "$1" in
    NOT_RUN) echo "Chờ AI phân tích" ;;       RUNNING) echo "AI đang phân tích" ;;
    POSITIVE) echo "Nghi xuất huyết" ;;       NEGATIVE) echo "AI không thấy dấu hiệu" ;;
    UNANALYZABLE) echo "Không phân tích được" ;; NO_RESULT) echo "Không có kết quả AI" ;;
    AI_DOWN) echo "AI tạm ngừng" ;;           -) echo "chưa có trong PACS" ;;
    *) echo "$1" ;;
  esac
}

# Print the AI state of one patient every 2 s until it is final.
wait_ai() {
  patient "$1"
  local t0=$SECONDS s
  while :; do
    s=$(ai_state "$ACC")
    printf '\r   AI cho %-14s %-24s %3ds ' "${NAME/^/ }:" "$(label "$s")" $((SECONDS - t0))
    case "$s" in POSITIVE|NEGATIVE|UNANALYZABLE|NO_RESULT) echo; return ;; esac
    if (( SECONDS - t0 > 120 )); then echo; echo "   (quá 2 phút, bỏ qua)"; return; fi
    sleep 2
  done
}

wait_offline() {
  local t0=$SECONDS
  until [ "$(ai_state online)" = no ]; do
    printf '\r   Chờ danh sách phát hiện AI mất tín hiệu (khoảng 12 s) ... %2ds ' $((SECONDS - t0))
    if (( SECONDS - t0 > 60 )); then echo; echo "   (quá 1 phút, bỏ qua)"; return; fi
    sleep 2
  done
  printf '\r   Danh sách đã báo "AI tạm ngừng" sau %ds.%40s\n' $((SECONDS - t0)) ""
}

# --- Guided tour ----------------------------------------------------------

if [ -t 1 ]; then B=$'\e[1m' D=$'\e[2m' R=$'\e[0m' C=$'\e[36m' Y=$'\e[33m' G=$'\e[32m' M=$'\e[35m'
else B= D= R= C= Y= G= M=; fi

act()   { echo; echo "${B}${M}━━━ MÀN $1: $2 ━━━${R}"; echo "${D}$3${R}"; }
run()   { echo; echo "${C}▶ Lệnh:${R} $*"; }
you()   { echo; echo "${C}▶ Bạn làm:${R} $*"; }
look()  { echo "${Y}  Nhìn:${R} $*"; }
point() { echo "${G}  Ý chính:${R} $*"; }
pause() { [ -t 0 ] || return 0; echo; read -rp "${D}   Enter để tiếp ...${R} " _; }

tour_check() {
  if ! curl -sf "$URL/triage/api/studies" -o /dev/null; then
    echo "Stack chưa chạy. Chạy trước: bash demo/scenarios.sh reset" >&2; exit 1
  fi
  if [ "$(ai_state ACC2001)" != - ] && [ "${1:-1}" = 1 ]; then
    echo "${Y}PACS đã có ca của lượt trước. Nên chạy 'bash demo/scenarios.sh reset' để demo từ đầu.${R}"
  fi
  local inf
  inf=$(docker compose exec -T ai-worker printenv INFERENCE_SECONDS 2>/dev/null || echo "?")
  [ "$inf" -ge 15 ] 2>/dev/null || echo "${Y}AI đang chạy với INFERENCE_SECONDS=$inf; màn 3 cần ≥ 15 s để kịp mở ca trước khi AI xong (reset sẽ đặt 20).${R}"
}

tour1() {
  act 1 "Một ca chụp đi vào hệ thống" \
    "Bệnh nhân NGUYEN VAN AN được chỉ định chụp CT sọ. Xem chỉ định đi từ HIS tới máy chụp, rồi ảnh vào PACS."
  you "mở $URL/triage/ trên màn hình chiếu. Danh sách đang trống, góc phải có 'AI hoạt động'."
  point "đây là danh sách bác sĩ đọc: các ca trong PACS ghép với kết quả AI."
  pause

  run "order an   (HIS/RIS gửi chỉ định HL7 ORM^O01)"
  order an
  look "bảng Modality Worklist ở cuối trang: trong 4 s có dòng NGUYEN VAN AN, trạng thái SCHEDULED."
  look "terminal: dòng MSA|AA trong ACK nghĩa là PACS đã nhận chỉ định."
  point "luồng 1.4: PACS biến chỉ định thành worklist để máy CT tự lấy thông tin bệnh nhân, không ai gõ tay."
  pause

  run "scan an   (máy CT hỏi worklist rồi gửi 48 ảnh)"
  scan an
  look "bảng Ca chụp ở trên: có dòng NGUYEN VAN AN, 48 ảnh, trạng thái 'Chờ AI phân tích' rồi 'AI đang phân tích'."
  point "tên, mã BN, mã chỉ định lấy từ worklist (C-FIND). Ca đã mở đọc được ngay: không ai phải chờ AI."
  pause
}

tour2() {
  act 2 "AI gắn cờ ưu tiên" \
    "AI giả lập đang phân tích ca của AN (khoảng 30 s). Trong lúc chờ, giải thích: AI chạy nền, không chặn việc đọc."
  run "chờ kết quả AI cho AN"
  wait_ai an
  look "dòng của AN chuyển đỏ, có nhãn '▲ ƯU TIÊN', nhảy lên đầu; góc dưới phải hiện thông báo."
  look "nhãn ghi 'Nghi xuất huyết · … mL · chờ xác nhận'."
  point "AI chỉ nói 'nghi', bác sĩ mới là người kết luận. Cờ được gửi trước, mask và báo cáo đến sau."
  pause

  run "case bich, rồi case cuong   (một ca âm tính, một ca AI không đọc được)"
  order bich; scan bich
  order cuong; scan cuong
  echo; wait_ai bich; wait_ai cuong
  look "hai ca mới hơn nhưng vẫn nằm dưới ca của AN."
  look "BICH: 'AI không thấy dấu hiệu'. CUONG: 'Không phân tích được' (chỉ có chuỗi ảnh dày 5 mm)."
  point "AI chỉ được nâng ưu tiên, không bao giờ hạ. 'Không phân tích được' khác hẳn 'âm tính': bác sĩ phải biết AI chưa xem."
  pause
}

tour3() {
  act 3 "Bác sĩ đọc ca trong OHIF" \
    "Đóng vai bác sĩ: mở ca có cờ, xem vùng AI khoanh, rồi xác nhận."
  you "bấm 'Mở trong OHIF' ở dòng NGUYEN VAN AN."
  look "ảnh CT ở giữa; panel AI góc dưới phải, tiêu đề 'AI · NGUYEN VAN AN' (trạng thái, thể tích, phiên bản mô hình); panel trái có chuỗi 'SEG AI ICH mask' và SR."
  point "OHIF đọc ảnh thẳng từ PACS qua DICOMweb. Lớp phủ AI tắt sẵn để bác sĩ nhìn ảnh gốc trước."
  echo "${D}  Tuỳ chọn (khán giả kỹ thuật): F12 → Network → lọc 'rs/' để thấy QIDO-RS (…/series) và WADO-RS (…/metadata, …/frames/1).${R}"
  pause

  you "nhấn đúp 'SEG AI ICH mask' ở panel trái, chọn Yes."
  look "màn hình nhảy tới lát giữa khối máu; vùng đỏ phủ lên khối sáng."
  point "vùng đỏ là DICOM SEG chuẩn AI lưu vào PACS; OHIF hiển thị được mà không sửa mã OHIF."
  pause

  you "bấm 'Xác nhận' trong panel AI, rồi 'Danh sách ↗' để quay lại."
  look "dòng AN hết đỏ, ghi 'Bác sĩ đã xác nhận XH', và xếp lại theo giờ chụp như ca thường."
  point "quyết định của bác sĩ được lưu; ca đã xử lý thì rời nhóm ưu tiên."
  pause

  run "case dung   (ca mới; lần này mở ca TRƯỚC khi AI xong)"
  order dung; scan dung
  you "ngay bây giờ bấm 'Mở trong OHIF' ở dòng PHAM THI DUNG (không chờ AI)."
  look "ảnh mở được ngay; panel AI ghi 'AI đang phân tích'."
  wait_ai dung
  look "panel báo mask đến sau khi ca đã mở. Bấm 'Tải lại ca' để thấy chuỗi SEG."
  point "OHIF chỉ đọc danh sách chuỗi ảnh một lần lúc mở. Bản thật cần extension tự nạp SEG mới."
  pause
}

tour4() {
  act 4 "Khi AI hỏng" \
    "Tắt dịch vụ AI để xem hệ thống còn an toàn không. Quay lại trang danh sách."
  run "ai-down   (dừng container ai-worker)"
  docker compose stop ai-worker
  wait_offline
  look "banner vàng 'AI tạm ngừng' trên cùng; góc phải chuyển 'AI tạm ngừng'."
  pause

  run "case em   (ca đến trong lúc AI ngừng)"
  order em; scan em
  look "ca của HOANG VAN EM vẫn vào PACS, mở đọc được, nhãn 'AI tạm ngừng'."
  point "AI hỏng không chặn việc chụp và đọc. Ca không có cờ không bao giờ trông giống ca âm tính."
  pause

  run "ai-up   (bật lại AI)"
  docker compose start ai-worker
  wait_ai em
  look "AI tự xử lý bù ca của EM; ca được gắn cờ và lên đầu."
  point "không mất ca nào trong lúc AI ngừng."
  pause
}

tour() {
  local from="${1:-1}"
  case "$from" in 1|2|3|4) ;; *) echo "act must be 1-4" >&2; exit 2 ;; esac
  tour_check "$from"
  echo "${B}Demo trình xem PoC: 4 màn, khoảng 10 phút. Mở $URL/triage/ trên màn hình chiếu.${R}"
  echo "${D}Mỗi bước in: lệnh đang chạy, chỗ cần nhìn, và ý chính để nói. Enter để sang bước tiếp.${R}"
  local i
  for i in 1 2 3 4; do (( i < from )) || "tour$i"; done
  echo
  echo "${B}${M}━━━ TÓM TẮT ━━━${R}"
  echo "  1. Chỉ định HL7 → worklist → máy CT → PACS: định danh đi tự động, ảnh đọc được ngay."
  echo "  2. AI chạy nền, chỉ nâng ưu tiên ca nghi xuất huyết và luôn chờ bác sĩ xác nhận."
  echo "  3. OHIF hiển thị mask AI (DICOM SEG) không cần sửa; ưu tiên, thông báo và panel AI phải tự làm."
  echo "  4. AI hỏng thì hệ thống vẫn chạy, ca không bao giờ bị hiểu nhầm là âm tính, AI lên lại thì xử lý bù."
}

cmd="${1:-help}"
case "$cmd" in
  reset)
    docker compose down -v
    INFERENCE_SECONDS="${INFERENCE_SECONDS:-20}" docker compose up -d --build --wait
    echo "Ready: $URL/triage/   Next: bash demo/scenarios.sh tour" ;;
  tour) tour "${2:-1}" ;;
  order) order "${2:?patient}" ;;
  scan) scan "${2:?patient}" ;;
  case) order "${2:?patient}"; echo; scan "$2" ;;
  wait) wait_ai "${2:?patient}" ;;
  ai-down) docker compose stop ai-worker ;;
  ai-up) docker compose start ai-worker ;;
  all)
    for p in an bich cuong; do order "$p"; scan "$p"; sleep 15; done
    docker compose stop ai-worker
    order em; scan em
    echo "AI is down; waiting 20 s so the worklist shows it ..."; sleep 20
    docker compose start ai-worker ;;
  *) sed -n '/^set -euo/q;2,$p' "$0"; exit 1 ;;
esac
