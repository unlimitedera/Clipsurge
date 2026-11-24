# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Job runner: one job at a time (GPU). State lives in job.json; live progress lives in memory."""
import json, os, threading, time, traceback, uuid
from concurrent.futures import ThreadPoolExecutor
from .config import JOBS
from . import analyze, render, extras

_pool = ThreadPoolExecutor(max_workers=1)
_lock = threading.RLock()
PROG = {}   # job id -> {"sp": 0-1 for current stage, "note": str, "clips": {clip id: 0-1}}
STAGES = ["Get video", "Transcribe", "Find moments", "Crop + captions", "Export"]

def _path(jid): return JOBS / jid / "job.json"

def save(job):
    with _lock:
        p = _path(job["id"]); tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, indent=1), "utf-8")
        os.replace(tmp, p)

def load(jid):
    with _lock:
        return json.loads(_path(jid).read_text("utf-8"))

def update(jid, fn):
    """Atomic read-modify-write so the worker and the web server never overwrite each other."""
    with _lock:
        job = load(jid); fn(job); save(job); return job

def public(job):
    p = PROG.get(job["id"], {})
    return {**job, "sp": p.get("sp", 0), "note": p.get("note", ""), "cprog": p.get("clips", {})}

def list_jobs():
    out = []
    for p in sorted(JOBS.glob("*/job.json"), key=lambda x: -x.stat().st_mtime):
        try: out.append(public(json.loads(p.read_text("utf-8"))))
        except Exception: pass
    return out

def create(source, settings):
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    (JOBS / jid).mkdir(parents=True)
    job = {"id": jid, "source": source, "title": source[-60:], "stage": 0, "state": "queued",
           "error": None, "log": [], "clips": [], "info": None,
           "settings": {"mode": "auto", "count": 5, "minlen": 20, "maxlen": 55,
                        "layout": "auto", "captions": "pop", **settings}}
    save(job)
    _pool.submit(run_job, jid)
    return job

def _logger(jid):
    def f(msg):
        def a(j): j["log"] = (j["log"] + [msg])[-40:]
        update(jid, a)
    return f

def run_job(jid):
    P = PROG[jid] = {"sp": 0, "note": "", "clips": {}}
    log = _logger(jid)
    def prog(f, note=None):
        P["sp"] = max(0.0, min(1.0, float(f)))
        if note is not None: P["note"] = note
    def stage(i, note=""):
        update(jid, lambda j: j.update(stage=i, state="running")); P["sp"] = 0; P["note"] = note
    try:
        job = load(jid); st = job["settings"]; jd = JOBS / jid
        stage(0, "Downloading")
        video, title, info = analyze.ingest(job["source"], jd, log, prog)
        update(jid, lambda j: j.update(title=title or j["title"], info=info, video=video.name))
        stage(1, "Transcribing speech")
        tr = analyze.transcribe(video, jd, log, prog, info["duration"])
        log(f"Transcript: {len(tr['words'])} words, language {tr['language']}")
        stage(2, "Scoring moments")
        extra = []
        c = extras.chat_signal(job["source"], jd, info["duration"], log)
        if c is not None: extra.append(c)
        prog(0.2)
        if st["mode"] == "gaming":
            P["note"] = "Reading on-screen text"
            o = extras.ocr_signal(video, info["duration"], log, prog=lambda f: prog(0.2 + 0.6 * f))
            if o is not None: extra.append(o)
        P["note"] = "Ranking moments"; prog(0.85)
        clips = analyze.find_moments(video, tr, info["duration"], st["mode"], int(st["count"]),
                                     float(st["minlen"]), float(st["maxlen"]), log, extra)
        update(jid, lambda j: j.update(clips=clips))
        stage(3, "Rendering clips")
        render_all(jid, tr, log)
        stage(4, "Exporting timeline"); prog(0.5)
        try: extras.write_otio(load(jid), jd)
        except Exception as e: log(f"timeline export: {e}")
        prog(1.0)
        update(jid, lambda j: j.update(state="done"))
    except Exception as e:
        update(jid, lambda j: j.update(state="error", error=f"{type(e).__name__}: {e}"))
        log(traceback.format_exc()[-600:])

def render_all(jid, tr, log, only=None):
    P = PROG.setdefault(jid, {"sp": 0, "note": "", "clips": {}})
    job = load(jid); st = job["settings"]; jd = JOBS / jid; video = jd / job["video"]
    ids = [c["id"] for c in job["clips"] if c["approved"] and (only is None or c["id"] in only)]
    if "webcam" not in job:   # find the webcam once per video, reuse for every clip
        P["note"] = "Looking for the webcam"; P["sp"] = 0
        try:
            box = render.detect_webcam(video, job["info"]["duration"], job["info"]["width"],
                                       job["info"]["height"], prog=lambda f: P.__setitem__("sp", f * 0.5))
        except Exception as e:
            box = None; log(f"webcam detect: {e}")
        update(jid, lambda x: x.update(webcam={"checked": True, "box": list(box) if box else None}))
        log("Webcam found" if box else "No webcam overlay found")
        job = load(jid)
    def setc(cid, **kw):
        def f(j): next(x for x in j["clips"] if x["id"] == cid).update(kw)
        update(jid, f)
    for n, cid in enumerate(ids):
        clip = dict(next(c for c in load(jid)["clips"] if c["id"] == cid))
        setc(cid, status="rendering")
        P["clips"][cid] = 0.0; P["note"] = f"Clip {n + 1} of {len(ids)}"; P["sp"] = n / len(ids)
        def cprog(f, n=n, cid=cid):
            P["clips"][cid] = f; P["sp"] = (n + f) / len(ids)
        out = jd / "clips" / f"clip{cid}.mp4"; out.parent.mkdir(exist_ok=True)
        try:
            used = render.render_clip(video, job["info"], tr, clip, out, st["layout"],
                                      clip.get("caption_style") or st["captions"],
                                      st["captions"] != "off", log, cprog, st["mode"], job.get("webcam"))
            extras.write_srt(out.with_suffix(".srt"), tr["words"], clip["start"], clip["end"])
            rev = clip.get("rev", 0) + 1
            setc(cid, status="done", file=f"clips/{out.name}", layout_used=used, rev=rev)
        except Exception as e:
            setc(cid, status="error"); log(f"clip {cid}: {e}")
        P["clips"].pop(cid, None)
    P["sp"] = 1.0

def rerender(jid, ids):
    def go():
        tr = json.loads((JOBS / jid / "transcript.json").read_text("utf-8"))
        render_all(jid, tr, _logger(jid), only=set(ids))
        try: extras.write_otio(load(jid), JOBS / jid)
        except Exception: pass
    _pool.submit(go)
