# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Clipsurge web server: python -m clipsurge.server"""
import datetime, json, shutil, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import insights, updater, transfers, library, models, jobs, llm, youtube, extras, settings, projects, fsbrowse, analyze
from .config import JOBS, WEB, DATA, ROOT

app = FastAPI(title="Clipsurge")
projects.ensure_inbox()
jobs.mark_orphans()
library.sync_async()
threading.Thread(target=extras.sched_loop, daemon=True).start()

def _clip(job, cid):
    c = next((c for c in job["clips"] if c["id"] == cid), None)
    if not c: raise HTTPException(404)
    return c

@app.get("/api/settings")
def get_settings():
    return {"settings": settings.public(), "presets": llm.PRESETS, "youtube": youtube.state(),
            "mcp": {
                "json": {"mcpServers": {"clipsurge": {
                    "command": str(ROOT / ".venv/Scripts/python.exe").replace("\\", "/"),
                    "args": ["-m", "clipsurge.mcp_server"],
                    "env": {"PYTHONPATH": str(ROOT).replace("\\", "/")}}}},
                "claude_code": f'claude mcp add clipsurge --env PYTHONPATH={str(ROOT).replace(chr(92), "/")} -- '
                               f'{str(ROOT / ".venv/Scripts/python.exe").replace(chr(92), "/")} -m clipsurge.mcp_server',
                "hermes": f'hermes mcp add clipsurge --command "{str(ROOT / ".venv/Scripts/python.exe").replace(chr(92), "/")}" '
                          f'--env PYTHONPATH={str(ROOT).replace(chr(92), "/")} --args -m clipsurge.mcp_server'}}


@app.post("/api/settings")
def set_settings(body: dict):
    settings.save(body); return get_settings()

@app.post("/api/ai/test")
def ai_test(p: dict):
    if p.get("api_key") == settings.MASK:
        old = next((x for x in settings.get()["ai"]["providers"] if x["id"] == p.get("id")), {})
        p["api_key"] = old.get("api_key", "")
    return llm.test(p)

# ---------- model hub ----------
@app.get("/api/hw")
def api_hw(): return models.hardware()

@app.get("/api/models/speech")
def api_speech(): return models.speech_catalog()

class DlIn(BaseModel):
    kind: str
    name: str = ""
    repo: str = ""
    file: str = ""

@app.post("/api/models/download")
def api_download(d: DlIn):
    if d.kind == "speech": models.download_speech(d.name)
    elif d.kind == "gguf": models.download_gguf(d.repo, d.file)
    elif d.kind == "runtime": models.install_runtime()
    else: raise HTTPException(400, "unknown kind")
    return {"ok": True}

@app.post("/api/models/speech/delete")
def api_speech_del(d: DlIn):
    models.delete_speech(d.name); return {"ok": True}

@app.get("/api/models/downloads")
def api_dls(): return models.downloads()

@app.get("/api/models/hf/search")
def api_hf_search(q: str = ""):
    try: return models.hf_search(q)
    except Exception as e: raise HTTPException(502, f"Could not reach Hugging Face ({type(e).__name__})")

@app.get("/api/models/hf/files")
def api_hf_files(repo: str):
    try: return models.hf_files(repo)
    except Exception as e: raise HTTPException(502, f"Could not read that repository ({type(e).__name__})")

@app.get("/api/models/local")
def api_local():
    return {"models": models.local_models(), "status": models.local_status()}

@app.get("/api/models/plan")
def api_plan(path: str, ctx: int = 8192):
    try: return models.plan_llm(path, ctx)
    except Exception as e: raise HTTPException(400, str(e))

class RunIn(BaseModel):
    path: str
    ctx: int = 8192

@app.post("/api/models/local/run")
def api_run(r: RunIn):
    try: return models.run_local(r.path, r.ctx)
    except Exception as e: raise HTTPException(400, str(e))

@app.post("/api/models/local/stop")
def api_stop(): models.stop_local(); return {"ok": True}

