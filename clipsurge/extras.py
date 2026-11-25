# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Extra signals (chat replay, on-screen text), exports (SRT, OTIO), OBS, search, scheduler."""
import json, re, threading, time
from pathlib import Path
import numpy as np
from .config import DATA, FFMPEG
from . import settings

# ---------- signal: YouTube chat replay spikes (Stream-clipper idea) ----------
def chat_signal(url, jobdir, duration, log):
    if "youtube.com" not in url and "youtu.be" not in url:
        return None
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"skip_download": True, "writesubtitles": True, "quiet": True,
                               "no_warnings": True, "subtitleslangs": ["live_chat"],
                               "outtmpl": str(Path(jobdir) / "chat")}) as y:
            y.download([url])
        f = next(Path(jobdir).glob("chat*.live_chat.json"), None)
        if not f:
            return None
        sig = np.zeros(int(duration) + 2)
        for line in f.read_text("utf-8", "ignore").splitlines():
            m = re.search(r'"videoOffsetTimeMsec":"(-?\d+)"', line)
            if m and 0 <= int(m.group(1)) / 1000 < len(sig):
                sig[int(int(m.group(1)) / 1000)] += 1
        if sig.sum() < 20:
            return None
        k = np.ones(5) / 5
        sm = np.convolve(sig, k, "same")
        log(f"Chat replay: {int(sig.sum())} messages")
        return (sm - sm.mean()) / (sm.std() + 1e-6)
    except Exception as e:
        log(f"No chat replay ({type(e).__name__})")
        return None

# ---------- signal: on-screen text (OCR) for gaming moments ----------
OCR_HITS = re.compile(r"(kill|elimin|victory|winner|you win|ace|clutch|headshot|knock|"
                      r"defeat|wasted|level up|champion|double|triple|quad|penta|mvp|"
                      r"round won|match point|first blood|boss)", re.I)

def _grab(video, t, w=640):
    """One frame at time t via a fast keyframe seek (OpenCV seeks are ~2.7 s/frame on AV1)."""
    import subprocess
    from .render import _ENV
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "bmp", "-"],
                       capture_output=True, env=_ENV)
    return r.stdout

def ocr_signal(video, duration, log, energy=None, step=3.0, prog=None, workers=4):
    """Looks for on-screen words like KILL / VICTORY / ACE, but only during LOUD stretches
    (top 25% of the volume map), a few frames per stretch, several frames in parallel."""
    try:
        import cv2
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return None
    n = int(duration) + 2
    if energy is not None and len(energy) > 10:
        thr = np.percentile(energy, 75)
        secs = np.where(np.asarray(energy) >= thr)[0]
    else:
        secs = np.arange(0, n)
    times, last = [], -99.0
    for t in secs:                       # one sample every `step` seconds inside loud stretches
        if t - last >= step:
            times.append(float(t)); last = t
    if not times:
        return None
    log(f"Reading on-screen text in {len(times)} loud moments")
    engines = [RapidOCR() for _ in range(workers)]     # one engine per thread
    sig = np.zeros(n)
    hits = done = 0

    def work(i, t):
        buf = _grab(video, t)
        if not buf:
            return t, False
        fr = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
        res, _ = engines[i % workers](fr)
        return t, bool(res and any(OCR_HITS.search(r[1]) for r in res))

    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(work, i, t) for i, t in enumerate(times)]
        try:
            for f in as_completed(futs):
                t, hit = f.result()
                if hit:
                    sig[int(t)] += 1; hits += 1
                done += 1
                if prog: prog(done / len(times), f"{done} of {len(times)} frames · {hits} hits")
        except BaseException:
            for f in futs: f.cancel()
            raise
    log(f"On-screen text hits: {hits}")
    return np.convolve(sig, np.ones(7) / 7 * 3, "same") if hits else None

# ---------- exports ----------
def _srt_time(t):
    t = max(0, t)
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t % 1 * 1000):03d}"

def write_srt(path, words, start, end, censor_on=False):
    ws = [w for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]
    out = []
    for n, g in enumerate(range(0, len(ws), 4), 1):
        grp = ws[g:g + 4]
        out.append(f"{n}\n{_srt_time(grp[0]['s'] - start)} --> {_srt_time(grp[-1]['e'] - start)}\n"
                   + " ".join(__import__("clipsurge.censor", fromlist=["x"]).mask_word(w["w"]) if censor_on else w["w"] for w in grp) + "\n")
    Path(path).write_text("\n".join(out), "utf-8")

