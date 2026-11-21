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

Reset everything (empty PACS, no AI results): `bash demo/scenarios.sh reset`.

## Demo for the team (about 10 minutes)

The demo tells one story in four acts: a head CT goes from the order to the
radiologist's confirmation, then the AI goes down. The `tour` command runs it
step by step in the terminal: for each step it prints the command it runs,
where to look on screen and the point to make, then waits for Enter. The
Vietnamese version of this guide, with a status cheat sheet, is section 9 of
`viewer.html`.

Needs Docker and a terminal with `bash` (on Windows: Git Bash).

```bash
cd poc/viewer
bash demo/scenarios.sh reset   # empty PACS, AI takes 20 s per study so there is time to talk
bash demo/scenarios.sh tour    # start the demo; "tour 3" jumps to act 3
```

Show http://localhost:8000/triage/ on the projector and keep the terminal next to it.

| Act | Do | Look at | Point to make |
|---|---|---|---|
| 1. A study enters the system | `order an` | Modality Worklist table (bottom): NGUYEN VAN AN, SCHEDULED within 4 s. Terminal: `MSA\|AA` | **Flow 1.4.** HIS sends HL7 ORM^O01, the PACS builds the worklist for the scanner. Nobody types the patient's name. |
| | `scan an` | Study table: AN, 48 images, "Chờ AI phân tích", then "AI đang phân tích" | **Flow 1.1.** The scanner takes the identifiers from the worklist (C-FIND), sends images (C-STORE). The study can be read now: nobody waits for the AI. |
| 2. The AI flags it | wait about 25 s (the terminal counts) | AN turns red, "▲ ƯU TIÊN", moves to the top, toast bottom right | **Flow 2.5.** The AI only says "suspected"; the radiologist decides. The flag is sent before the mask and report. |
| | `case bich`, `case cuong` | Newer studies stay below AN. BICH "AI không thấy dấu hiệu", CUONG "Không phân tích được" | The AI only raises priority. "Unanalyzable" (no thin axial series) is not "negative": the AI never looked. |
| 3. The radiologist reads it in OHIF | "Mở trong OHIF" on AN | AI panel bottom right; AI SEG and SR series in the left panel; overlay off | **Flow 1.3.** OHIF reads the PACS over DICOMweb. Optional: F12, Network, filter `rs/` for QIDO-RS and WADO-RS. |
| | double-click "SEG AI ICH mask", Yes | The view moves to the middle of the bleed, red overlay | **Flow 1.5 / 2.4.** A standard DICOM SEG from the PACS; OHIF shows it with no code change. |
| | "Xác nhận", then "Danh sách ↗" | AN is no longer red, "Bác sĩ đã xác nhận XH" | The decision is stored; the study leaves the priority group. |
| | `case dung`, open DUNG right away | Panel says "AI đang phân tích", then that the mask came late, with "Tải lại ca" | OHIF reads the series list once. The real extension must load new SEGs itself. |
| 4. The AI goes down | `ai-down` | Within 12 s, yellow banner "AI tạm ngừng" | The triage service watches the AI heartbeat. |
| | `case em` | EM is stored and readable, shown as "AI tạm ngừng" | An unflagged study never looks negative. |
| | `ai-up` | EM is processed and flagged | No study is lost while the AI is down. |

If something goes wrong:

- "Stack chưa chạy": run `bash demo/scenarios.sh reset` and wait for it to finish.
- Studies from a previous run are in the PACS: `reset`, or jump ahead with `tour 3`.
- The AI finishes before DUNG is opened: `INFERENCE_SECONDS=30 bash demo/scenarios.sh reset`.
- OHIF does not show the SEG series: click "Tải lại ca" in the AI panel, or F5.

The single commands still work (`order`, `scan`, `case`, `wait`, `ai-down`,
`ai-up`). `bash demo/scenarios.sh all` runs cases an, bich, cuong and the AI
outage unattended.

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