@app.post("/api/models/local/delete")
def api_del_local(r: RunIn): models.delete_gguf(r.path); return {"ok": True}

@app.get("/api/status")
def status():
    p = llm.provider("rating")
    busy = sum(1 for j in jobs.list_jobs() if j["state"] in ("running", "queued"))
    return {"llm": llm.model_id("rating"), "provider": p["name"] if p else None, "busy": busy}

@app.get("/api/update")
def update_check(force: bool = False):
    return {**updater.check(force), "progress": updater.status()}

@app.get("/api/update/status")
def update_status():
    return updater.status()

@app.post("/api/update/apply")
def update_apply():
    busy = sum(1 for j in jobs.list_jobs() if j["state"] in ("running", "queued"))
    try: return updater.apply(busy)
    except RuntimeError as e: raise HTTPException(400, str(e))

@app.post("/api/restart")
def restart_service():
    """Starts a fresh server after this one exits. Jobs in progress become 'interrupted' (Resume)."""
    import os, subprocess, sys
    subprocess.Popen([sys.executable, "-m", "clipsurge.relaunch"], cwd=str(ROOT), close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x08000000 | 0x00000200)      # CREATE_NO_WINDOW | NEW_PROCESS_GROUP
    threading.Timer(0.7, lambda: os._exit(0)).start()
    return {"restarting": True}

_SZ = {}
def _dsize(p, ttl=20):
    """Folder size in bytes, cached briefly (walking big folders is slow)."""
    import os, time
    k = str(p); hit = _SZ.get(k)
    if hit and time.time() - hit[0] < ttl: return hit[1]
    tot = 0
    for root, _, fs in os.walk(p):
        for f in fs:
            try: tot += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    _SZ[k] = (time.time(), tot); return tot

def _fsz(p):
    try: return p.stat().st_size
    except OSError: return 0

def _parts(jid):
    """What is inside one video's folder, grouped for people: original, clips (each), transcript, other."""
    d = JOBS / jid
    src, clips, text, other = [], [], [], []
    for p in sorted(d.iterdir()) if d.is_dir() else []:
        n = p.name.lower()
        if p.is_dir() and n == "clips":
            for c in sorted(p.iterdir()):
                clips.append({"name": c.name, "size": _fsz(c) if c.is_file() else _dsize(c), "rel": f"clips/{c.name}"})
        elif n.startswith("source."): src.append({"name": p.name, "size": _fsz(p), "rel": p.name})
        elif n in ("transcript.json", "audio.wav", "energy.json") or n.endswith((".srt", ".otio", ".edl")):
            text.append({"name": p.name, "size": _fsz(p), "rel": p.name})
        else: other.append({"name": p.name, "size": _fsz(p) if p.is_file() else _dsize(p), "rel": p.name})
    g = lambda label, items, rel="": {"label": label, "size": sum(i["size"] for i in items), "items": items, "rel": rel}
    out = [g("Original video", src), g(f"Clips ({len([c for c in clips if c['name'].endswith('.mp4')])})", clips, "clips"),
           g("Transcript and audio", text), g("Other", other)]
    return [x for x in out if x["items"]]

@app.get("/api/storage")
def storage(pid: str | None = None):
    """Space Clipsurge uses. With pid: that project's videos, their folders and the total."""
    if pid is None:
        return {"total": _dsize(DATA), "path": str(DATA)}
    try: projects.get(pid)
    except FileNotFoundError: raise HTTPException(404)
    vids = [{"id": j["id"], "title": j.get("title"), "size": _dsize(JOBS / j["id"]), "path": str(JOBS / j["id"]),
             "parts": _parts(j["id"])} for j in jobs.list_jobs() if j.get("project") == pid]
    pr = projects.get(pid)
    pd = library.project_dir(pid)
    return {"name": pr["name"], "total": sum(v["size"] for v in vids), "path": str(pd or JOBS), "videos": vids}

class OpenIn(BaseModel):
    job: str | None = None
    project: str | None = None  # open that project's Explorer folder
    sub: str | None = None      # file or folder inside that video's folder

