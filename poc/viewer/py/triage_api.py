"""AI results service + triage worklist (fills the gap OHIF leaves).

OHIF only knows what QIDO-RS returns, and QIDO has no "suspected bleed" field
and no way to push an event. This service keeps the AI results (the "AI results
DB" of the architecture), merges them with the study list from the PACS, sorts
flagged studies first and pushes changes to browsers over Server-Sent Events.

Endpoints (all under /triage/ behind the proxy):
  GET  /api/studies              study list from QIDO-RS + AI state, flagged first
  GET  /api/studies/{uid}        one study, used by the in-viewer AI panel
  POST /api/studies/{uid}/review radiologist confirms or rejects the AI result
  GET  /api/mwl                  modality worklist items (Flow 1.4), via dcm4chee REST
  GET  /api/events               Server-Sent Events stream
  POST /api/results/{uid}        written by the AI worker
  POST /api/heartbeat            written by the AI worker
  GET  /api/results              study UIDs that already have a result (worker)
"""
import asyncio
import json
import os
import sqlite3
import time

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

DICOMWEB = os.environ.get("DICOMWEB_URL", "http://arc:8080/dcm4chee-arc/aets/DCM4CHEE/rs")
# dcm4chee serves the modality worklist from its own application entity.
MWL_RS = os.environ.get("MWL_URL", "http://arc:8080/dcm4chee-arc/aets/WORKLIST/rs")
DB = os.environ.get("TRIAGE_DB", "/data/triage.db")
DEADLINE_S = float(os.environ.get("AI_DEADLINE_SECONDS", "60"))
AI_STALE_S = 12.0

