# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Job runner: one job at a time (GPU). State lives in job.json; live progress in memory."""
import json, os, threading, time, traceback, uuid
from concurrent.futures import ThreadPoolExecutor
from .config import JOBS
from . import analyze, render, extras, settings, llm, projects
from .progress import Tracker, Cancelled

_pool = ThreadPoolExecutor(max_workers=1)
_lock = threading.RLock()
PROG = {}   # job id -> Tracker
STAGES = ["Get video", "Transcribe", "Find moments", "Crop + captions", "Export"]
WEIGHTS = [20, 25, 15, 35, 5]   # share of the overall progress bar

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
    T = PROG.get(job["id"])
    snap = T.snapshot() if T else {"sp": 0, "note": "", "detail": "", "subs": [], "idle": 0, "clips": {}}
    st = job.get("stage", 0)
    if job["state"] == "done":
        overall = 100
    elif job["state"] in ("running", "queued"):
        overall = sum(WEIGHTS[:st]) + WEIGHTS[min(st, 4)] * snap["sp"]
    else:
        overall = sum(WEIGHTS[:st]) + WEIGHTS[min(st, 4)] * snap["sp"]
    return {**job, **{k: snap[k] for k in ("sp", "note", "detail", "subs", "idle")},
            "cprog": snap["clips"], "overall": round(overall, 1)}

def list_jobs():
    out = []
    for p in sorted(JOBS.glob("*/job.json"), key=lambda x: -x.stat().st_mtime):
        try: out.append(public(json.loads(p.read_text("utf-8"))))
        except Exception: pass
    return out

def create(source, opts=None, project="inbox"):
    opts = dict(opts or {})
    try:
        pr = projects.get(project)
    except Exception:
        project, pr = "inbox", projects.get("inbox")
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    (JOBS / jid).mkdir(parents=True)
    job = {"id": jid, "source": source, "title": source[-60:], "stage": 0, "state": "queued",
           "error": None, "log": [], "clips": [], "info": None,
           "project": project, "brief": pr.get("brief", {}),
           "settings": {**settings.get()["defaults"], **pr.get("defaults", {}), **opts}}
    save(job)
    PROG[jid] = Tracker(jid)
    _pool.submit(run_job, jid)
    return job

def mark_orphans():
    """Called at server start: a job left 'running' lost its worker when the server restarted."""
    for p in JOBS.glob("*/job.json"):
        try:
            j = json.loads(p.read_text("utf-8"))
            if j.get("state") in ("running", "queued"):
                j["state"] = "interrupted"; j["error"] = "Interrupted (the app was restarted). Press Resume."
                p.write_text(json.dumps(j, indent=1), "utf-8")
        except Exception:
            pass

def resume(jid):
    job = update(jid, lambda j: j.update(state="queued", error=None))
    PROG[jid] = Tracker(jid)
    _pool.submit(run_job, jid)
    return job

def refind(jid):
    """Pick moments again with the project's CURRENT brief. Reuses the download and transcript."""
    def f(j):
        try: j["brief"] = projects.get(j.get("project", "inbox")).get("brief", {})
        except Exception: pass
        try:
            for k, v in projects.get(j.get("project", "inbox")).get("defaults", {}).items():
                j["settings"][k] = v
        except Exception: pass
        j["clips"] = []; j.pop("webcam", None); j["state"] = "queued"; j["error"] = None
    update(jid, f)
    PROG[jid] = Tracker(jid)
    _pool.submit(run_job, jid)
    return load(jid)

def remove(jid):
    import shutil
    T = PROG.get(jid)
    if load(jid)["state"] in ("running", "queued"):
        raise RuntimeError("Cancel the job first")
    shutil.rmtree(JOBS / jid, ignore_errors=True); PROG.pop(jid, None)

def cancel(jid):
    T = PROG.get(jid)
    if T: T.cancel = True
    return bool(T)

def _logger(jid):
    def f(msg):
        def a(j): j["log"] = (j["log"] + [msg])[-40:]
        update(jid, a)
    return f

