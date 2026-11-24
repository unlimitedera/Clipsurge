# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Job runner: one job at a time (GPU), state saved as job.json."""
import json, threading, time, traceback, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .config import JOBS
from . import analyze, render

_pool = ThreadPoolExecutor(max_workers=1)
_lock = threading.Lock()
STAGES = ["Get video", "Transcribe", "Find moments", "Smart crop + captions", "Export"]

def _path(jid): return JOBS / jid / "job.json"

def save(job):
    with _lock:
        _path(job["id"]).write_text(json.dumps(job, indent=1), "utf-8")

def load(jid):
    return json.loads(_path(jid).read_text("utf-8"))

def list_jobs():
    out = []
    for p in sorted(JOBS.glob("*/job.json"), key=lambda x: -x.stat().st_mtime):
        try: out.append(json.loads(p.read_text("utf-8")))
        except Exception: pass
    return out

def create(source, settings):
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    (JOBS / jid).mkdir(parents=True)
    job = {"id": jid, "source": source, "title": source[-60:], "stage": 0, "state": "queued",
           "progress": 0, "error": None, "log": [], "clips": [], "info": None,
           "settings": {"mode": "auto", "count": 5, "minlen": 20, "maxlen": 55,
                        "layout": "auto", "captions": "pop", **settings}}
    save(job)
    _pool.submit(run_job, jid)
    return job

def _log(job):
    def f(msg):
        job["log"].append(msg); job["log"] = job["log"][-40:]; save(job)
    return f

def _set(job, stage, progress=None):
    job["stage"] = stage
    if progress is not None: job["progress"] = progress
    save(job)

def run_job(jid):
    job = load(jid); log = _log(job); jd = JOBS / jid
    st = job["settings"]
    try:
        job["state"] = "running"; _set(job, 0, 5)
        video, title, info = analyze.ingest(job["source"], jd, log)
        job.update(title=title or job["title"], info=info, video=video.name)
        _set(job, 1, 20)
        tr = analyze.transcribe(video, jd, log)
        log(f"Transcript: {len(tr['words'])} words, language {tr['language']}")
        _set(job, 2, 45)
        job["clips"] = analyze.find_moments(video, tr, info["duration"], st["mode"],
                                            int(st["count"]), float(st["minlen"]),
                                            float(st["maxlen"]), log)
        save(job)
        _set(job, 3, 55)
        render_all(job, tr, log)
        job["state"] = "done"; _set(job, 4, 100)
    except Exception as e:
        job["state"] = "error"; job["error"] = f"{type(e).__name__}: {e}"
        log(traceback.format_exc()[-600:]); save(job)

def render_all(job, tr, log, only=None):
    jd = JOBS / job["id"]; st = job["settings"]; video = jd / job["video"]
    todo = [c for c in job["clips"] if c["approved"] and (only is None or c["id"] in only)]
    for n, c in enumerate(todo):
        c["status"] = "rendering"; save(job)
        out = jd / "clips" / f"clip{c['id']}.mp4"; out.parent.mkdir(exist_ok=True)
        try:
            c["layout_used"] = render.render_clip(video, job["info"], tr, c, out,
                st["layout"], c.get("caption_style") or st["captions"],
                st["captions"] != "off", log)
            c["file"] = f"clips/{out.name}"; c["status"] = "done"
        except Exception as e:
            c["status"] = "error"; log(f"clip {c['id']}: {e}")
        job["progress"] = 55 + int(45 * (n + 1) / max(1, len(todo))); save(job)

def rerender(jid, ids):
    def go():
        job = load(jid); jd = JOBS / jid
        tr = json.loads((jd / "transcript.json").read_text("utf-8"))
        render_all(job, tr, _log(job), only=set(ids))
    _pool.submit(go)