@app.post("/api/open-folder")
def open_folder(body: OpenIn):
    """Show a video's folder (or the videos folder) in Windows Explorer."""
    import os, subprocess
    if body.project and not body.job:
        library.sync()
        pd = library.project_dir(body.project)
        if pd is None: raise HTTPException(404, "Project not found")
        subprocess.Popen(["explorer", str(pd)]); return {"opened": str(pd)}
    p = ((JOBS / body.job / (body.sub or "")) if body.job else JOBS).resolve()
    if p != JOBS.resolve() and JOBS.resolve() not in p.parents: raise HTTPException(400, "Not a Clipsurge folder")
    if not p.exists(): raise HTTPException(404, "That does not exist any more")
    if p.is_file(): subprocess.Popen(["explorer", "/select,", str(p)])      # opens the folder with the file highlighted
    else: subprocess.Popen(["explorer", str(p)])
    return {"opened": str(p)}

@app.get("/api/memory")
def memory():
    """GPU and system memory in use, plus the models Clipsurge itself loaded (those it can unload)."""
    hw = models.hardware()
    g = hw["gpus"][0] if hw["gpus"] else None
    ls = models.local_status()
    busy = [j for j in jobs.list_jobs() if j["state"] in ("running", "queued")]
    return {"vram_used": g["used"] if g else None, "vram_total": g["total"] if g else None,
            "ram_used": hw["ram_total"] - hw["ram_free"], "ram_total": hw["ram_total"],
            "llm": {"loaded": ls["running"], "ready": ls["ready"], "name": ls["file"]},
            "busy": len(busy), "storage": _dsize(DATA, 60)}

@app.post("/api/models/unload")
def unload_models():
    """Unload what Clipsurge loaded (its managed local language model). Other apps' models are left alone."""
    was = models.local_status()["running"]
    models.stop_local()
    return {"unloaded": ["language model"] if was else []}

@app.post("/api/stop")
def stop_service():
    """Shut Clipsurge down (no relaunch). Videos in progress become 'interrupted' and can be resumed later."""
    import os
    try: models.stop_local()
    except Exception: pass
    threading.Timer(0.7, lambda: os._exit(0)).start()
    return {"stopping": True}

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
           "thumbs": [j["id"] for j in js if j.get("video")][:8]}
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
    try: out = _proj_view(projects.update(pid, p), True)
    except FileNotFoundError: raise HTTPException(404)
    library.sync_async(); return out

@app.delete("/api/projects/{pid}")
def del_project(pid: str):
    for j in jobs.list_jobs():
        if j.get("project") == pid:
            if j["state"] in ("running", "queued"): raise HTTPException(400, "Cancel running videos first")
            jobs.remove(j["id"])
    projects.delete(pid); library.sync_async(); return {"ok": True}

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
    tr = analyze.load_transcript(JOBS / jid / "transcript.json")
    return [{"i": i, "w": w["w"], "s": round(w["s"], 2), "e": round(w["e"], 2)}
            for i, w in enumerate(tr["words"]) if w["w"] and w["e"] >= start - 0.3 and w["s"] <= end + 0.3]

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
    try:
        return jobs.create(src, {"mode": mode, "count": count, "minlen": minlen,
                                 "maxlen": maxlen, "layout": layout, "captions": captions}, project)
    except ValueError as e: raise HTTPException(400, str(e))

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

@app.delete("/api/jobs/{jid}/clips/{cid}")
def delete_clip(jid: str, cid: int):
    if jobs.load(jid)["state"] in ("running", "queued"): raise HTTPException(400, "Wait for the video to finish or cancel it first")
    files = []
    def f(j):
        c = _clip(j, cid)
        if c["status"] in ("queued", "rendering"): raise HTTPException(400, "This clip is rendering. Try again when it finishes")
        if c.get("file"): files.append(c["file"])
        j["clips"] = [x for x in j["clips"] if x["id"] != cid]
    jobs.update(jid, f)
    d = JOBS / jid / "clips"
    for name in files + [f"clip{cid}.srt", f"clip{cid}.ass", f"clip{cid}.jpg"]:
        (JOBS / jid / name if "/" in name else d / name).unlink(missing_ok=True)
    try: extras.write_otio(jobs.load(jid), JOBS / jid)
    except Exception: pass
    return {"ok": True}

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

