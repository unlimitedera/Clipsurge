# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Extra signals (chat replay, on-screen text), exports (SRT, OTIO), OBS, search, scheduler."""
import json, re, threading, time
from pathlib import Path
import numpy as np
from .config import DATA, FFMPEG

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

def ocr_signal(video, duration, log, step=2.0, prog=None):
    try:
        import cv2
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return None
    ocr = RapidOCR()
    cap = cv2.VideoCapture(str(video))
    sig = np.zeros(int(duration) + 2)
    hits, t = 0, 0.0
    while t < duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            break
        fr = cv2.resize(fr, (960, int(fr.shape[0] * 960 / fr.shape[1])))
        res, _ = ocr(fr)
        if res and any(OCR_HITS.search(r[1]) for r in res):
            sig[int(t)] += 1
            hits += 1
        t += step
        if prog: prog(t / duration)
    cap.release()
    log(f"On-screen text hits: {hits}")
    return np.convolve(sig, np.ones(7) / 7 * 3, "same") if hits else None

# ---------- exports ----------
def _srt_time(t):
    t = max(0, t)
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t % 1 * 1000):03d}"

def write_srt(path, words, start, end):
    ws = [w for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]
    out = []
    for n, g in enumerate(range(0, len(ws), 4), 1):
        grp = ws[g:g + 4]
        out.append(f"{n}\n{_srt_time(grp[0]['s'] - start)} --> {_srt_time(grp[-1]['e'] - start)}\n"
                   + " ".join(w["w"] for w in grp) + "\n")
    Path(path).write_text("\n".join(out), "utf-8")

def write_otio(job, jobdir):
    """Timeline of the picked moments over the source video. Opens in OpenCut-compatible
    and other editors that read OpenTimelineIO (and CMX EDL)."""
    import opentimelineio as otio
    fps = 30.0
    video = (Path(jobdir) / job["video"]).resolve()
    tl = otio.schema.Timeline(name=job["title"] or "Cliptastic")
    tr = otio.schema.Track(name="Cliptastic moments", kind=otio.schema.TrackKind.Video)
    for c in job["clips"]:
        if not c.get("approved"):
            continue
        ref = otio.schema.ExternalReference(target_url=video.as_uri())
        cl = otio.schema.Clip(name=c["title"] or f"clip {c['id']}", media_reference=ref,
            source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(c["start"] * fps, fps),
                                                 otio.opentime.RationalTime((c["end"] - c["start"]) * fps, fps)))
        cl.metadata["cliptastic"] = {"score": c["score"], "tags": c.get("tags", [])}
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
    cfg = DATA.parent / "secrets" / "obs.json"
    c = json.loads(cfg.read_text()) if cfg.exists() else {}
    return obs.ReqClient(host=c.get("host", "localhost"), port=c.get("port", 4455),
                         password=c.get("password", ""), timeout=5)

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
    ex = llm.chat_json("Reply ONLY with a JSON array of up to 10 synonyms or related words.", q)
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
                                             " ".join(c.get("tags", [])), c.get("tags"), "private")
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
