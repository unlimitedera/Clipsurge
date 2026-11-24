# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Stages 1-3: get video, transcribe, find moments."""
import json, re, shutil, subprocess
from pathlib import Path
import numpy as np
from .config import FFMPEG, FFPROBE, WHISPER_MODEL
from . import llm, settings
from .progress import fmt_time

# ---------- 1. ingest ----------
def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json",
                          "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return {"duration": float(j["format"]["duration"]),
            "width": int(v["width"]), "height": int(v["height"])}

def ingest(src, jobdir, log, T=None):
    jobdir = Path(jobdir)
    title = None
    have = [p for p in jobdir.glob("source.*") if p.suffix not in (".part", ".json", ".ytdl", ".tmp")]
    if have and not list(jobdir.glob("*.part")):          # resume: download already finished
        try:
            info = probe(have[0])
            if T:
                for n in ("Read video info", "Download video", "Download audio", "Merge", "Read file", "Copy file"):
                    T.done(n, "already done")
            return have[0], None, info
        except Exception:
            pass
    for p in jobdir.glob("*.part"):                       # stale partial download: yt-dlp resumes it
        pass
    if re.match(r"^https?://", src):
        import yt_dlp
        from .progress import fmt_bytes, fmt_time
        h = int(settings.get()["video"].get("max_height", 1080))
        T and T.set("Read video info", None, "Contacting the site")
        log("Downloading with yt-dlp...")

        def hook(d):
            if not T: return
            T.check()
            kind = "Download video" if (d.get("info_dict") or {}).get("vcodec") not in (None, "none") else "Download audio"
            if d["status"] == "downloading":
                got = d.get("downloaded_bytes") or 0
                tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                sp = d.get("speed"); eta = d.get("eta")
                det = f"{fmt_bytes(got)} of {fmt_bytes(tot)}" if tot else fmt_bytes(got)
                if sp: det += f" · {fmt_bytes(sp)}/s"
                if eta: det += f" · {fmt_time(eta)} left"
                T.set(kind, (got / tot) if tot else None, det)
            elif d["status"] == "finished":
                T.done(kind, "done")

        def pp(d):
            if T and d.get("postprocessor") in ("Merger", "FFmpegMerger", "VideoConvertor"):
                (T.set if d["status"] == "started" else T.done)("Merge", *(([None, "Joining video and audio"]) if d["status"] == "started" else []))

        opts = {"outtmpl": str(jobdir / "source.%(ext)s"), "noplaylist": True,
                "format": f"bv*[height<={h}]+ba/b[height<={h}]/b",
                "merge_output_format": "mp4", "quiet": True, "no_warnings": True,
                "ffmpeg_location": str(Path(FFMPEG).parent),
                "progress_hooks": [hook], "postprocessor_hooks": [pp],
                "socket_timeout": 20, "retries": 10, "fragment_retries": 10,
                "http_chunk_size": 10 * 1024 * 1024,      # avoids YouTube throttling stalls
                "continuedl": True}
        node = shutil.which("node")
        if node:
            opts["js_runtimes"] = {"node": {"path": node}}
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(src, download=False)
            title = info.get("title")
            T and T.done("Read video info", title or "")
            y.process_ie_result(info, download=True)
        files = [p for p in jobdir.glob("source.*") if p.suffix not in (".part", ".json", ".ytdl")]
        if not files:
            raise RuntimeError("download produced no file")
        path = files[0]
        if T:
            for n in ("Download video", "Download audio", "Merge"):
                T.done(n)
    else:
        p = Path(src.strip('"'))
        if not p.exists():
            raise FileNotFoundError(src)
        T and T.set("Read file", 0.5, p.name)
        path = jobdir / ("source" + p.suffix)
        T and T.done("Read file")
        if p.resolve() != path.resolve():
            T and T.set("Copy file", None, "Copying to the project folder")
            shutil.copy2(p, path)
        T and T.done("Copy file")
        title = p.stem
    return path, title, probe(path)

# ---------- 2. transcribe ----------
NON_LATIN = {"ar", "fa", "ur", "he", "ps", "ku", "sd", "ug", "yi", "hi", "bn", "ta", "te", "th", "ru",
             "uk", "bg", "sr", "zh", "ja", "ko", "el", "ka", "hy"}
