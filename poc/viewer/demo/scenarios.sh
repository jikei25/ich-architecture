#!/usr/bin/env bash
# Drive the PoC by hand during a demo. Watch http://localhost:8000/triage/.
#
#   bash demo/scenarios.sh order an     HIS/RIS sends the HL7 order (Flow 1.4)
#   bash demo/scenarios.sh scan an      scanner reads the worklist, sends images (Flow 1.1)
#   bash demo/scenarios.sh case an      both of the above
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

tools() { docker compose run --rm -T tools python "$@"; }

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

cmd="${1:-help}"
case "$cmd" in
  order) order "${2:?patient}" ;;
  scan) scan "${2:?patient}" ;;
  case) order "${2:?patient}"; echo; scan "$2" ;;
  ai-down) docker compose stop ai-worker ;;
  ai-up) docker compose start ai-worker ;;
  all)
    for p in an bich cuong; do order "$p"; scan "$p"; sleep 15; done
    docker compose stop ai-worker
    order em; scan em
    echo "AI is down; waiting 20 s so the worklist shows it ..."; sleep 20
    docker compose start ai-worker ;;
  *) sed -n '2,19p' "$0"; exit 1 ;;
esac
