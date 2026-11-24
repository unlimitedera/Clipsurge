# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Cliptastic web server: python -m cliptastic.server"""
import datetime, json, shutil, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import jobs, llm, youtube, extras, settings, projects, fsbrowse, analyze
from .config import JOBS, WEB, DATA, ROOT

app = FastAPI(title="Cliptastic")
projects.ensure_inbox()
jobs.mark_orphans()
threading.Thread(target=extras.sched_loop, daemon=True).start()

def _clip(job, cid):
    c = next((c for c in job["clips"] if c["id"] == cid), None)
    if not c: raise HTTPException(404)
    return c

@app.get("/api/settings")
def get_settings():
    return {"settings": settings.public(), "presets": llm.PRESETS, "youtube": youtube.state(),
            "mcp": {
                "json": {"mcpServers": {"cliptastic": {
                    "command": str(ROOT / ".venv/Scripts/python.exe").replace("\\", "/"),
                    "args": ["-m", "cliptastic.mcp_server"],
                    "env": {"PYTHONPATH": str(ROOT).replace("\\", "/")}}}},
                "claude_code": f'claude mcp add cliptastic --env PYTHONPATH={str(ROOT).replace(chr(92), "/")} -- '
                               f'{str(ROOT / ".venv/Scripts/python.exe").replace(chr(92), "/")} -m cliptastic.mcp_server',
                "hermes": f'hermes mcp add cliptastic --command "{str(ROOT / ".venv/Scripts/python.exe").replace(chr(92), "/")}" '
                          f'--env PYTHONPATH={str(ROOT).replace(chr(92), "/")} --args -m cliptastic.mcp_server'}}


@app.post("/api/settings")
def set_settings(body: dict):
    settings.save(body); return get_settings()

@app.post("/api/ai/test")
def ai_test(p: dict):
    if p.get("api_key") == settings.MASK:
        old = next((x for x in settings.get()["ai"]["providers"] if x["id"] == p.get("id")), {})
        p["api_key"] = old.get("api_key", "")
    return llm.test(p)

@app.get("/api/status")
def status():
    p = llm.provider("rating")
    return {"llm": llm.model_id("rating"), "provider": p["name"] if p else None}

@app.get("/api/jobs")
def list_jobs():
    return [{k: j.get(k) for k in ("id", "title", "state", "overall", "project")} for j in jobs.list_jobs()]

# ---------- projects ----------
def _proj_view(pr, with_jobs=False):
    js = [j for j in jobs.list_jobs() if j.get("project") == pr["id"]]
    clips = sum(len(j["clips"]) for j in js)
    out = {**pr, "videos": len(js), "clips": clips,
           "running": sum(1 for j in js if j["state"] in ("running", "queued")),
           "last": max([0] + [float(__import__("time").mktime(__import__("time").strptime(j["id"][:15], "%Y%m%d-%H%M%S"))) for j in js]),
           "thumbs": [j["id"] for j in js if j.get("video")][:3]}
    if with_jobs:
        out["jobs"] = js
    return out

@app.get("/api/projects")
def list_projects():
    return [_proj_view(p) for p in projects.all_projects()]

class ProjectIn(BaseModel):
    name: str = ""
    description: str = ""
    brief: dict | None = None
    defaults: dict | None = None

@app.post("/api/projects")
def new_project(p: ProjectIn):
    return _proj_view(projects.create(p.name, p.description, p.brief, p.defaults))

@app.get("/api/projects/{pid}")
def get_project(pid: str):
    try: return _proj_view(projects.get(pid), True)
    except FileNotFoundError: raise HTTPException(404)

@app.post("/api/projects/{pid}")
def edit_project(pid: str, p: dict):
    try: return _proj_view(projects.update(pid, p), True)
    except FileNotFoundError: raise HTTPException(404)

@app.delete("/api/projects/{pid}")
def del_project(pid: str):
    if pid == "inbox": raise HTTPException(400, "The Inbox cannot be deleted")
    for j in jobs.list_jobs():
        if j.get("project") == pid:
            if j["state"] in ("running", "queued"): raise HTTPException(400, "Cancel running videos first")
            jobs.remove(j["id"])
    projects.delete(pid); return {"ok": True}

class AddVideos(BaseModel):
    sources: list[str]

@app.post("/api/projects/{pid}/videos")
def add_videos(pid: str, a: AddVideos):
    projects.get(pid)
    made = []
    for src in [x.strip() for x in a.sources if x.strip()]:
        made.append({"id": jobs.create(src, {}, pid)["id"], "source": src})
    return made

@app.post("/api/projects/{pid}/upload")
async def upload_videos(pid: str, files: list[UploadFile] = File(...)):
    projects.get(pid)
    up = DATA / "uploads"; up.mkdir(exist_ok=True, parents=True)
    made = []
    for f in files:
        dst = up / Path(f.filename).name
        with open(dst, "wb") as o: shutil.copyfileobj(f.file, o)
        made.append({"id": jobs.create(str(dst), {}, pid)["id"], "source": str(dst)})
    return made

@app.delete("/api/jobs/{jid}")
def delete_job(jid: str):
    try: jobs.remove(jid)
    except RuntimeError as e: raise HTTPException(400, str(e))
    return {"ok": True}

@app.post("/api/jobs/{jid}/refind")
def refind_job(jid: str):
    return jobs.public(jobs.refind(jid))