RTL_LANGS = {"ar", "fa", "ur", "he", "ps", "ku", "sd", "ug", "yi"}
_LAT = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]")

def clean_transcript(tr):
    """For non-Latin languages (Arabic, Hebrew, Russian...), remove stray English/Latin letters that
    speech models hallucinate. Word positions are kept (emptied, not deleted) so edits stay aligned."""
    if tr.get("language") not in NON_LATIN or not settings.get()["features"].get("native_only", True):
        return tr
    for w in tr["words"]:
        if _LAT.search(w["w"]):
            w["w"] = _LAT.sub("", w["w"]).strip()
        if w["w"] and not re.search(r"\w", w["w"]):
            w["w"] = ""
    for sg in tr["segments"]:
        if _LAT.search(sg["text"]):
            sg["text"] = re.sub(r"\s+", " ", _LAT.sub("", sg["text"])).strip()
    return tr

def load_transcript(path):
    return clean_transcript(json.loads(Path(path).read_text("utf-8")))

def extract_audio(video, wav, duration=None, T=None):
    p = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-progress", "pipe:1", "-nostats", "-i", str(video),
                          "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for line in p.stdout:
        if T and duration and line.startswith("out_time_us="):
            try:
                f = int(line.split("=")[1]) / 1e6 / duration
                T.set("Extract audio", f, f"{int(min(f, 1) * 100)}% of the soundtrack")
            except ValueError:
                pass
    p.wait()
    if p.returncode:
        raise RuntimeError("could not extract audio")

def _collect(it, T, duration):
    out = []
    for sg in it:
        out.append(sg)
        if T and duration:
            T.set("Transcribe speech", sg.end / duration,
                  f"{fmt_time(sg.end)} of {fmt_time(duration)} · {len(out)} phrases")
    return out

def transcribe(video, jobdir, log, T=None, duration=None, lang_req=None, model_req=None):
    jobdir = Path(jobdir)
    cache = jobdir / "transcript.json"
    cached = json.loads(cache.read_text("utf-8")) if cache.exists() else None
    if cached and ((model_req and cached.get("model") != model_req) or (lang_req and cached.get("lang_req") != lang_req)):
        cached = None                                  # user asked for a different model/language
    if cached:
        if T:
            for n in ("Extract audio", "Load speech model", "Transcribe speech"):
                T.done(n, "already done")
        return clean_transcript(cached)
    wav = jobdir / "audio.wav"
    extract_audio(video, wav, duration, T)
    T and T.done("Extract audio")
    import wave
    import numpy as np
    from faster_whisper import WhisperModel
    with wave.open(str(wav)) as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    ts = settings.get()["transcribe"]
    name = model_req or ts.get("model") or WHISPER_MODEL
    req = lang_req or ts.get("language", "auto")
    lang = None if req in ("auto", "", None) else req
    kw = dict(word_timestamps=True, vad_filter=True, language=lang)
    raw = None
    if ts.get("device", "auto") in ("auto", "cuda"):
        try:
            T and T.set("Load speech model", None, f"Loading {name} on GPU (first use downloads it)")
            model = WhisperModel(name, device="cuda", compute_type="float16")
            T and T.done("Load speech model", f"{name} on GPU")
            log(f"Whisper '{name}' on GPU")
            segs_iter, info = model.transcribe(audio, **kw)
            raw = _collect(segs_iter, T, duration)
        except Exception as e:
            log(f"GPU unavailable ({type(e).__name__}), using CPU")
    if raw is None:
        T and T.set("Load speech model", None, f"Loading {name} on CPU")
        model = WhisperModel(name, device="cpu", compute_type="int8")
        T and T.done("Load speech model", f"{name} on CPU")
        log(f"Whisper '{name}' on CPU")
        segs_iter, info = model.transcribe(audio, **kw)
        raw = _collect(segs_iter, T, duration)
    segs, words = [], []
    for s in raw:
        segs.append({"s": s.start, "e": s.end, "text": s.text.strip()})
        for w in (s.words or []):
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end})
    out = {"language": info.language, "segments": segs, "words": words, "model": name, "lang_req": req}
    cache.write_text(json.dumps(out), "utf-8")
    return clean_transcript(out)