app = FastAPI(title="ICH triage PoC")
subscribers: set[asyncio.Queue] = set()
ai_seen = {"at": 0.0, "model_version": None, "boot": 0.0}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS ai_results (
        study_uid TEXT PRIMARY KEY, state TEXT, volume_ml REAL, model_version TEXT,
        preprocessing_hash TEXT, seg_series_uid TEXT, error TEXT,
        started_at REAL, updated_at REAL, review TEXT, reviewed_at REAL)""")
    return con


async def publish(event):
    for q in list(subscribers):
        q.put_nowait(event)


def ai_online():
    return time.time() - ai_seen["at"] < AI_STALE_S


def display_state(row):
    """The four states the architecture requires, never shown like a negative."""
    if row is None:
        return "NOT_RUN" if ai_online() else "AI_DOWN"
    if row["state"] == "RUNNING":
        if time.time() - row["started_at"] > DEADLINE_S:
            return "NO_RESULT"
        return "RUNNING" if ai_online() else "AI_DOWN"
    if row["state"] == "FAILED":
        return "NO_RESULT"
    return row["state"]   # POSITIVE, NEGATIVE, UNANALYZABLE


def tag(obj, t, default=""):
    v = obj.get(t, {}).get("Value")
    if not v:
        return default
    x = v[0]
    return x.get("Alphabetic", "") if isinstance(x, dict) else x


def study_view(s, row):
    return {
        "study_uid": tag(s, "0020000D"),
        "patient_name": tag(s, "00100010").replace("^", " "),
        "patient_id": tag(s, "00100020"),
        "accession": tag(s, "00080050"),
        "date": tag(s, "00080020"),
        "time": str(tag(s, "00080030"))[:6],
        "modalities": s.get("00080061", {}).get("Value", []),
        "instances": tag(s, "00201208", 0),
        "ai_state": display_state(row),
        "volume_ml": row["volume_ml"] if row else None,
        "model_version": row["model_version"] if row else None,
        "preprocessing_hash": row["preprocessing_hash"] if row else None,
        "seg_series_uid": row["seg_series_uid"] if row else None,
        "review": row["review"] if row else None,
    }


def priority_key(v):
    # AI may only raise priority: unreviewed positives first, everything else
    # keeps its normal (newest first) order.
    flagged = v["ai_state"] == "POSITIVE" and not v["review"]
    return (0 if flagged else 1, -int(f"{v['date'] or 0}{v['time'] or 0}"))


@app.get("/api/studies")
def list_studies():
    r = requests.get(f"{DICOMWEB}/studies", params={
        "ModalitiesInStudy": "CT", "includefield": "00080061,00201208,00080030", "limit": 100},
        headers={"Accept": "application/dicom+json"}, timeout=10)
    studies = r.json() if r.status_code == 200 else []
    with db() as con:
        rows = {x["study_uid"]: x for x in con.execute("SELECT * FROM ai_results")}
    views = [study_view(s, rows.get(tag(s, "0020000D"))) for s in studies]
    views.sort(key=priority_key)
    return {"ai_online": ai_online(), "model_version": ai_seen["model_version"],
            "deadline_s": DEADLINE_S, "studies": views}


@app.get("/api/studies/{uid}")
def get_study(uid: str):
    r = requests.get(f"{DICOMWEB}/studies", params={
        "StudyInstanceUID": uid, "includefield": "00080061,00201208,00080030"},
        headers={"Accept": "application/dicom+json"}, timeout=10)
    if r.status_code != 200 or not r.json():
        raise HTTPException(404, "study not in PACS")
    with db() as con:
        row = con.execute("SELECT * FROM ai_results WHERE study_uid=?", (uid,)).fetchone()
    return {"ai_online": ai_online(), **study_view(r.json()[0], row)}


@app.post("/api/studies/{uid}/review")
async def review(uid: str, body: dict):
    decision = body.get("decision")
    if decision not in ("CONFIRMED", "REJECTED"):
        raise HTTPException(400, "decision must be CONFIRMED or REJECTED")
    with db() as con:
        n = con.execute("UPDATE ai_results SET review=?, reviewed_at=? WHERE study_uid=?",
                        (decision, time.time(), uid)).rowcount
    if not n:
        raise HTTPException(404, "no AI result for this study")
    await publish({"type": "review", "study_uid": uid, "review": decision})
    return {"ok": True}


@app.get("/api/mwl")
def mwl():
    r = requests.get(f"{MWL_RS}/mwlitems", params={"limit": 50},
                     headers={"Accept": "application/dicom+json"}, timeout=10)
    items = r.json() if r.status_code == 200 else []
    out = []
    for it in items:
        sps = it.get("00400100", {}).get("Value", [{}])[0]
        out.append({
            "patient_name": tag(it, "00100010").replace("^", " "),
            "patient_id": tag(it, "00100020"),
            "accession": tag(it, "00080050"),
            "study_uid": tag(it, "0020000D"),
            "procedure": tag(it, "00321060") or tag(sps, "00400007"),
            "modality": tag(sps, "00080060"),
            "start": f"{tag(sps, '00400002')} {str(tag(sps, '00400003'))[:4]}",
            "status": tag(sps, "00400020"),
        })
    return {"items": out, "raw": items}


@app.get("/api/results")
def results():
    # A study left RUNNING by a worker that has since restarted, or past its
    # deadline, is not "done": the worker picks it up again.
    with db() as con:
        return [r["study_uid"] for r in con.execute(
            "SELECT study_uid FROM ai_results WHERE state != 'RUNNING' "
            "OR (? - started_at < ? AND started_at >= ?)",
            (time.time(), DEADLINE_S, ai_seen["boot"]))]


@app.post("/api/results/{uid}")
async def put_result(uid: str, body: dict):
    now = time.time()
    with db() as con:
        old = con.execute("SELECT started_at FROM ai_results WHERE study_uid=?", (uid,)).fetchone()
        con.execute("""INSERT OR REPLACE INTO ai_results (study_uid, state, volume_ml,
            model_version, preprocessing_hash, seg_series_uid, error, started_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""", (
            uid, body["state"], body.get("volume_ml"), body.get("model_version"),
            body.get("preprocessing_hash"), body.get("seg_series_uid"), body.get("error"),
            old["started_at"] if old and body["state"] != "RUNNING" else now, now))
    await publish({"type": "result", "study_uid": uid, "state": body["state"],
                   "volume_ml": body.get("volume_ml"), "seg_series_uid": body.get("seg_series_uid")})
    return {"ok": True}


@app.post("/api/heartbeat")
async def heartbeat(body: dict):
    was = ai_online()
    ai_seen.update(at=time.time(), model_version=body.get("model_version"),
                   boot=float(body.get("boot", ai_seen["boot"])))
    if not was:
        await publish({"type": "ai_status", "online": True})
    return {"ok": True}


@app.get("/api/events")
async def events(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)

    async def stream():
        online = ai_online()
        try:
            yield f"data: {json.dumps({'type': 'hello', 'ai_online': online})}\n\n"
            while not await request.is_disconnected():
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=3)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    now_online = ai_online()
                    if now_online != online:
                        online = now_online
                        yield f"data: {json.dumps({'type': 'ai_status', 'online': online})}\n\n"
                    else:
                        yield ": keep-alive\n\n"
        finally:
            subscribers.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True))