@app.get("/api/jobs/{jid}/energy")
def job_energy(jid: str):
    """Loudness per second (0-1), for the editor timeline. Cached."""
    f = JOBS / jid / "energy.json"
    if not f.exists():
        j = jobs.load(jid)
        e = analyze.audio_energy(JOBS / jid / j["video"])
        mx = float(e.max()) or 1.0
        f.write_text(json.dumps([round(float(x) / mx, 3) for x in e]), "utf-8")
    return json.loads(f.read_text("utf-8"))

@app.get("/api/jobs/{jid}/words")
def job_words(jid: str, start: float, end: float):
    tr = json.loads((JOBS / jid / "transcript.json").read_text("utf-8"))
    return [{"i": i, "w": w["w"], "s": round(w["s"], 2), "e": round(w["e"], 2)}
            for i, w in enumerate(tr["words"]) if w["e"] >= start - 0.3 and w["s"] <= end + 0.3]

@app.get("/api/jobs/{jid}/frame")
def job_frame(jid: str, t: float, w: int = 960):
    """One frame of the source video at time t (for the crop editor)."""
    import subprocess
    from .render import _ENV
    from .config import FFMPEG
    j = jobs.load(jid)
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", str(JOBS / jid / j["video"]),
                        "-frames:v", "1", "-vf", f"scale={min(1920, w)}:-2", "-q:v", "4", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                       capture_output=True, env=_ENV)
    if not r.stdout: raise HTTPException(404)
    from fastapi.responses import Response
    return Response(r.stdout, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})

@app.get("/api/jobs/{jid}/clips/{cid}/poster")
def clip_poster(jid: str, cid: int):
    import subprocess
    from .render import _ENV
    from .config import FFMPEG
    c = _clip(jobs.load(jid), cid)
    if not c.get("file"): raise HTTPException(404)
    mp4 = JOBS / jid / c["file"]; jpg = mp4.with_suffix(".jpg")
    if not jpg.exists() or jpg.stat().st_mtime < mp4.stat().st_mtime:
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "1", "-i", str(mp4), "-frames:v", "1",
                        "-vf", "scale=270:-2", "-q:v", "5", str(jpg)], capture_output=True, env=_ENV)
    if not jpg.exists(): raise HTTPException(404)
    return FileResponse(jpg, headers={"Cache-Control": "max-age=3600"})

@app.get("/api/jobs/{jid}/thumb")
def job_thumb(jid: str):
    j = jobs.load(jid)
    if not j.get("video"): raise HTTPException(404)
    t = fsbrowse.thumb(str(JOBS / jid / j["video"]), at=min(30, max(1, (j.get("info") or {}).get("duration", 60) * 0.1)))
    if not t: raise HTTPException(404)
    return FileResponse(t, headers={"Cache-Control": "max-age=86400"})

# ---------- this PC's files ----------
@app.get("/api/fs/roots")
def fs_roots(): return fsbrowse.roots()

@app.get("/api/fs")
def fs_list(path: str, kind: str = "video"):
    try: return fsbrowse.listdir(path, kind)
    except (FileNotFoundError, NotADirectoryError): raise HTTPException(404, "Folder not found")

@app.get("/api/fs/thumb")
def fs_thumb(path: str):
    t = fsbrowse.thumb(path)
    if not t: raise HTTPException(404)
    return FileResponse(t, headers={"Cache-Control": "max-age=86400"})

@app.post("/api/jobs/{jid}/resume")
def resume_job(jid: str):
    return jobs.public(jobs.resume(jid))

@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    return {"cancelled": jobs.cancel(jid)}

@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    try: return jobs.public(jobs.load(jid))
    except FileNotFoundError: raise HTTPException(404)

@app.post("/api/jobs")
async def new_job(url: str = Form(""), mode: str = Form("auto"), count: int = Form(5),
                  minlen: int = Form(20), maxlen: int = Form(55),
                  layout: str = Form("auto"), captions: str = Form("pop"), project: str = Form("inbox"),
                  file: UploadFile | None = File(None)):
    src = url.strip()
    if file is not None and file.filename:
        up = DATA / "uploads"; up.mkdir(exist_ok=True, parents=True)
        dst = up / Path(file.filename).name
        with open(dst, "wb") as f: shutil.copyfileobj(file.file, f)
        src = str(dst)
    if not src: raise HTTPException(400, "give a link or a file")
    return jobs.create(src, {"mode": mode, "count": count, "minlen": minlen,
                             "maxlen": maxlen, "layout": layout, "captions": captions}, project)

class ClipEdit(BaseModel):
    edit: dict | None = None
    layout_note: str | None = None
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

@app.post("/api/jobs/{jid}/rerender-all")
def rerender_all(jid: str):
    ids = []
    def f(j):
        for c in j["clips"]:
            if c["approved"] and c["status"] not in ("queued", "rendering"):
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
def upload_clip(jid: str, cid: int, privacy: str = ""):
    privacy = privacy or settings.get()["youtube"]["privacy"]
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
def obs_stop(mode: str = "auto", count: int = 5, project: str = "inbox"):
    try: path = extras.obs_stop()
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    return jobs.create(path, {"mode": mode, "count": count}, project)

@app.get("/files/{jid}/{path:path}")
def files(jid: str, path: str):
    p = (JOBS / jid / path).resolve()
    if JOBS.resolve() not in p.parents or not p.is_file(): raise HTTPException(404)
    return FileResponse(p)   # supports range requests, so seeking/playback is stable

app.mount("/", StaticFiles(directory=WEB, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8420)