def write_otio(job, jobdir):
    """Timeline of the picked moments over the source video. Opens in OpenCut-compatible
    and other editors that read OpenTimelineIO (and CMX EDL)."""
    import opentimelineio as otio
    fps = 30.0
    video = (Path(jobdir) / job["video"]).resolve()
    tl = otio.schema.Timeline(name=job["title"] or "Clipsurge")
    tr = otio.schema.Track(name="Clipsurge moments", kind=otio.schema.TrackKind.Video)
    for c in job["clips"]:
        if not c.get("approved"):
            continue
        ref = otio.schema.ExternalReference(target_url=video.as_uri())
        cl = otio.schema.Clip(name=c["title"] or f"clip {c['id']}", media_reference=ref,
            source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(c["start"] * fps, fps),
                                                 otio.opentime.RationalTime((c["end"] - c["start"]) * fps, fps)))
        cl.metadata["clipsurge"] = {"score": c["score"], "tags": c.get("tags", [])}
        tr.append(cl)
    tl.tracks.append(tr)
    p = Path(jobdir) / "timeline.otio"
    otio.adapters.write_to_file(tl, str(p))
    try:
        otio.adapters.write_to_file(tl, str(Path(jobdir) / "timeline.edl"), adapter_name="cmx_3600")
    except Exception:
        pass
    return p

# ---------- OBS recording (obs-websocket v5) ----------
def _obs():
    import obsws_python as obs
    c = settings.get()["obs"]
    return obs.ReqClient(host=c["host"], port=int(c["port"]), password=c["password"], timeout=5)

def obs_start():
    _obs().start_record()

def obs_stop():
    """Stops recording and returns the saved file path."""
    r = _obs().stop_record()
    return r.output_path

# ---------- find moments by typing what you want ----------
STOP = set("the a an and or of to in on is it that this for with as at by be are was were i you he she we they my your".split())

def search(tr, q, minlen=20, maxlen=55, k=6):
    from . import llm
    terms = {w for w in re.findall(r"[a-z0-9']+", q.lower()) if w not in STOP}
    ex = llm.chat_json("Reply ONLY with a JSON array of up to 10 synonyms or related words.", q, role="search")
    if isinstance(ex, list):
        terms |= {str(w).lower() for w in ex}
    segs = tr["segments"]
    hits = []
    for i, s in enumerate(segs):
        toks = re.findall(r"[a-z0-9']+", s["text"].lower())
        sc = sum(1 for t in toks if t in terms)
        if sc:
            hits.append((sc / (len(toks) ** 0.3 + 1), i))
    out, used = [], []
    for sc, i in sorted(hits, reverse=True):
        a = b = i
        while segs[b]["e"] - segs[a]["s"] < minlen and (b + 1 < len(segs) or a > 0):
            if b + 1 < len(segs): b += 1
            elif a > 0: a -= 1
            if segs[b]["e"] - segs[a]["s"] > maxlen: break
        s, e = segs[a]["s"], segs[b]["e"]
        if any(min(e, u[1]) - max(s, u[0]) > 0 for u in used):
            continue
        used.append((s, e))
        out.append({"start": round(s, 2), "end": round(e, 2), "score": round(sc * 20),
                    "text": " ".join(x["text"] for x in segs[a:b + 1])[:300]})
        if len(out) >= k:
            break
    return out

# ---------- scheduler ----------
SCHED = DATA / "schedule.json"
_slock = threading.Lock()

def sched_list():
    return json.loads(SCHED.read_text("utf-8")) if SCHED.exists() else []

def sched_save(items):
    with _slock:
        SCHED.write_text(json.dumps(items, indent=1), "utf-8")

def sched_add(jid, cid, when_ts, platform="youtube"):
    items = sched_list()
    items.append({"job": jid, "clip": cid, "when": when_ts, "platform": platform, "state": "waiting"})
    sched_save(items)

def sched_loop():
    from . import jobs, youtube
    from .config import JOBS
    while True:
        try:
            items, changed = sched_list(), False
            for it in items:
                if it["state"] == "waiting" and it["when"] <= time.time():
                    it["state"] = "uploading"; sched_save(items)
                    try:
                        job = jobs.load(it["job"])
                        c = next(c for c in job["clips"] if c["id"] == it["clip"])
                        url = youtube.upload(JOBS / it["job"] / c["file"], c["title"],
                                             " ".join(c.get("tags", [])), c.get("tags"), settings.get()["youtube"]["privacy"])
                        def setu(j, url=url, cid=it["clip"]):
                            next(x for x in j["clips"] if x["id"] == cid)["youtube"] = url
                        jobs.update(it["job"], setu)
                        it["state"] = "done"; it["url"] = url
                    except Exception as e:
                        it["state"] = "error"; it["error"] = f"{type(e).__name__}: {e}"
                    changed = True
            if changed: sched_save(items)
        except Exception:
            pass
        time.sleep(30)