class WebcamIn(BaseModel):
    box: list[float] | None = None      # [x1, y1, x2, y2] fractions; None = no webcam
    auto: bool = False                  # forget the hand-drawn box and detect again next render

@app.post("/api/jobs/{jid}/webcam")
def set_webcam(jid: str, b: WebcamIn):
    if b.auto:
        jobs.update(jid, lambda j: j.pop("webcam", None)); return {"webcam": None}
    if b.box is not None and len(b.box) != 4: raise HTTPException(400, "box needs 4 numbers")
    try: return jobs.public(jobs.set_webcam(jid, b.box))["webcam"]
    except ValueError as e: raise HTTPException(400, str(e))

class RedoIn(BaseModel):
    step: int
    through_end: bool = False

@app.post("/api/jobs/{jid}/redo")
def redo_step(jid: str, body: RedoIn):
    if not 0 <= body.step <= 4: raise HTTPException(400, "unknown step")
    try: return jobs.public(jobs.redo(jid, body.step, body.through_end))
    except RuntimeError as e: raise HTTPException(400, str(e))

class OverrideIn(BaseModel):
    enabled: bool
    brief: dict | None = None
    settings: dict | None = None

@app.post("/api/jobs/{jid}/override")
def set_override(jid: str, body: OverrideIn):
    """Turn per-video goals/settings on (they beat the project) or off (follow the project again)."""
    return jobs.public(jobs.set_override(jid, body.enabled, body.brief, body.settings))

@app.post("/api/jobs/{jid}/narration")
def set_job_narration(jid: str, body: dict):
    """Per-video narration choices (on, title_caption, voice, vol). Missing keys fall back to Settings."""
    keep = {k: body[k] for k in ("on", "title_caption", "voice", "vol") if body.get(k) not in (None, "")}
    jobs.update(jid, lambda j: j.setdefault("settings", {}).__setitem__("narration", keep))
    return {"narration": keep}

class NewClip(BaseModel):
    start: float
    end: float
    title: str = "Custom clip"
    edit: dict | None = None      # optional crop / caption choices made while marking the clip

@app.get("/api/jobs/{jid}/search")
def search(jid: str, q: str):
    job = jobs.load(jid)
    tr = analyze.load_transcript(JOBS / jid / "transcript.json")
    st = job["settings"]
    return extras.search(tr, q, float(st["minlen"]), float(st["maxlen"]))

@app.post("/api/jobs/{jid}/clips")
def add_clip(jid: str, n: NewClip):
    cid = []
    def f(j):
        i = max([c["id"] for c in j["clips"]] + [0]) + 1; cid.append(i)
        j["clips"].append({"id": i, "start": n.start, "end": n.end, "score": 0, "title": n.title,
                           "tags": [], "text": "", "approved": True, "status": "queued",
                           **({"edit": n.edit} if n.edit else {})})
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

class YtClientIn(BaseModel):
    json_text: str | None = None
    client_id: str | None = None
    client_secret: str | None = None

@app.post("/api/youtube/client")
def yt_client(body: YtClientIn):
    try: youtube.save_client(body.json_text, body.client_id, body.client_secret)
    except ValueError as e: raise HTTPException(400, str(e))
    return youtube.state()

@app.post("/api/youtube/disconnect")
def yt_disconnect(forget_client: bool = False):
    youtube.disconnect(forget_client); return youtube.state()

@app.post("/api/youtube/connect")
def yt_connect():
    try: youtube.connect()
    except Exception as e: raise HTTPException(400, str(e))
    return youtube.state()