# ---------- 3. find moments ----------
def audio_energy(video):
    """RMS loudness per second."""
    p = subprocess.run([FFMPEG, "-v", "error", "-i", str(video), "-vn", "-ac", "1",
                        "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768
    n = len(a) // 8000
    if n == 0:
        return np.zeros(1)
    return np.sqrt((a[: n * 8000].reshape(n, 8000) ** 2).mean(axis=1))

HYPE = re.compile(r"\b(no way|oh my god|omg|insane|crazy|unbelievable|what the|holy|wow|"
                  r"never|secret|nobody|everyone|biggest|worst|best|mistake|truth|"
                  r"shocking|incredible|wait|actually|honestly|literally|million|"
                  r"love|hate|hilarious|funny|laugh|scary|impossible)\b", re.I)
HOOK = re.compile(r"^(why|how|what|did you|have you|nobody|everyone|the (secret|truth|biggest)|"
                  r"here'?s|stop|never|you (won'?t|need|should)|imagine)", re.I)

MODES = {  # peak, mean, keywords, speech-rate, hook
    "auto":     (0.30, 0.15, 0.20, 0.20, 0.15),
    "gaming":   (0.50, 0.25, 0.10, 0.10, 0.05),
    "podcast":  (0.15, 0.10, 0.30, 0.25, 0.20),
    "tutorial": (0.10, 0.10, 0.25, 0.25, 0.30),
}

_W = re.compile(r"[a-z0-9']+")
_SKIP = set("the a an and or of to in on is it that this for with as at by be are was were i you he she we they my your when where who what moments moment clips clip parts part scenes scene any all find look show".split())

def _toks(t):
    return {w for w in _W.findall(t.lower()) if w not in _SKIP and len(w) > 2}

def _brief_match(text, brief):
    """Returns (best idea or '', 0..1 strength, avoided?). Plain word overlap: no AI needed."""
    words = _toks(text)
    best, bs = "", 0.0
    for idea in brief.get("ideas", []):
        t = _toks(idea)
        if t:
            sc = len(t & words) / len(t)
            if sc > bs: best, bs = idea, sc
    avoided = any(_toks(a) and len(_toks(a) & words) >= max(1, len(_toks(a)) // 2 + len(_toks(a)) % 2)
                  for a in brief.get("avoid", []))
    return (best if bs >= 0.34 else ""), bs, avoided

def _pct(x):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return np.ones(len(x))
    return x.argsort().argsort() / (len(x) - 1)

def find_moments(video, tr, duration, mode, count, minlen, maxlen, log, extra=None, T=None, energy=None, brief=None):
    if energy is None:
        T and T.set("Loudness map", None, "Measuring volume second by second")
        energy = audio_energy(video)
        T and T.done("Loudness map")
    T and T.set("Score moments", 0.1, "Building candidate clips")
    z = (energy - energy.mean()) / (energy.std() + 1e-6)
    for ex in (extra or []):   # chat spikes, on-screen text hits
        n = min(len(z), len(ex))
        z[:n] = z[:n] + ex[:n]
    segs = tr["segments"]
    if sum(len(s["text"].split()) for s in segs) < 20:   # no speech: fixed chunks
        segs = [{"s": t, "e": min(t + 4.0, duration), "text": ""}
                for t in np.arange(0, duration, 4.0)]
    cands = []
    for i, sg in enumerate(segs):
        s = sg["s"]
        j = i
        while j < len(segs) and segs[j]["e"] - s < minlen:
            j += 1
        if j >= len(segs):
            break
        while j > i and segs[j]["e"] - s > maxlen:
            j -= 1
        e = segs[j]["e"]
        if e - s < minlen * 0.7 or e - s > maxlen:
            continue
        text = " ".join(x["text"] for x in segs[i:j + 1]).strip()
        zz = z[int(s): int(e) + 1]
        if len(zz) == 0:
            continue
        cands.append({"s": max(0, s - 0.15), "e": min(duration, e + 0.35), "text": text,
                      "peak": float(zz.max()), "mean": float(zz.mean()),
                      "kw": min(1.0, len(HYPE.findall(text)) / 3),
                      "wps": len(text.split()) / (e - s),
                      "hook": 1.0 if HOOK.search(segs[i]["text"]) or "?" in segs[i]["text"] else 0.0})
    if not cands:
        raise RuntimeError("video too short or silent to find moments")
    w = MODES.get(mode, MODES["auto"])
    cols = [_pct([c[k] for c in cands]) for k in ("peak", "mean", "kw", "wps")]
    hooks = np.array([c["hook"] for c in cands])
    for n, c in enumerate(cands):
        c["heur"] = 100 * (w[0] * cols[0][n] + w[1] * cols[1][n] + w[2] * cols[2][n]
                           + w[3] * cols[3][n] + w[4] * hooks[n])
    brief = brief or {}
    has_brief = bool(brief.get("ideas") or brief.get("avoid"))
    if has_brief:
        for c in cands:
            idea, bs, avoided = _brief_match(c["text"], brief)
            c["idea"] = idea
            c["heur"] = min(100, c["heur"] + 35 * bs) - (45 if avoided else 0)
    cands.sort(key=lambda c: -c["heur"])
    keep = []
    for c in cands:  # non-max suppression
        if all(min(c["e"], k["e"]) - max(c["s"], k["s"]) < 0.2 * (c["e"] - c["s"]) for k in keep):
            keep.append(c)
        if len(keep) >= min(24, max(count * 3, count)):
            break
    T and T.done("Score moments", f"{len(cands)} candidates")
    if T and any(x["name"] == "AI rating" for x in T.subs): T.set("AI rating", None, "Waiting for the model")
    rated = _llm_rate(keep, mode, log, brief)
    if T and any(x["name"] == "AI rating" for x in T.subs): T.done("AI rating", "rated" if rated else "no reply")
    T and T.set("Pick best", 0.5, f"Choosing the top {count}")
    for n, c in enumerate(keep):
        r = rated.get(n)
        if r:
            w = 0.65 if has_brief else 0.5          # with a brief, the AI's judgment counts more
            c["score"] = round((1 - w) * c["heur"] + w * float(r.get("score", c["heur"])))
            if r.get("idea") and not c.get("idea"): c["idea"] = str(r["idea"])[:80]
            c["title"] = r.get("title") or _title(c)
            c["tags"] = r.get("hashtags") or []
        else:
            c["score"] = round(c["heur"])
            c["title"] = _title(c)
            c["tags"] = []
    keep.sort(key=lambda c: -c["score"])
    out = []
    for n, c in enumerate(keep[:count]):
        out.append({"id": n + 1, "start": round(c["s"], 2), "end": round(c["e"], 2),
                    "score": c["score"], "title": c["title"], "tags": c["tags"],
                    "text": c["text"][:400], "idea": c.get("idea", ""), "approved": True, "status": "pending"})
    T and T.done("Pick best", f"{len(out)} moments")
    return out

def _title(c):
    t = c["text"].strip()
    if not t:
        return "Highlight"
    first = re.split(r"(?<=[.!?])\s", t)[0]
    return (first[:70] + "...") if len(first) > 72 else first

def _llm_rate(cands, mode, log, brief=None):
    if not settings.get()["features"]["llm_rating"]:
        return {}
    if not llm.model_id("rating"):
        log("No AI model connected: using audio + speech scoring only")
        return {}
    p = llm.provider("rating")
    log(f"Rating moments with {p['name']}...")
    items = [{"id": i, "text": c["text"][:500]} for i, c in enumerate(cands)]
    wants = ""
    if brief and brief.get("ideas"):
        wants += "The creator wants moments like:\n- " + "\n- ".join(brief["ideas"]) + "\nScore moments that match these much higher and set \"idea\" to the matching line (else \"\").\n"
    if brief and brief.get("avoid"):
        wants += "Score moments about these very low:\n- " + "\n- ".join(brief["avoid"]) + "\n"
    res = llm.chat_json(
        "You pick viral short-video moments. For each candidate rate 0-100 how well it works "
        "as a standalone short (hook, emotion, surprise, clear payoff). Write titles and hashtags in the same "
        "language and script as the transcript (never mix in English letters unless the transcript does). " + wants + "Reply ONLY with a JSON "
        'array: [{"id":0,"score":0-100,"title":"max 8 words catchy title","hashtags":["#a","#b"],"idea":""}]',
        f"Video type: {mode}\nCandidates:\n{json.dumps(items)}", role="rating")
    if not isinstance(res, list):
        log("LLM reply unusable: heuristic scoring only")
        return {}
    return {int(r["id"]): r for r in res if isinstance(r, dict) and "id" in r}
