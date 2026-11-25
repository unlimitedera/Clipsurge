# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Job runner: one job at a time (GPU). State lives in job.json; live progress in memory."""
import json, os, threading, time, traceback, uuid
from concurrent.futures import ThreadPoolExecutor
from .config import JOBS
from . import analyze, render, extras, settings, llm, projects, censor
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
        for k in range(40):             # Windows refuses the swap while another thread or a scanner has the file open
            try: os.replace(tmp, p); break
            except PermissionError:
                if k == 39: raise
                time.sleep(0.05)

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
        raise ValueError("Create a project first, then add videos to it.")
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    (JOBS / jid).mkdir(parents=True)
    job = {"id": jid, "source": source, "title": source[-60:], "stage": 0, "state": "queued",
           "error": None, "log": [], "clips": [], "info": None,
           "project": project, "brief": pr.get("brief", {}),
           "settings": {**settings.get()["defaults"], **pr.get("defaults", {}), **opts}}
    save(job)
    PROG[jid] = Tracker(jid)
    _pool.submit(run_job, jid)
    try: from . import library; library.sync_async()
    except Exception: pass
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
        sync_project(j)
        j["clips"] = []; _drop_auto_webcam(j); j["state"] = "queued"; j["error"] = None
    update(jid, f)
    PROG[jid] = Tracker(jid)
    _pool.submit(run_job, jid)
    return load(jid)

def _drop_auto_webcam(j):
    """Forget the detected webcam so it is found again, but never one the user drew by hand."""
    if not (j.get("webcam") or {}).get("manual"): j.pop("webcam", None)

def set_webcam(jid, box):
    """box = [x1, y1, x2, y2] as fractions of the frame, or None for 'there is no webcam'."""
    def f(j):
        if box is None: j["webcam"] = {"checked": True, "box": None, "manual": True}
        else:
            x1, y1, x2, y2 = [max(0.0, min(1.0, float(v))) for v in box]
            if x2 - x1 < 0.04 or y2 - y1 < 0.04: raise ValueError("That area is too small to be a webcam")
            j["webcam"] = {"checked": True, "box": [x1, y1, x2, y2], "manual": True}
    return update(jid, f)

def sync_project(j):
    """Make a video follow its project again (goals + defaults), unless it has its own settings."""
    if j.get("override"): return
    try:
        pr = projects.get(j.get("project", "inbox"))
        j["brief"] = pr.get("brief", {})
        keep = j["settings"].get("narration")
        j["settings"].update(pr.get("defaults", {}))
        if keep is not None: j["settings"]["narration"] = keep
    except Exception: pass

STEPS = ["download", "transcribe", "moments", "render", "export"]

def redo(jid, step, through_end=False):
    """Redo one pipeline step (0-4). Earlier steps are reused from disk. through_end also redoes later steps."""
    jd = JOBS / jid
    if load(jid)["state"] in ("running", "queued"):
        raise RuntimeError("Wait for the video to finish or cancel it first")
    def f(j):
        sync_project(j)
        if step == 2 or (through_end and step < 2):   # only a new moment search replaces the clips
            j["clips"] = []
        if step == 3 or (through_end and step < 3):
            _drop_auto_webcam(j)
        j["state"] = "queued"; j["error"] = None
    if step <= 0:
        for p in list(jd.glob("source.*")):
            try: p.unlink()
            except Exception: pass
    elif step == 1:
        for p in (jd / "transcript.json", jd / "audio.wav"):
            try: p.unlink()
            except Exception: pass
    update(jid, f)
    PROG[jid] = Tracker(jid)
    _pool.submit(run_job, jid, step, 4 if through_end else step)
    return load(jid)

def set_override(jid, enabled, brief=None, settings_in=None):
    def f(j):
        j["override"] = bool(enabled)
        if enabled:
            if brief is not None: j["brief"] = projects._brief(brief)
            if settings_in:
                j["settings"].update(projects._defaults(settings_in))
        else:       # back to project: drop this video's own values first so none of them linger
            for k in ("mode", "count", "minlen", "maxlen", "layout", "captions", "language", "whisper_model", "censor"):
                j["settings"].pop(k, None)
            j["settings"].update(settings.get()["defaults"])
            sync_project(j)
    return update(jid, f)

