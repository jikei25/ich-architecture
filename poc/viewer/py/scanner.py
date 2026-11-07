"""Simulated CT scanner (Flows 1.1 and 1.4).

1. Query the Modality Worklist on the PACS with C-FIND (by accession number),
   so patient and order details come from the order, not from typing.
2. "Scan": generate a synthetic head CT carrying those details.
3. Send it to the PACS with C-STORE.

Kinds of study, to exercise every AI state in the viewer:
  positive       thin axial series with a hyperdense lesion
  negative       thin axial series, no lesion
  unanalyzable   only a thick 5 mm series, which the AI contract rejects
"""
import argparse
import os
import time

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage, ModalityWorklistInformationFind

from synthetic_ct import make_series

CALLING_AE = "CT_SCANNER"


def query_mwl(host, port, called, accession):
    ae = AE(ae_title=CALLING_AE)
    ae.add_requested_context(ModalityWorklistInformationFind)
    q = Dataset()
    q.AccessionNumber = accession
    q.PatientName = ""
    q.PatientID = ""
    q.PatientBirthDate = ""
    q.PatientSex = ""
    q.StudyInstanceUID = ""
    q.RequestedProcedureDescription = ""
    q.RequestedProcedureID = ""
    sps = Dataset()
    sps.Modality = ""
    sps.ScheduledStationAETitle = ""
    sps.ScheduledProcedureStepStartDate = ""
    sps.ScheduledProcedureStepID = ""
    sps.ScheduledProcedureStepDescription = ""
    q.ScheduledProcedureStepSequence = [sps]
    assoc = ae.associate(host, port, ae_title=called)
    if not assoc.is_established:
        raise SystemExit("could not open an association to the PACS")
    items = []
    for status, ident in assoc.send_c_find(q, ModalityWorklistInformationFind):
        if status and status.Status in (0xFF00, 0xFF01) and ident is not None:
            items.append(ident)
    assoc.release()
    return items


def c_store(datasets, host, port, called):
    ae = AE(ae_title=CALLING_AE)
    ae.add_requested_context(CTImageStorage)
    assoc = ae.associate(host, port, ae_title=called)
    if not assoc.is_established:
        raise SystemExit("could not open an association to the PACS")
    ok = 0
    for ds in datasets:
        st = assoc.send_c_store(ds)
        ok += bool(st and st.Status == 0x0000)
    assoc.release()
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--accession", required=True)
    p.add_argument("--kind", choices=["positive", "negative", "unanalyzable"], required=True)
    p.add_argument("--host", default=os.environ.get("PACS_HOST", "arc"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PACS_DICOM_PORT", "11112")))
    p.add_argument("--aet", default=os.environ.get("PACS_AET", "DCM4CHEE"))
    p.add_argument("--mwl-aet", default="WORKLIST", help="dcm4chee's worklist AE")
    a = p.parse_args()

    print(f"--> C-FIND Modality Worklist, AccessionNumber={a.accession}")
    items = query_mwl(a.host, a.port, a.mwl_aet, a.accession)
    if not items:
        raise SystemExit("no worklist item: send the HL7 order first (his.py)")
    w = items[0]
    print(f"<-- {len(items)} item(s): {w.PatientName} / {w.PatientID} / "
          f"StudyInstanceUID={w.get('StudyInstanceUID', '')}")

    patient = {
        "PatientName": w.PatientName,
        "PatientID": w.PatientID,
        "PatientBirthDate": w.get("PatientBirthDate", ""),
        "PatientSex": w.get("PatientSex", ""),
    }
    study = {
        "StudyInstanceUID": w.get("StudyInstanceUID") or generate_uid(),
        "AccessionNumber": a.accession,
        "StudyDescription": w.get("RequestedProcedureDescription") or "CT head",
    }
    if a.kind == "unanalyzable":
        series = make_series(patient, study, positive=False, thickness_mm=5.0, n_slices=14,
                             description="Head non-contrast AXIAL 5mm")
    else:
        series = make_series(patient, study, positive=a.kind == "positive")

    t0 = time.monotonic()
    print(f"--> C-STORE {len(series)} images to {a.aet}@{a.host}:{a.port}")
    ok = c_store(series, a.host, a.port, a.aet)
    print(f"<-- {ok}/{len(series)} stored in {time.monotonic() - t0:.1f}s")
    print(f"StudyInstanceUID={study['StudyInstanceUID']}")


if __name__ == "__main__":
    main()
