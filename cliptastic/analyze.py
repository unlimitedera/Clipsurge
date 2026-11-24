# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Stages 1-3: get video, transcribe, find moments."""
import json, re, shutil, subprocess
from pathlib import Path
import numpy as np
from .config import FFMPEG, FFPROBE, WHISPER_MODEL
from . import llm

# ---------- 1. ingest ----------
def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json",
                          "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return {"duration": float(j["format"]["duration"]),
            "width": int(v["width"]), "height": int(v["height"])}

def ingest(src, jobdir, log, prog=None):
    jobdir = Path(jobdir)
    title = None
    if re.match(r"^https?://", src):
        import yt_dlp
        log("Downloading with yt-dlp...")
        opts = {"outtmpl": str(jobdir / "source.%(ext)s"), "noplaylist": True,
                "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
                "merge_output_format": "mp4", "quiet": True, "no_warnings": True,
                "ffmpeg_location": str(Path(FFMPEG).parent),
                "progress_hooks": [lambda d: prog and d.get("status") == "downloading" and prog(
                    d.get("downloaded_bytes", 0) / (d.get("total_bytes") or d.get("total_bytes_estimate") or 1))]}
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(src, download=True)
            title = info.get("title")
        files = [p for p in jobdir.glob("source.*") if p.suffix not in (".part", ".json")]
        if not files:
            raise RuntimeError("download produced no file")
        path = files[0]
    else:
        p = Path(src.strip('"'))
        if not p.exists():
            raise FileNotFoundError(src)
        path = jobdir / ("source" + p.suffix)
        if p.resolve() != path.resolve():
            shutil.copy2(p, path)
        title = p.stem
    return path, title, probe(path)

# ---------- 2. transcribe ----------
def extract_audio(video, wav):
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
                    "-ar", "16000", str(wav)], check=True)

def _collect(it, prog, duration):
    out = []
    for sg in it:
        out.append(sg)
        if prog and duration:
            prog(sg.end / duration)
    return out

def transcribe(video, jobdir, log, prog=None, duration=None):
    jobdir = Path(jobdir)
    cache = jobdir / "transcript.json"
    if cache.exists():
        return json.loads(cache.read_text("utf-8"))
    wav = jobdir / "audio.wav"
    extract_audio(video, wav)
    import wave
    import numpy as np
    from faster_whisper import WhisperModel
    with wave.open(str(wav)) as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    try:
        model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
        log(f"Whisper '{WHISPER_MODEL}' on GPU")
        segs_iter, info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
        raw = _collect(segs_iter, prog, duration)
    except Exception as e:
        log(f"GPU unavailable ({type(e).__name__}), using CPU")
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        segs_iter, info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
        raw = _collect(segs_iter, prog, duration)
    segs, words = [], []
    for s in raw:
        segs.append({"s": s.start, "e": s.end, "text": s.text.strip()})
        for w in (s.words or []):
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end})
    out = {"language": info.language, "segments": segs, "words": words}
    cache.write_text(json.dumps(out), "utf-8")
    return out

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

def _pct(x):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return np.ones(len(x))
    return x.argsort().argsort() / (len(x) - 1)

def find_moments(video, tr, duration, mode, count, minlen, maxlen, log, extra=None):
    energy = audio_energy(video)
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
    cands.sort(key=lambda c: -c["heur"])
    keep = []
    for c in cands:  # non-max suppression
        if all(min(c["e"], k["e"]) - max(c["s"], k["s"]) < 0.2 * (c["e"] - c["s"]) for k in keep):
            keep.append(c)
        if len(keep) >= min(24, max(count * 3, count)):
            break
    # optional LLM rating
    rated = _llm_rate(keep, mode, log)
    for n, c in enumerate(keep):
        r = rated.get(n)
        if r:
            c["score"] = round(0.5 * c["heur"] + 0.5 * float(r.get("score", c["heur"])))
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
                    "text": c["text"][:400], "approved": True, "status": "pending"})
    return out

def _title(c):
    t = c["text"].strip()
    if not t:
        return "Highlight"
    first = re.split(r"(?<=[.!?])\s", t)[0]
    return (first[:70] + "...") if len(first) > 72 else first

def _llm_rate(cands, mode, log):
    if not llm.model_id():
        log("No local LLM running: using heuristic scoring only")
        return {}
    log("Rating moments with local LLM...")
    items = [{"id": i, "text": c["text"][:500]} for i, c in enumerate(cands)]
    res = llm.chat_json(
        "You pick viral short-video moments. For each candidate rate 0-100 how well it works "
        "as a standalone short (hook, emotion, surprise, clear payoff). Reply ONLY with a JSON "
        'array: [{"id":0,"score":0-100,"title":"max 8 words catchy title","hashtags":["#a","#b"]}]',
        f"Video type: {mode}\nCandidates:\n{json.dumps(items)}")
    if not isinstance(res, list):
        log("LLM reply unusable: heuristic scoring only")
        return {}
    return {int(r["id"]): r for r in res if isinstance(r, dict) and "id" in r}