class UploadBody(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    description: str | None = None
    privacy: str | None = None

@app.get("/api/insights")
def insights_report(refresh: bool = False):
    insights.refresh(force=refresh)
    a = insights.analyse()
    a["youtube"] = youtube.state(); a["busy"] = insights._busy["stats"]; a["fetched"] = insights._load().get("fetched", 0)
    return a

@app.get("/api/insights/trending")
def insights_trending(topic: str, force: bool = False):
    return insights.trending(topic, force=force, wait=False)

@app.get("/api/jobs/{jid}/clips/{cid}/tags")
def clip_tags(jid: str, cid: int):
    _clip(jobs.load(jid), cid)
    return insights.suggest(jid, cid, wait=False)

@app.post("/api/jobs/{jid}/clips/{cid}/upload")
def upload_clip(jid: str, cid: int, privacy: str = "", body: UploadBody | None = None):
    body = body or UploadBody()
    privacy = body.privacy or privacy or settings.get()["youtube"]["privacy"]
    c = _clip(jobs.load(jid), cid)
    if not c.get("file"): raise HTTPException(404, "render the clip first")
    if any(u["jid"] == jid and u["cid"] == cid and u["state"] in ("queued", "uploading") for u in transfers.list_uploads()):
        raise HTTPException(400, "This clip is already uploading")
    tags = body.tags if body.tags is not None else c.get("tags")
    title = (body.title or c["title"] or "Clip").strip()
    desc = body.description
    if desc is None and body.tags is not None:
        hs = ["#" + t.lstrip("#").replace(" ", "") for t in body.tags[:3] if t.strip()]
        desc = title + ("\n\n" + " ".join(hs) if hs else "")
    j = jobs.load(jid); st = j.get("settings") or {}
    meta = {"dur": round(max(0, (c.get("end") or 0) - (c.get("start") or 0)), 1), "score": c.get("score"),
            "layout": c.get("layout_used"), "mode": st.get("mode"), "tags": [t.lstrip("#") for t in (tags or [])],
            "project": j.get("project"), "source": j.get("title"), "captions": st.get("captions"),
            "narration": bool(((c.get("edit") or {}).get("narration") or st.get("narration") or {}).get("enabled"))}
    return transfers.start_upload(jid, cid, title, c["file"], privacy, tags, desc, meta)

@app.get("/api/uploads")
def uploads_list(): return transfers.list_uploads()

@app.delete("/api/uploads")
def uploads_clear(uid: str | None = None):
    transfers.clear(uid); return {"ok": True}

class ClipDl(BaseModel):
    jid: str
    cid: int
    kind: str = "mp4"

@app.post("/api/downloads/clip")
def log_dl(b: ClipDl):
    try:
        c = _clip(jobs.load(b.jid), b.cid)
        f = JOBS / b.jid / (c.get("file") or "")
        transfers.log_clip_download(b.jid, b.cid, c.get("title"), b.kind, f.stat().st_size if f.is_file() else 0)
    except Exception: pass
    return {"ok": True}

@app.delete("/api/downloads")
def dl_clear(): transfers.clear_downloads(); return {"ok": True}

@app.get("/api/downloads")
def dl_list():
    vids = []
    for j in jobs.list_jobs():
        if not j.get("video"): continue
        f = JOBS / j["id"] / j["video"]
        vids.append({"id": j["id"], "title": j.get("title"), "project": j.get("project"), "source": j.get("source"),
                     "size": f.stat().st_size if f.is_file() else 0, "t": f.stat().st_mtime if f.is_file() else 0})
    return {"videos": sorted(vids, key=lambda v: -v["t"]), "clips": transfers.clips_downloaded()}

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
    try: return jobs.create(path, {"mode": mode, "count": count}, project)
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/files/{jid}/{path:path}")
def files(jid: str, path: str):
    p = (JOBS / jid / path).resolve()
    if JOBS.resolve() not in p.parents or not p.is_file(): raise HTTPException(404)
    return FileResponse(p)   # supports range requests, so seeking/playback is stable

app.mount("/", StaticFiles(directory=WEB, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("CLIPSURGE_PORT") or 8420))
