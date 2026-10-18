/* Scenario 2 sequence diagrams (rendered by sequence.js).
   A box keeps its lane colour wherever it runs; the slate "Site 2" band shows where it runs. */
window.SEQ = window.SEQ || {};
window.SEQ.s2 = [
  {
    id: "s2-triage",
    tab: "A · Scan → gateway → site 2 → diagnosis",
    ui: true,
    title: "Scenario 2: AI triage through the gateway to GPUs at site 2",
    summary: "The clinical path is unchanged from scenario 1. The gateway de-identifies, prepares one encrypted tensor and forwards it over N8; if site 2 does not answer before the deadline, the radiologist sees “no AI result” and reads in normal order.",
    groups: {
      clin: { label: "Clinical · main site", color: "blue" },
      ai: { label: "AI inference · main site", color: "violet" },
      data: { label: "Data", color: "emerald" },
      site2: { label: "Site 2 · over N8 (mTLS)", color: "slate", site: true }
    },
    participants: [
      { id: "rad", name: "Radiologist", sub: "reads + diagnoses", kind: "actor", color: "blue", group: "clin" },
      { id: "viewer", name: "OHIF viewer", sub: "web UI", kind: "ui", color: "blue", group: "clin" },
      { id: "his", name: "HIS / RIS", sub: "orders · worklist UI", kind: "ui", color: "blue", group: "clin" },
      { id: "ct", name: "CT scanner", sub: "modality", color: "blue", group: "clin" },
      { id: "pacs", name: "PACS", sub: "dcm4chee · N+1", color: "blue", group: "clin" },
      { id: "gw", name: "AI gateway", sub: "Orthanc · de-id · tensor", color: "violet", group: "ai" },
      { id: "pg", name: "PostgreSQL", sub: "AI results", color: "emerald", group: "data" },
      { id: "inf", name: "GPU inference", sub: "service · TBD", color: "violet", group: "site2" }
    ],
    steps: [
      { t: "sep", label: "Clinical path · unchanged from scenario 1" },
      { t: "msg", from: "his", to: "pacs", style: "flow", label: "HL7 ORM order → worklist" },
      { t: "msg", from: "ct", to: "pacs", style: "crit", label: "C-STORE :11112, each series", detail: "Straight to dcm4chee, stored to SeaweedFS and indexed in PostgreSQL exactly as in scenario 1." },
      { t: "msg", from: "rad", to: "viewer", style: "ui", label: "log in (Keycloak SSO), open study" },
      { t: "msg", from: "viewer", to: "pacs", style: "crit", label: "QIDO / WADO-RS while series arrive" },
      { t: "msg", from: "pacs", to: "viewer", style: "crit", ret: true, label: "images · AI status: not run yet" },

      { t: "sep", label: "AI triage through the gateway" },
      { t: "msg", from: "pacs", to: "gw", style: "ai", label: "C-STORE export of selected series (push, retried)", detail: "Same export rule as scenario 1, including earlier studies of the same patient when the AI needs them." },
      { t: "msg", from: "gw", to: "gw", style: "ai", label: "de-identify (fail-closed)", detail: "Identity is removed from the tags; instances that may carry burned-in text are rejected." },
      { t: "alt", label: "cannot de-identify safely" },
      { t: "msg", from: "gw", to: "gw", style: "flow", label: "block the study: nothing leaves the site" },
      { t: "msg", from: "gw", to: "pg", style: "flow", label: "status: no AI result" },
      { t: "else", label: "de-identified" },
      { t: "msg", from: "gw", to: "gw", style: "ai", label: "crop + resample (as in training), encrypt → one tensor", detail: "One tensor per study needs a single round trip; fetching slices on demand over the link would multiply round trips by hundreds." },
      { t: "msg", from: "gw", to: "inf", style: "ai", label: "gRPC over mTLS · N8: encrypted tensor", detail: "Store and forward: the tensor stays on the gateway until site 2 confirms receipt. Deadline 120 s, or 90 s for emergency cases." },
      { t: "alt", label: "site 2 answers before the deadline" },
      { t: "msg", from: "inf", to: "inf", style: "ai", label: "run model · never sees patient identity" },
      { t: "msg", from: "inf", to: "gw", style: "ai", ret: true, label: "mask" },
      { t: "msg", from: "gw", to: "gw", style: "ai", label: "map mask back onto the original study" },
      { t: "msg", from: "gw", to: "pacs", style: "ai", label: "C-STORE SEG + SR" },
      { t: "msg", from: "gw", to: "his", style: "ai", label: "priority flag · HL7 ORU / FHIR" },
      { t: "msg", from: "gw", to: "pg", style: "flow", label: "result metadata" },
      { t: "else", label: "deadline passed · site 2 or N8 down" },
      { t: "msg", from: "gw", to: "gw", style: "flow", label: "circuit breaker: drop job, delete tensor", detail: "The job is not sent when the link returns, and no late result or alert ever arrives." },
      { t: "msg", from: "gw", to: "pg", style: "flow", label: "status: no AI result" },
      { t: "end" },
      { t: "end" },

      { t: "sep", label: "What the radiologist sees" },
      { t: "alt", label: "AI done" },
      { t: "msg", from: "his", to: "rad", style: "ui", ret: true, label: "worklist re-ordered: suspected ICH first" },
      { t: "msg", from: "viewer", to: "pacs", style: "ai", label: "WADO-RS SEG + SR" },
      { t: "msg", from: "pacs", to: "viewer", style: "ai", ret: true, label: "mask overlay" },
      { t: "msg", from: "viewer", to: "rad", style: "ui", ret: true, label: "mask shown · awaiting confirmation" },
      { t: "else", label: "no AI result" },
      { t: "msg", from: "viewer", to: "rad", style: "ui", ret: true, label: "“no AI result” · read in normal order", detail: "The viewer always distinguishes three states: AI not run yet, AI failed or timed out (“no AI result”), and AI done awaiting confirmation." },
      { t: "end" },
      { t: "msg", from: "rad", to: "viewer", style: "ui", label: "confirm or correct, diagnose" }
    ]
  },

  {
    id: "s2-annotation",
    tab: "B · Annotation here, training at site 2",
    ui: true,
    title: "Scenario 2: annotation at the main site, training at site 2",
    summary: "Annotation is unchanged and stays at the main site. Training, the registry and inference run at site 2 on de-identified data only; datasets go out and models come back over N8.",
    groups: {
      res: { label: "AI research · main site", color: "pink" },
      ai: { label: "AI inference", color: "violet" },
      data: { label: "Data", color: "emerald" },
      site2: { label: "Site 2 · over N8 (mTLS)", color: "slate", site: true }
    },
    participants: [
      { id: "ann", name: "Clinician", sub: "annotates · validates", kind: "actor", color: "pink", group: "res" },
      { id: "aui", name: "Annotation UI", sub: "tool · TBD", kind: "ui", color: "pink", group: "res" },
      { id: "gw", name: "AI gateway", sub: "Orthanc · DICOMweb", color: "violet", group: "ai" },
      { id: "s3", name: "SeaweedFS", sub: "research bucket", color: "emerald", group: "data" },
      { id: "trn", name: "Model training", sub: "site 2 GPUs", color: "pink", group: "site2" },
      { id: "reg", name: "Model registry", sub: "approved versions", color: "pink", group: "site2" },
      { id: "inf", name: "GPU inference", sub: "service · TBD", color: "violet", group: "site2" }
    ],
    steps: [
      { t: "sep", label: "Annotate at the main site" },
      { t: "msg", from: "gw", to: "gw", style: "res", label: "de-identify selected cases from the PACS export (fail-closed)" },
      { t: "loop", label: "each case in the queue" },
      { t: "msg", from: "ann", to: "aui", style: "ui", label: "open next case" },
      { t: "msg", from: "aui", to: "gw", style: "res", label: "QIDO / WADO-RS de-identified study" },
      { t: "msg", from: "gw", to: "aui", style: "res", ret: true, label: "images, no patient identity" },
      { t: "msg", from: "aui", to: "reg", style: "res", label: "current model (over N8)" },
      { t: "msg", from: "reg", to: "aui", style: "res", ret: true, label: "latest model version" },
      { t: "msg", from: "aui", to: "aui", style: "res", label: "draft hemorrhage mask" },
      { t: "msg", from: "aui", to: "ann", style: "ui", ret: true, label: "scan + AI draft mask" },
      { t: "msg", from: "ann", to: "aui", style: "ui", label: "correct the draft, save" },
      { t: "msg", from: "aui", to: "gw", style: "res", label: "STOW-RS DICOM SEG label" },
      { t: "msg", from: "gw", to: "s3", style: "res", label: "copy label to research bucket" },
      { t: "end" },

      { t: "sep", label: "Train and release at site 2" },
      { t: "msg", from: "gw", to: "s3", style: "res", label: "export frozen, versioned dataset" },
      { t: "msg", from: "s3", to: "trn", style: "res", label: "de-identified labeled dataset (N8 · mTLS)", detail: "Only de-identified data crosses N8. Site 2 has no route to the PACS, the archive database or the identity key table." },
      { t: "msg", from: "trn", to: "trn", style: "res", label: "train + evaluate" },
      { t: "msg", from: "trn", to: "reg", style: "res", label: "publish candidate + metrics" },
      { t: "msg", from: "ann", to: "reg", style: "ui", label: "review candidate on held-out test set (over N8)" },
      { t: "alt", label: "approved" },
      { t: "msg", from: "reg", to: "reg", style: "res", label: "mark version validated" },
      { t: "msg", from: "inf", to: "reg", style: "ai", label: "load validated version only" },
      { t: "msg", from: "reg", to: "inf", style: "ai", ret: true, label: "model" },
      { t: "msg", from: "reg", to: "aui", style: "res", label: "new model for better drafts (over N8)", detail: "Validated models come back over N8; the annotation loop closes." },
      { t: "else", label: "rejected" },
      { t: "msg", from: "reg", to: "reg", style: "res", label: "stays a candidate; inference keeps its current model" },
      { t: "end" }
    ]
  }
];
