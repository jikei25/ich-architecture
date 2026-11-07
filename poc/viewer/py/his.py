"""Simulated HIS/RIS: send an HL7 v2 ORM^O01 order to the PACS (Flow 1.4).

dcm4chee turns the order into a Modality Worklist item that the scanner then
queries with C-FIND. The message goes over MLLP: <VT> message <FS><CR>.
"""
import argparse
import datetime as dt
import os
import socket

from pydicom.uid import generate_uid

VT, FS, CR = b"\x0b", b"\x1c", b"\x0d"


def build_orm(patient_id, name, birth, sex, accession, procedure, priority="S"):
    now = dt.datetime.now()
    ts = now.strftime("%Y%m%d%H%M%S")
    sched = (now + dt.timedelta(minutes=5)).strftime("%Y%m%d%H%M%S")
    ctl = f"MSG{now.strftime('%H%M%S%f')}"
    # OBR-18 accession number, OBR-19 requested procedure ID, OBR-20 scheduled
    # procedure step ID, OBR-24 modality: the fields dcm4chee maps into the MWL.
    obr = [""] * 28
    obr[0] = "OBR"
    obr[1] = "1"
    obr[2] = accession                                  # placer order number
    obr[4] = f"{procedure[0]}^{procedure[1]}^LOCAL"     # universal service ID
    obr[18] = accession
    obr[19] = accession
    obr[20] = accession
    obr[24] = "CT"
    obr[27] = f"^^^{sched}^^{priority}"                  # quantity/timing
    segs = [
        f"MSH|^~\\&|HIS|HOSPITAL|DCM4CHEE|DCM4CHEE|{ts}||ORM^O01|{ctl}|P|2.5.1",
        f"PID|||{patient_id}^^^HOSPITAL||{name}||{birth}|{sex}",
        "PV1||E",
        f"ORC|NW|{accession}|||SC||^^^{sched}^^{priority}",
        "|".join(obr),
        # ZDS (IHE scheduled workflow) carries the Study Instance UID; without it
        # dcm4chee creates no Scheduled Procedure Step, so no worklist item.
        f"ZDS|{generate_uid()}^DCM4CHEE^Application^DICOM",
    ]
    return ctl, "\r".join(segs) + "\r"


def send(msg, host, port):
    with socket.create_connection((host, port), timeout=15) as s:
        s.sendall(VT + msg.encode("utf-8") + FS + CR)
        buf = b""
        while not buf.endswith(FS + CR):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    return buf.strip(VT + FS + CR).decode("utf-8", "replace")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--patient-id", required=True)
    p.add_argument("--name", required=True, help="HL7 name, e.g. NGUYEN^VAN A")
    p.add_argument("--birth", default="19700101")
    p.add_argument("--sex", default="M")
    p.add_argument("--accession", required=True)
    p.add_argument("--priority", default="S", help="S=stat (emergency), R=routine")
    p.add_argument("--host", default=os.environ.get("PACS_HOST", "arc"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PACS_HL7_PORT", "2575")))
    a = p.parse_args()
    ctl, msg = build_orm(a.patient_id, a.name, a.birth, a.sex, a.accession,
                         ("CTHEAD", "CT so nao khong tiem thuoc"), a.priority)
    print("--> HL7 ORM^O01 to PACS", f"{a.host}:{a.port}")
    print(msg.replace("\r", "\n"))
    ack = send(msg, a.host, a.port)
    print("<-- ACK")
    print(ack.replace("\r", "\n"))
    if f"MSA|AA|{ctl}" not in ack:
        raise SystemExit("order was not accepted (expected MSA|AA)")


if __name__ == "__main__":
    main()
