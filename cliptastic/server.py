# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Cliptastic web server: python -m cliptastic.server"""
import datetime, json, shutil, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import jobs, llm, youtube, extras
from .config import JOBS, WEB, DATA

app = FastAPI(title="Cliptastic")
threading.Thread(target=extras.sched_loop, daemon=True).start()

def _clip(job, cid):
    c = next((c for c in job["clips"] if c["id"] == cid), None)
    if not c: raise HTTPException(404)
    return c

@app.get("/api/status")
def status():
    return {"llm": llm.model_id(), "jobs": len(jobs.list_jobs())}

@app.get("/api/jobs")
def list_jobs():
    return [{k: j[k] for k in ("id", "title", "state")} for j in jobs.list_jobs()]

@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    try: return jobs.public(jobs.load(jid))
    except FileNotFoundError: raise HTTPException(404)

@app.post("/api/jobs")
async def new_job(url: str = Form(""), mode: str = Form("auto"), count: int = Form(5),
                  minlen: int = Form(20), maxlen: int = Form(55),
                  layout: str = Form("auto"), captions: str = Form("pop"),
                  file: UploadFile | None = File(None)):
    src = url.strip()
    if file is not None and file.filename:
        up = DATA / "uploads"; up.mkdir(exist_ok=True, parents=True)
        dst = up / Path(file.filename).name
        with open(dst, "wb") as f: shutil.copyfileobj(file.file, f)
        src = str(dst)
    if not src: raise HTTPException(400, "give a link or a file")
    return jobs.create(src, {"mode": mode, "count": count, "minlen": minlen,
                             "maxlen": maxlen, "layout": layout, "captions": captions})

class ClipEdit(BaseModel):
    start: float | None = None
    end: float | None = None
    title: str | None = None
    approved: bool | None = None
    caption_style: str | None = None

@app.post("/api/jobs/{jid}/clips/{cid}")
def edit_clip(jid: str, cid: int, e: ClipEdit, render: bool = False):
    data = e.model_dump(exclude_none=True)
    def f(j):
        c = _clip(j, cid); c.update(data)
        if c["end"] - c["start"] < 3: raise HTTPException(400, "clip too short")
        if render and c["approved"] and c["status"] not in ("queued", "rendering"):
            c["status"] = "queued"
    job = jobs.update(jid, f)
    if render and _clip(job, cid)["status"] == "queued": jobs.rerender(jid, [cid])
    return _clip(job, cid)

@app.post("/api/jobs/{jid}/render")
def render_all(jid: str):
    """Render only clips that never rendered or failed. Never touches finished or running ones."""
    ids = []
    def f(j):
        for c in j["clips"]:
            if c["approved"] and c["status"] in ("pending", "error"):
                c["status"] = "queued"; ids.append(c["id"])
    jobs.update(jid, f)
    if ids: jobs.rerender(jid, ids)
    return {"queued": ids}

class NewClip(BaseModel):
    start: float
    end: float
    title: str = "Custom clip"

@app.get("/api/jobs/{jid}/search")
def search(jid: str, q: str):
    job = jobs.load(jid)
    tr = json.loads((JOBS / jid / "transcript.json").read_text("utf-8"))
    st = job["settings"]
    return extras.search(tr, q, float(st["minlen"]), float(st["maxlen"]))

@app.post("/api/jobs/{jid}/clips")
def add_clip(jid: str, n: NewClip):
    cid = []
    def f(j):
        i = max([c["id"] for c in j["clips"]] + [0]) + 1; cid.append(i)
        j["clips"].append({"id": i, "start": n.start, "end": n.end, "score": 0, "title": n.title,
                           "tags": [], "text": "", "approved": True, "status": "queued"})
    jobs.update(jid, f); jobs.rerender(jid, cid); return {"id": cid[0]}

class Sched(BaseModel):
    when: str

@app.post("/api/jobs/{jid}/clips/{cid}/schedule")
def schedule(jid: str, cid: int, s: Sched):
    extras.sched_add(jid, cid, datetime.datetime.fromisoformat(s.when).timestamp())
    return extras.sched_list()

@app.get("/api/schedule")
def sched(): return extras.sched_list()

@app.get("/api/youtube")
def yt_state(): return youtube.state()

@app.post("/api/youtube/connect")
def yt_connect():
    try: youtube.connect()
    except Exception as e: raise HTTPException(400, str(e))
    return youtube.state()

@app.post("/api/jobs/{jid}/clips/{cid}/upload")
def upload_clip(jid: str, cid: int, privacy: str = "private"):
    c = _clip(jobs.load(jid), cid)
    if not c.get("file"): raise HTTPException(404, "render the clip first")
    try: url = youtube.upload(JOBS / jid / c["file"], c["title"], " ".join(c.get("tags", [])),
                              c.get("tags"), privacy)
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    jobs.update(jid, lambda j: _clip(j, cid).update(youtube=url))
    return {"youtube": url}

@app.post("/api/obs/start")
def obs_start():
    try: extras.obs_start()
    except Exception as e:
        raise HTTPException(400, f"OBS not reachable ({type(e).__name__}). Open OBS and enable "
                                 "Tools > WebSocket Server Settings.")
    return {"recording": True}

@app.post("/api/obs/stop")
def obs_stop(mode: str = "auto", count: int = 5):
    try: path = extras.obs_stop()
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    return jobs.create(path, {"mode": mode, "count": count})

@app.get("/files/{jid}/{path:path}")
def files(jid: str, path: str):
    p = (JOBS / jid / path).resolve()
    if JOBS.resolve() not in p.parents or not p.is_file(): raise HTTPException(404)
    return FileResponse(p)   # supports range requests, so seeking/playback is stable

app.mount("/", StaticFiles(directory=WEB, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8420)
