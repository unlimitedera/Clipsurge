# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Cliptastic web server: python -m cliptastic.server"""
import json, shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import jobs, llm, youtube
from .config import JOBS, WEB, DATA

app = FastAPI(title="Cliptastic")

@app.get("/api/status")
def status():
    return {"llm": llm.model_id(), "jobs": len(jobs.list_jobs())}

@app.get("/api/jobs")
def list_jobs():
    return jobs.list_jobs()

@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    try: return jobs.load(jid)
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
    job = jobs.load(jid)
    c = next((c for c in job["clips"] if c["id"] == cid), None)
    if not c: raise HTTPException(404)
    for k, v in e.model_dump(exclude_none=True).items(): c[k] = v
    if c["end"] - c["start"] < 3: raise HTTPException(400, "clip too short")
    jobs.save(job)
    if render and c["approved"]:
        c["status"] = "queued"; jobs.save(job); jobs.rerender(jid, [cid])
    return c

@app.post("/api/jobs/{jid}/render")
def render_all(jid: str):
    job = jobs.load(jid)
    ids = [c["id"] for c in job["clips"] if c["approved"] and c["status"] != "done"]
    for c in job["clips"]:
        if c["id"] in ids: c["status"] = "queued"
    jobs.save(job); jobs.rerender(jid, ids)
    return {"queued": ids}

@app.get("/api/youtube")
def yt_state(): return youtube.state()

@app.post("/api/youtube/connect")
def yt_connect():
    try: youtube.connect()
    except Exception as e: raise HTTPException(400, str(e))
    return youtube.state()

@app.post("/api/jobs/{jid}/clips/{cid}/upload")
def upload_clip(jid: str, cid: int, privacy: str = "private"):
    job = jobs.load(jid)
    c = next((c for c in job["clips"] if c["id"] == cid and c.get("file")), None)
    if not c: raise HTTPException(404, "render the clip first")
    try:
        c["youtube"] = youtube.upload(JOBS / jid / c["file"], c["title"],
                                      " ".join(c.get("tags", [])), c.get("tags"), privacy)
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    jobs.save(job); return c

@app.get("/files/{jid}/{path:path}")
def files(jid: str, path: str):
    p = (JOBS / jid / path).resolve()
    if JOBS.resolve() not in p.parents or not p.is_file(): raise HTTPException(404)
    return FileResponse(p)

app.mount("/", StaticFiles(directory=WEB, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8420)