def remove(jid):
    import shutil
    T = PROG.get(jid)
    if load(jid)["state"] in ("running", "queued"):
        raise RuntimeError("Cancel the job first")
    shutil.rmtree(JOBS / jid, ignore_errors=True); PROG.pop(jid, None)
    try: from . import library; library.sync_async()
    except Exception: pass

def cancel(jid):
    T = PROG.get(jid)
    if T: T.cancel = True
    return bool(T)

def _logger(jid):
    def f(msg):
        def a(j): j["log"] = (j["log"] + [msg])[-40:]
        update(jid, a)
    return f

def run_job(jid, start=0, stop=4):
    T = PROG.setdefault(jid, Tracker(jid))
    log = _logger(jid)
    def stage(i, names):
        update(jid, lambda j: j.update(stage=i, state="running")); T.plan(names)
    try:
        job = load(jid); st = job["settings"]; jd = JOBS / jid
        feat = settings.get()["features"]
        is_url = job["source"].startswith(("http://", "https://"))
        def _finish():
            T.finish_all(); update(jid, lambda j: j.update(state="done"))

        if start <= 0:
            stage(0, ["Read video info", "Download video", "Download audio", "Merge"] if is_url else ["Read file", "Copy file"])
            video, title, info = analyze.ingest(job["source"], jd, log, T)
            update(jid, lambda j: j.update(title=title or j["title"], info=info, video=video.name))
            try: from . import library; library.sync_async()      # the folder is named after the real title
            except Exception: pass
        else:
            video = _ensure_source(jid, T, log); info = load(jid)["info"]
        if stop <= 0: return _finish()

        if start <= 1:
            stage(1, ["Extract audio", "Load speech model", "Transcribe speech"])
            lg = st.get("language"); lg = lg if lg not in (None, "", "auto") else None
            tr = analyze.transcribe(video, jd, log, T, info["duration"], lg, st.get("whisper_model") or None)
            log(f"Transcript: {len(tr['words'])} words, language {tr['language']}")
            if tr['language'] in analyze.NON_LATIN and tr.get('model') in ('tiny', 'base', 'small', 'distil-large-v3') and not st.get('whisper_model'):
                log(f"Detected {tr['language']}: redoing the transcript with the large-v3 speech model for accuracy")
                stage(1, ["Extract audio", "Load speech model", "Transcribe speech"])
                tr = analyze.transcribe(video, jd, log, T, info["duration"], lg, "large-v3")
        else:
            tr = analyze.load_transcript(jd / "transcript.json")
        if stop <= 1: return _finish()

        if start <= 2:
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
        if stop <= 2: return _finish()

        if start <= 3:
            stage(3, ["Find webcam"] + [f"Clip {c['id']}" for c in load(jid)["clips"]])
            render_all(jid, tr, log)
        if stop <= 3: return _finish()

        if start <= 4:
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

def _ensure_source(jid, T, log):
    """The source video, fetched again first if it was deleted from the Transfers tab to free disk space."""
    job = load(jid); jd = JOBS / jid
    if job.get("video") and (jd / job["video"]).exists(): return jd / job["video"]
    log("The source video was deleted to save space: getting it again")
    video, title, info = analyze.ingest(job["source"], jd, log, T)
    update(jid, lambda j: j.update(info=info, video=video.name))
    return video

def render_all(jid, tr, log, only=None):
    T = PROG.setdefault(jid, Tracker(jid))
    video = _ensure_source(jid, T, log)
    job = load(jid); st = job["settings"]; jd = JOBS / jid
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
                                      st["captions"] != "off", log, cprog, st["mode"], job.get("webcam"),
                                      st.get("narration"), st.get("censor"))
            extras.write_srt(out.with_suffix(".srt"), tr["words"], clip["start"], clip["end"],
                             censor.enabled((clip.get("edit") or {}).get("censor"), st.get("censor")))
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