def run_job(jid):
    T = PROG.setdefault(jid, Tracker(jid))
    log = _logger(jid)
    def stage(i, names):
        update(jid, lambda j: j.update(stage=i, state="running")); T.plan(names)
    try:
        job = load(jid); st = job["settings"]; jd = JOBS / jid
        feat = settings.get()["features"]
        is_url = job["source"].startswith(("http://", "https://"))

        stage(0, ["Read video info", "Download video", "Download audio", "Merge"] if is_url else ["Read file", "Copy file"])
        video, title, info = analyze.ingest(job["source"], jd, log, T)
        update(jid, lambda j: j.update(title=title or j["title"], info=info, video=video.name))

        stage(1, ["Extract audio", "Load speech model", "Transcribe speech"])
        lg = st.get("language"); lg = lg if lg not in (None, "", "auto") else None
        tr = analyze.transcribe(video, jd, log, T, info["duration"], lg, st.get("whisper_model") or None)
        log(f"Transcript: {len(tr['words'])} words, language {tr['language']}")
        if tr['language'] in analyze.NON_LATIN and tr.get('model') in ('tiny', 'base', 'small'):
            log(f"Tip: the '{tr.get('model')}' speech model makes many mistakes in this language. Choose large-v3 in the project's Goals and settings, then Re-find.")

        yt = "youtube.com" in job["source"] or "youtu.be" in job["source"]
        use_chat = feat["chat_replay"] and yt
        use_ocr = st["mode"] == "gaming" and feat["ocr"]
        use_ai = feat["llm_rating"] and bool(llm.model_id("rating"))
        names = (["Loudness map"] + (["Chat replay"] if use_chat else []) + (["Read on-screen text"] if use_ocr else [])
                 + ["Score moments"] + (["AI rating"] if use_ai else []) + ["Pick best"])
        stage(2, names)
        extra = []
        T.set("Loudness map", None, "Measuring volume second by second")
        energy = analyze.audio_energy(video)
        T.done("Loudness map", f"{len(energy)} seconds measured")
        if use_chat:
            T.set("Chat replay", None, "Fetching chat")
            c = extras.chat_signal(job["source"], jd, info["duration"], log)
            if c is not None: extra.append(c)
            T.done("Chat replay")
        if use_ocr:
            o = extras.ocr_signal(video, info["duration"], log, energy=energy,
                                  prog=lambda f, d="": T.set("Read on-screen text", f, d))
            if o is not None: extra.append(o)
            T.done("Read on-screen text")
        clips = analyze.find_moments(video, tr, info["duration"], st["mode"], int(st["count"]),
                                     float(st["minlen"]), float(st["maxlen"]), log, extra, T, energy, job.get("brief"))
        update(jid, lambda j: j.update(clips=clips))

        stage(3, ["Find webcam"] + [f"Clip {c['id']}" for c in clips])
        render_all(jid, tr, log)

        stage(4, ["Write timeline"]); T.set("Write timeline", 0.3)
        try: extras.write_otio(load(jid), jd)
        except Exception as e: log(f"timeline export: {e}")
        T.finish_all()
        update(jid, lambda j: j.update(state="done"))
    except Cancelled:
        update(jid, lambda j: j.update(state="cancelled", error="Cancelled"))
    except Exception as e:
        update(jid, lambda j: j.update(state="error", error=f"{type(e).__name__}: {e}"))
        log(traceback.format_exc()[-600:])

def render_all(jid, tr, log, only=None):
    T = PROG.setdefault(jid, Tracker(jid))
    job = load(jid); st = job["settings"]; jd = JOBS / jid; video = jd / job["video"]
    if "webcam" not in job:   # find the webcam once per video, reuse for every clip
        if settings.get()["features"]["webcam_detect"]:
            try:
                box = render.detect_webcam(video, job["info"]["duration"], job["info"]["width"],
                                           job["info"]["height"],
                                           prog=lambda f: T.set("Find webcam", f, f"{int(f * 100)}% of 30 sample frames"))
            except Cancelled: raise
            except Exception as e:
                box = None; log(f"webcam detect: {e}")
        else:
            box = None
        update(jid, lambda x: x.update(webcam={"checked": True, "box": list(box) if box else None}))
        log("Webcam found" if box else "No webcam overlay found")
        job = load(jid)
    T.done("Find webcam", "found" if job["webcam"]["box"] else "none found")
    ids = [c["id"] for c in job["clips"] if c["approved"] and (only is None or c["id"] in only)]
    def setc(cid, **kw):
        def f(j): next(x for x in j["clips"] if x["id"] == cid).update(kw)
        update(jid, f)
    for n, cid in enumerate(ids):
        T.check()
        clip = dict(next(c for c in load(jid)["clips"] if c["id"] == cid))
        setc(cid, status="rendering")
        name = f"Clip {cid}"
        T.clips[cid] = {"f": 0.0, "note": "Starting"}
        def cprog(f, note=None, cid=cid, name=name):
            c = T.clips.setdefault(cid, {"f": 0.0, "note": ""})
            c["f"] = f
            if note: c["note"] = note
            T.set(name, f, f"{int(f * 100)}% · {c['note']}")
        out = jd / "clips" / f"clip{cid}.mp4"; out.parent.mkdir(exist_ok=True)
        try:
            used = render.render_clip(video, job["info"], tr, clip, out, st["layout"],
                                      clip.get("caption_style") or st["captions"],
                                      st["captions"] != "off", log, cprog, st["mode"], job.get("webcam"))
            extras.write_srt(out.with_suffix(".srt"), tr["words"], clip["start"], clip["end"])
            setc(cid, status="done", file=f"clips/{out.name}", layout_used=used,
                 rev=clip.get("rev", 0) + 1)
            T.done(name, f"layout: {used}")
        except Cancelled:
            setc(cid, status="pending"); raise
        except Exception as e:
            setc(cid, status="error"); log(f"clip {cid}: {e}"); T.done(name, "failed")
        T.clips.pop(cid, None)

def rerender(jid, ids):
    def go():
        T = PROG.setdefault(jid, Tracker(jid)); T.cancel = False
        try:
            update(jid, lambda j: j.update(state="running", stage=3))
            T.plan(["Find webcam"] + [f"Clip {i}" for i in ids])
            tr = analyze.load_transcript(JOBS / jid / "transcript.json")
            render_all(jid, tr, _logger(jid), only=set(ids))
            try: extras.write_otio(load(jid), JOBS / jid)
            except Exception: pass
            T.finish_all()
            update(jid, lambda j: j.update(state="done", stage=4))
        except Cancelled:
            update(jid, lambda j: j.update(state="cancelled", error="Cancelled"))
        except Exception as e:
            update(jid, lambda j: j.update(state="error", error=f"{type(e).__name__}: {e}"))
    _pool.submit(go)
