/* Scenario 1 sequence diagrams (rendered by sequence.js).
   Participant colours follow the architecture lanes: blue clinical, violet AI inference,
   pink AI research, emerald data, amber boundary/backup, cyan cloud, slate operations. */
window.SEQ = window.SEQ || {};
window.SEQ.s1 = [
  {
    id: "s1-triage",
    tab: "A · Scan → AI triage → diagnosis",
    ui: true,
    title: "Scenario 1: scan to diagnosis with AI triage",
    summary: "From the order to the diagnosis, including what the radiologist sees in the viewer and the RIS worklist. Reading (red) and AI triage (violet) run <b>in parallel</b>: the radiologist never waits for the AI.",
    groups: {
      clin: { label: "Clinical · VLAN 10–20", color: "blue" },
      ai: { label: "AI inference · VLAN 30", color: "violet" },
      data: { label: "Data · VLAN 50 / 80", color: "emerald" }
    },
    participants: [
      { id: "rad", name: "Radiologist", sub: "reads + diagnoses", kind: "actor", color: "blue", group: "clin" },
      { id: "viewer", name: "OHIF viewer", sub: "web UI", kind: "ui", color: "blue", group: "clin" },
      { id: "kc", name: "Keycloak", sub: "SSO + MFA", color: "blue", group: "clin" },
      { id: "his", name: "HIS / RIS", sub: "orders · worklist UI", kind: "ui", color: "blue", group: "clin" },
      { id: "ct", name: "CT scanner", sub: "modality", color: "blue", group: "clin" },
      { id: "pacs", name: "PACS", sub: "dcm4chee · N+1", color: "blue", group: "clin" },
      { id: "gw", name: "Orthanc gateway", sub: "NVMe buffer", color: "violet", group: "ai" },
      { id: "ai", name: "AI inference", sub: "service · TBD", color: "violet", group: "ai" },
      { id: "s3", name: "SeaweedFS", sub: "PACS bucket", color: "emerald", group: "data" },
      { id: "pg", name: "PostgreSQL", sub: "index · AI results", color: "emerald", group: "data" }
    ],
    steps: [
      { t: "sep", label: "Before the scan" },
      { t: "msg", from: "his", to: "pacs", style: "flow", label: "HL7 ADT / ORM order", detail: "HIS/RIS sends the order and patient data to the PACS, which adds it to the modality worklist." },
      { t: "msg", from: "ct", to: "pacs", style: "flow", label: "C-FIND modality worklist", detail: "The scanner queries the worklist, so patient and procedure details are not typed by hand." },
      { t: "msg", from: "pacs", to: "ct", style: "flow", ret: true, label: "patient + procedure" },

      { t: "sep", label: "Scan and store · clinical critical path" },
      { t: "loop", label: "each series, as it is acquired" },
      { t: "msg", from: "ct", to: "pacs", style: "crit", label: "C-STORE :11112, direct", detail: "The scanner sends straight to dcm4chee. No router in between: no extra hop and nothing extra that could fail. Any PACS node behind the load balancer can accept it." },
      { t: "msg", from: "pacs", to: "s3", style: "crit", label: "S3 PUT pixel data :9000" },
      { t: "msg", from: "pacs", to: "pg", style: "crit", label: "index instance :5432", detail: "The study becomes queryable as soon as its first instances are indexed." },
      { t: "msg", from: "pacs", to: "ct", style: "crit", ret: true, label: "C-STORE success" },
      { t: "end" },

      { t: "par", label: "radiologist reads" },
      { t: "msg", from: "rad", to: "viewer", style: "ui", label: "open the viewer" },
      { t: "msg", from: "viewer", to: "kc", style: "ui", label: "OIDC login (redirect)", detail: "Single sign-on with multi-factor authentication. The viewer never sees the password." },
      { t: "msg", from: "kc", to: "viewer", style: "ui", ret: true, label: "tokens after MFA" },
      { t: "msg", from: "viewer", to: "pacs", style: "crit", label: "QIDO-RS search studies" },
      { t: "msg", from: "pacs", to: "viewer", style: "crit", ret: true, label: "study list · AI status: not run yet" },
      { t: "msg", from: "rad", to: "viewer", style: "ui", label: "open the new study" },
      { t: "msg", from: "viewer", to: "pacs", style: "crit", label: "WADO-RS frames", detail: "The viewer opens the study while later series are still arriving, so reading starts before the transfer ends." },
      { t: "msg", from: "pacs", to: "viewer", style: "crit", ret: true, label: "images, while series still arrive" },
      { t: "else", label: "AI triage · best-effort" },
      { t: "msg", from: "pacs", to: "gw", style: "ai", label: "C-STORE export of selected series (push, retried)", detail: "An export rule in dcm4chee picks the series the AI needs (and prior studies of the same patient if required) and pushes them once. If Orthanc is down, dcm4chee queues the task and retries; the clinical flow is not affected." },
      { t: "msg", from: "gw", to: "gw", style: "ai", label: "buffer on NVMe; de-identified copy if picked for research" },
      { t: "msg", from: "gw", to: "ai", style: "ai", label: "series for inference", detail: "The AI reads from the gateway as often as it needs (preprocessing, retries, re-runs) without loading the PACS." },
      { t: "msg", from: "ai", to: "ai", style: "ai", label: "validated model → mask, report, priority" },
      { t: "msg", from: "ai", to: "gw", style: "ai", label: "DICOM SEG + SR" },
      { t: "msg", from: "gw", to: "pacs", style: "ai", label: "C-STORE SEG + SR", detail: "Only the gateway talks to the PACS. The AI service holds no PACS credentials at all, not even for writing results." },
      { t: "msg", from: "ai", to: "his", style: "ai", label: "priority flag · HL7 ORU / FHIR" },
      { t: "msg", from: "ai", to: "pg", style: "flow", label: "result metadata (AI results DB)" },
      { t: "end" },

      { t: "sep", label: "What the radiologist sees" },
      { t: "alt", label: "AI result ready" },
      { t: "msg", from: "his", to: "rad", style: "ui", ret: true, label: "worklist re-ordered: suspected ICH first", detail: "The priority flag moves the study to the top of the RIS worklist." },
      { t: "msg", from: "viewer", to: "pacs", style: "ai", label: "WADO-RS SEG + SR" },
      { t: "msg", from: "pacs", to: "viewer", style: "ai", ret: true, label: "mask overlay" },
      { t: "msg", from: "viewer", to: "rad", style: "ui", ret: true, label: "mask shown · AI done, awaiting confirmation" },
      { t: "else", label: "AI down, failed or still running" },
      { t: "msg", from: "viewer", to: "rad", style: "ui", ret: true, label: "“no AI result” · read in normal order", detail: "The viewer always distinguishes three states: AI not run yet, AI failed or timed out (“no AI result”), and AI done awaiting confirmation. Scanning, reading and diagnosis never wait on the AI." },
      { t: "end" },
      { t: "msg", from: "rad", to: "viewer", style: "ui", label: "confirm or correct the mask, diagnose" },
      { t: "msg", from: "viewer", to: "pacs", style: "flow", label: "STOW-RS confirmed / corrected SEG", detail: "Reference choice: the confirmed or corrected mask is stored in the PACS with the study, so it is part of the clinical record." }
    ]
  },

  {
    id: "s1-annotation",
    tab: "B · Annotation → training → new model",
    ui: true,
    title: "Scenario 1: annotation and model development",
    summary: "How a clinician labels de-identified cases in the annotation UI, and how labels become a validated model. Not time-critical: it repeats over weeks and months.",
    groups: {
      res: { label: "AI research · VLAN 40", color: "pink" },
      clin: { label: "Clinical", color: "blue" },
      ai: { label: "AI inference", color: "violet" },
      data: { label: "Data", color: "emerald" }
    },
    participants: [
      { id: "ann", name: "Clinician", sub: "annotates · validates", kind: "actor", color: "pink", group: "res" },
      { id: "aui", name: "Annotation UI", sub: "tool · TBD", kind: "ui", color: "pink", group: "res" },
      { id: "pacs", name: "PACS", sub: "dcm4chee", color: "blue", group: "clin" },
      { id: "gw", name: "Orthanc gateway", sub: "de-id · DICOMweb", color: "violet", group: "ai" },
      { id: "s3", name: "SeaweedFS", sub: "research bucket", color: "emerald", group: "data" },
      { id: "trn", name: "Model training", sub: "GPU · TBD", color: "pink", group: "res" },
      { id: "reg", name: "Model registry", sub: "approved versions", color: "pink", group: "res" },
      { id: "inf", name: "AI inference", sub: "service · TBD", color: "violet", group: "ai" }
    ],
    steps: [
      { t: "sep", label: "Prepare de-identified cases" },
      { t: "msg", from: "pacs", to: "gw", style: "ai", label: "C-STORE export (the same single push as triage)", detail: "The PACS exports each series once; research is served from the gateway, so the PACS carries no extra load for it." },
      { t: "msg", from: "gw", to: "gw", style: "res", label: "de-identify selected cases (fail-closed)", detail: "Identifiers are removed from the DICOM tags. Instances that may carry burned-in text (localizers, Secondary Captures, Burned In Annotation) are rejected. If a study cannot be de-identified safely, nothing is written." },

      { t: "sep", label: "Annotate" },
      { t: "loop", label: "each case in the queue" },
      { t: "msg", from: "ann", to: "aui", style: "ui", label: "open next case" },
      { t: "msg", from: "aui", to: "gw", style: "res", label: "QIDO / WADO-RS de-identified study" },
      { t: "msg", from: "gw", to: "aui", style: "res", ret: true, label: "images, no patient identity" },
      { t: "msg", from: "aui", to: "reg", style: "res", label: "load current model" },
      { t: "msg", from: "reg", to: "aui", style: "res", ret: true, label: "latest model version" },
      { t: "msg", from: "aui", to: "aui", style: "res", label: "draft hemorrhage mask" },
      { t: "msg", from: "aui", to: "ann", style: "ui", ret: true, label: "scan + AI draft mask" },
      { t: "msg", from: "ann", to: "aui", style: "ui", label: "correct the draft, save", detail: "Clinicians correct the draft instead of drawing from scratch." },
      { t: "msg", from: "aui", to: "gw", style: "res", label: "STOW-RS DICOM SEG label" },
      { t: "msg", from: "gw", to: "s3", style: "res", label: "copy label to research bucket at once", detail: "So no label is lost if the gateway fails over." },
      { t: "end" },

      { t: "sep", label: "Train, validate, release" },
      { t: "msg", from: "gw", to: "s3", style: "res", label: "export frozen, versioned dataset", detail: "A versioned set of images and labels, so every model can be traced to the exact data it learned from." },
      { t: "msg", from: "trn", to: "s3", style: "res", label: "read dataset version" },
      { t: "msg", from: "trn", to: "trn", style: "res", label: "train + evaluate" },
      { t: "msg", from: "trn", to: "reg", style: "res", label: "publish candidate + metrics" },
      { t: "msg", from: "ann", to: "reg", style: "ui", label: "review candidate on held-out test set", detail: "Clinicians and the AI team review the candidate. Only an approved version is marked validated." },
      { t: "alt", label: "approved" },
      { t: "msg", from: "reg", to: "reg", style: "res", label: "mark version validated" },
      { t: "msg", from: "inf", to: "reg", style: "ai", label: "load validated version only", detail: "The registry is the only handoff between research and inference." },
      { t: "msg", from: "reg", to: "inf", style: "ai", ret: true, label: "model" },
      { t: "note", over: ["aui", "pacs"], text: "Annotation also picks up the new model for better drafts: the annotation loop closes." },
      { t: "else", label: "rejected" },
      { t: "msg", from: "reg", to: "reg", style: "res", label: "stays a candidate; inference keeps its current model" },
      { t: "end" }
    ]
  },

  {
    id: "s1-backup",
    tab: "C · Backup, old study, restore",
    ui: true,
    title: "Scenario 1: backup, prior-study retrieval and restore",
    summary: "The background backup to the cloud, what the radiologist sees when a study older than 90 days is opened, and a point-in-time database restore.",
    groups: {
      ops: { label: "Hospital IT", color: "slate" },
      clin: { label: "Clinical", color: "blue" },
      data: { label: "Data · VLAN 50 / 80", color: "emerald" },
      edge: { label: "Boundary", color: "amber" },
      cloud: { label: "Cloud · storage only", color: "cyan" }
    },
    participants: [
      { id: "ops", name: "IT operator", sub: "approves restores", kind: "actor", color: "slate", group: "ops" },
      { id: "rad", name: "Radiologist", sub: "reads", kind: "actor", color: "blue", group: "clin" },
      { id: "viewer", name: "OHIF viewer", sub: "web UI", kind: "ui", color: "blue", group: "clin" },
      { id: "pacs", name: "PACS", sub: "dcm4chee", color: "blue", group: "clin" },
      { id: "pg", name: "PostgreSQL", sub: "primary + standby", color: "emerald", group: "data" },
      { id: "s3", name: "SeaweedFS", sub: "PACS bucket", color: "emerald", group: "data" },
      { id: "bkp", name: "Backup gateway", sub: "pgBackRest · rclone", color: "amber", group: "data" },
      { id: "fw", name: "Egress firewall", sub: "443 out · IPsec", color: "amber", group: "edge" },
      { id: "cloud", name: "Cloud buckets", sub: "Object Lock · KMS", color: "cyan", group: "cloud" }
    ],
    steps: [
      { t: "sep", label: "Background · one-way backup" },
      { t: "msg", from: "pg", to: "pg", style: "flow", label: "streaming replication to standby", detail: "Covers server failure: Patroni switches to the standby within seconds. It does not protect against bad data." },
      { t: "msg", from: "pg", to: "bkp", style: "bak", label: "WAL stream + base backups (TLS :8432)", detail: "This is the only database backup, so it is monitored closely." },
      { t: "msg", from: "bkp", to: "s3", style: "bak", label: "rclone copy new studies", detail: "Copy, not sync: deleting something in the hospital never deletes the cloud copy." },
      { t: "msg", from: "bkp", to: "fw", style: "bak", label: "HTTPS 443 out" },
      { t: "msg", from: "fw", to: "cloud", style: "bak", label: "S3 PUT · DICOM + DB backups", detail: "Encrypted with hospital-held keys (KMS) and protected by Object Lock (WORM + versioning)." },
      { t: "msg", from: "cloud", to: "cloud", style: "bak", label: "lifecycle: Standard → IA (90 d) → Archive (1 y)" },

      { t: "sep", label: "Doctor opens a study older than 90 days" },
      { t: "msg", from: "rad", to: "viewer", style: "ui", label: "open prior study" },
      { t: "msg", from: "viewer", to: "pacs", style: "crit", label: "QIDO-RS" },
      { t: "msg", from: "pacs", to: "pg", style: "crit", label: "look up study location" },
      { t: "msg", from: "pg", to: "pacs", style: "crit", ret: true, label: "in cloud (tier)" },
      { t: "msg", from: "pacs", to: "viewer", style: "crit", ret: true, label: "listed · not online" },
      { t: "msg", from: "viewer", to: "rad", style: "ui", ret: true, label: "“retrieving from archive”", detail: "Minutes from Infrequent Access, hours from Archive. For scheduled follow-up visits, prior studies are fetched a day or two in advance so nobody waits." },
      { t: "msg", from: "pacs", to: "bkp", style: "rest", label: "retrieve request (restore account)", detail: "Data comes back only when needed, through a separate account." },
      { t: "msg", from: "bkp", to: "fw", style: "rest", label: "HTTPS 443 out" },
      { t: "msg", from: "fw", to: "cloud", style: "rest", label: "GET object" },
      { t: "alt", label: "Infrequent Access" },
      { t: "msg", from: "cloud", to: "bkp", style: "rest", ret: true, label: "object · minutes" },
      { t: "else", label: "Archive" },
      { t: "msg", from: "cloud", to: "cloud", style: "rest", label: "rehydrate · hours" },
      { t: "msg", from: "cloud", to: "bkp", style: "rest", ret: true, label: "object" },
      { t: "end" },
      { t: "msg", from: "bkp", to: "s3", style: "rest", label: "write back to PACS bucket" },
      { t: "msg", from: "viewer", to: "pacs", style: "crit", label: "WADO-RS (now online)" },
      { t: "msg", from: "pacs", to: "viewer", style: "crit", ret: true, label: "images" },

      { t: "sep", label: "Data corrupted or deleted by mistake" },
      { t: "note", over: ["pg", "bkp"], kind: "warn", text: "The standby cannot help here: it has already copied the mistake." },
      { t: "msg", from: "ops", to: "bkp", style: "rest", label: "approve point-in-time restore" },
      { t: "msg", from: "bkp", to: "cloud", style: "rest", label: "fetch base backup + WAL (via 443 out)" },
      { t: "msg", from: "cloud", to: "bkp", style: "rest", ret: true, label: "backup set" },
      { t: "msg", from: "bkp", to: "pg", style: "rest", label: "restore to just before the problem", detail: "Takes hours, depending on database size and internet speed. Restore drills should measure the real recovery time." },
      { t: "msg", from: "bkp", to: "ops", style: "rest", ret: true, label: "restore complete" }
    ]
  }
];
