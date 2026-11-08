# Viewer PoC: OHIF + dcm4chee + AI triage

Proof of concept for the viewer part of the ICH architecture (flows 1.3, 1.4, 1.5,
2.4, 2.5). Explanation and results: `viewer.html` on the static site.

| Container | Role | Architecture block |
|---|---|---|
| `arc`, `db`, `ldap` | dcm4chee-arc-light 5.35.2, PostgreSQL, OpenLDAP | PACS |
| `ohif` | OHIF 3.13.14, reads the PACS over DICOMweb | Viewer |
| `ai-worker` | Simulated AI: HU threshold, writes DICOM SEG + SR back to the PACS | Gateway + inference |
| `triage` | AI results service, triage worklist, in-viewer AI panel | AI results DB, priority flag |
| `proxy` | nginx, one origin on port 8000 | Reverse proxy |
| `tools` | `his.py` (HL7 orders), `scanner.py` (MWL C-FIND + C-STORE) | HIS/RIS, CT scanner |

All CT images are synthetic. A "positive" study has a 72 HU lesion that the
simulated AI finds by thresholding.

## Start

Needs Docker with about 3 GB of free memory.

```bash
cd poc/viewer
docker compose up -d --build --wait
```

- Triage worklist: http://localhost:8000/triage/
- OHIF: http://localhost:8000/
- dcm4chee admin UI: http://localhost:8000/dcm4chee-arc/ui2/

Reset everything (empty PACS, no AI results): `docker compose down -v`, then start again.

## Demo for the team (about 10 minutes)

Before the demo: reset the stack, open the triage worklist in a browser and a
terminal in `poc/viewer`. Start the AI with a longer inference time so there is
time to talk while it runs:

```bash
docker compose down -v
INFERENCE_SECONDS=20 docker compose up -d --build --wait
```

| # | Do | Show and say |
|---|---|---|
| 1 | Open http://localhost:8000/triage/ | Empty list, "AI hoạt động". The list is the PACS study list (QIDO-RS) merged with AI results. |
| 2 | `bash demo/scenarios.sh order an` | **Flow 1.4.** The terminal prints the HL7 ORM^O01 and the PACS ACK (`MSA\|AA`). Within 4 s the Modality Worklist table shows the order as SCHEDULED. Raw response: http://localhost:8000/dcm4chee-arc/aets/WORKLIST/rs/mwlitems |
| 3 | `bash demo/scenarios.sh scan an` | **Flow 1.1.** The scanner queries the worklist (C-FIND), so name, ID, accession and Study UID come from the order, then sends 48 images (C-STORE). The study appears with "Chờ AI phân tích", then "AI đang phân tích". It can be read now: nobody waits for the AI. |
| 4 | Wait for the AI | **Flow 2.5.** The row turns red, moves to the top, a toast pops up. The flag is sent before the mask. The result is always "chờ xác nhận". |
| 5 | `bash demo/scenarios.sh case bich` then `bash demo/scenarios.sh case cuong` | Newer studies stay below the flagged one: the AI only raises priority. "AI không thấy dấu hiệu" is not the same as "Không phân tích được" (no thin axial series). |
| 6 | Click "Mở trong OHIF" on NGUYEN VAN AN. Press F12, Network tab, filter `rs/` | **Flow 1.3.** OHIF calls `studies/.../series` (QIDO-RS), then `.../metadata` and `.../frames/1` (WADO-RS). The AI panel (bottom right, "–" collapses it) shows state, volume and model version. The AI SEG and SR series are in the left panel; the overlay is off by default. |
| 7 | Double-click "SEG AI ICH mask", answer Yes, scroll a few slices | **Flow 1.5 / 2.4.** The red overlay is a standard DICOM SEG stored in the PACS; OHIF shows it with no code change. Optional: double-click the SR to show that OHIF cannot render the volumetric report. |
| 8 | Click "Xác nhận", then "Danh sách ↗" | The radiologist's decision is stored; the study leaves the priority group and shows "Bác sĩ đã xác nhận XH". |
| 9 | `bash demo/scenarios.sh case dung`, then open the new study in OHIF right away | The images open immediately; the panel says "AI đang phân tích". When the mask arrives the panel says it came after the study was opened: OHIF reads the series list only once. Click "Tải lại ca" to see the SEG. |
| 10 | `bash demo/scenarios.sh ai-down`, then `bash demo/scenarios.sh case em` | Within 12 s the banner says "AI tạm ngừng". The new study is stored and readable, shown as "AI tạm ngừng", never as negative. |
| 11 | `bash demo/scenarios.sh ai-up` | The AI comes back and processes the study that arrived while it was down; it gets flagged. |

`bash demo/scenarios.sh all` runs cases an, bich, cuong and the AI outage unattended.

## Useful raw requests

```bash
# QIDO-RS: studies, series
curl "http://localhost:8000/dcm4chee-arc/aets/DCM4CHEE/rs/studies"
curl "http://localhost:8000/dcm4chee-arc/aets/DCM4CHEE/rs/studies/<StudyUID>/series"
# WADO-RS: metadata of one series
curl "http://localhost:8000/dcm4chee-arc/aets/DCM4CHEE/rs/studies/<StudyUID>/series/<SeriesUID>/metadata"
# Modality worklist (dcm4chee serves it from the WORKLIST AE)
curl "http://localhost:8000/dcm4chee-arc/aets/WORKLIST/rs/mwlitems"
# AI results service
curl "http://localhost:8000/triage/api/studies"
```

## Shortcuts compared with the architecture

- The AI polls the PACS over DICOMweb; in the architecture the PACS pushes series to the Orthanc gateway and the AI has no PACS access.
- AI results are C-STOREd with calling AE `AI_RESULTS` to the main DICOM port, not to a store-only AE on a separate port.
- The AI panel is a script the proxy injects into OHIF's page; the real one would be an OHIF extension.
- The priority flag goes to the triage service over HTTP and Server-Sent Events, not to HIS/RIS as HL7 ORU.
- No Keycloak login, no TLS, local disk instead of SeaweedFS, SQLite instead of PostgreSQL for AI results.
