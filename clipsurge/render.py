# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Stages 4-7: smart crop, captions, audio polish, export."""
import os, shutil, subprocess, sys
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from .config import FFMPEG
from . import settings

W, H = 1080, 1920
_ENV = dict(os.environ, PATH=str(Path(FFMPEG).parent) + os.pathsep + os.environ.get("PATH", ""))

# ---------- face / webcam detection ----------
def _cam_from_unions(unions, min_frames=4):
    """Webcam = faces that keep showing up in the same screen region, anchored to a frame edge.
    The box is the pooled face extent plus head room and shoulders."""
    if len(unions) < min_frames:
        return None
    u = np.array(unions)
    rx1, ry1 = np.percentile(u[:, 0], 10), np.percentile(u[:, 1], 10)
    rx2, ry2 = np.percentile(u[:, 2], 90), np.percentile(u[:, 3], 90)
    pad = 0.04
    inside = np.mean((u[:, 0] >= rx1 - pad) & (u[:, 1] >= ry1 - pad) &
                     (u[:, 2] <= rx2 + pad) & (u[:, 3] <= ry2 + pad))
    rw, rh = rx2 - rx1, ry2 - ry1
    bx1, bx2 = max(0.0, rx1 - 0.04), min(1.0, rx2 + 0.05)
    by1, by2 = max(0.0, ry1 - 0.1), min(1.0, ry2 + 0.3 * rh)
    if by2 > 0.85: by2 = 1.0
    if bx1 < 0.08: bx1 = 0.0
    if bx2 > 0.92: bx2 = 1.0
    edge = bx1 <= 0.0 or bx2 >= 1.0 or by2 >= 1.0 or by1 <= 0.05
    if inside >= 0.7 and edge and rw < 0.5 and rh < 0.45:
        return (float(bx1), float(by1), float(bx2), float(by2))
    return None

def _detect_webcam_haar(video, duration, fw, fh, n=30, prog=None):
    """Sample frames across the WHOLE video once; a webcam overlay stays put, so pooling
    many frames finds it far more reliably than looking at one clip."""
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    sw = 640
    sh = int(round(fh * sw / fw / 2)) * 2
    unions = []
    for i in range(n):
        t = duration * (0.04 + 0.92 * i / max(1, n - 1))
        r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           capture_output=True, env=_ENV)
        if len(r.stdout) == sw * sh * 3:
            sm = np.frombuffer(r.stdout, np.uint8).reshape(sh, sw, 3)
            f = cas.detectMultiScale(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), 1.2, 5, minSize=(30, 30))
            if len(f):
                unions.append((min(q[0] for q in f) / sw, min(q[1] for q in f) / sh,
                               max(q[0] + q[2] for q in f) / sw, max(q[1] + q[3] for q in f) / sh))
        if prog: prog((i + 1) / n)
    return _cam_from_unions(unions, min_frames=max(5, n // 5))

def _yunet(w, h):
    from .speaker import MODEL
    if not MODEL.exists(): return None
    try: return cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), 0.6, 0.3, 20)
    except Exception: return None

def _peak(profile, lo, hi, step, floor):
    """Strongest persistent edge between index lo and hi (walking in direction step). None if nothing stands out."""
    lo, hi = max(0, lo), min(len(profile) - 1, hi)
    idx = range(lo, hi + 1) if step > 0 else range(hi, lo - 1, -1)
    best, bv = None, floor
    for i in idx:
        if profile[i] > bv: best, bv = i, profile[i]
    return best

def detect_webcam(video, duration, fw, fh, n=30, prog=None):
    """Find the streamer's webcam overlay. A face that sits in the same place in most sampled frames marks it;
    the real rectangle is then snapped to the crisp edges that stay put across all frames (game footage blurs
    away when averaged, the overlay border does not). Falls back to the older face-pooling method."""
    sw, sh = 960, int(round(fh * 960 / fw / 2)) * 2
    det = _yunet(sw, sh)
    if det is None:
        return _detect_webcam_haar(video, duration, fw, fh, n, prog)
    Ex = np.zeros((sh, sw), np.float32); Ey = Ex.copy(); faces = []; frames = 0; smalls = []
    for i in range(n):
        tt = duration * (0.04 + 0.92 * i / max(1, n - 1))
        r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{tt:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, env=_ENV)
        if len(r.stdout) == sw * sh * 3:
            im = np.frombuffer(r.stdout, np.uint8).reshape(sh, sw, 3)
            g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
            smalls.append(cv2.resize(g, (192, 108), interpolation=cv2.INTER_AREA))
            Ex += np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)); Ey += np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)); frames += 1
            _, f = det.detect(im)
            faces.append([(x[0] / sw, x[1] / sh, x[2] / sw, x[3] / sh) for x in (f if f is not None else [])])
        else:
            faces.append([])
        if prog: prog((i + 1) / n)
    if frames < 5: return _detect_webcam_haar(video, duration, fw, fh, n, None)
    Ex /= frames; Ey /= frames
    allf = [(k, b) for k, fl in enumerate(faces) for b in fl]
    # faces that stay put in many frames (a webcam may show several people)
    need = max(4, int(0.25 * frames)); cands = []
    for _, b in allf:
        cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
        cnt = sum(1 for fl in faces if any(abs(o[0] + o[2] / 2 - cx) < 0.05 and abs(o[1] + o[3] / 2 - cy) < 0.07
                                           and 0.6 < o[2] / max(b[2], 1e-6) < 1.6 for o in fl))
        if cnt >= need: cands.append((cnt, cx, cy, b[2]))
    if os.environ.get("CS_DEBUG"): print("cands", cands[:4])
    if not cands:
        return _detect_webcam_haar(video, duration, fw, fh, n, None)
    cands.sort(reverse=True); reps = []
    for cnt, cx, cy, w in cands:
        if all(abs(cx - r[1]) > 0.05 or abs(cy - r[2]) > 0.07 for r in reps): reps.append((cnt, cx, cy, w))
    X = lambda v: int(v * (sw - 1)); Y = lambda v: int(v * (sh - 1))

    def refine(top0):
        # other people in the same webcam: similar size, similar persistence, nearby (not tiny chat avatars)
        group = [r for r in reps if abs(r[1] - top0[1]) < 0.3 and abs(r[2] - top0[2]) < 0.2
                 and 0.5 < r[3] / max(top0[3], 1e-6) < 2.0 and r[0] >= 0.5 * top0[0]]
        boxes = []
        for _, cx, cy, _w in group:
            near = [o for fl in faces for o in fl if abs(o[0] + o[2] / 2 - cx) < 0.05 and abs(o[1] + o[3] / 2 - cy) < 0.07]
            boxes.append((float(np.median([o[0] for o in near])), float(np.median([o[1] for o in near])),
                          float(np.median([o[0] + o[2] for o in near])), float(np.median([o[1] + o[3] for o in near]))))
        fx1 = min(b[0] for b in boxes); fy1 = min(b[1] for b in boxes); fx2 = max(b[2] for b in boxes); fy2 = max(b[3] for b in boxes)
        fwid = float(np.median([b[2] - b[0] for b in boxes])); fhei = float(np.median([b[3] - b[1] for b in boxes]))   # one person
        rows = slice(Y(fy1), max(Y(fy2), Y(fy1) + 2)); px = Ex[rows].mean(0); mx = float(np.median(px)) + 1e-3
        R = _peak(px, X(fx2), X(min(1.0, fx2 + 3.5 * fwid)), +1, 6 * mx)
        L = _peak(px, X(max(0.0, fx1 - 3.5 * fwid)), X(fx1), -1, 6 * mx)
        left = L / (sw - 1) if L is not None else (0.0 if fx1 < 0.2 else max(0.0, fx1 - 0.5 * fwid))
        right = R / (sw - 1) if R is not None else (1.0 if fx2 > 0.8 else min(1.0, fx2 + 0.5 * fwid))
        cols = slice(X(left), max(X(right), X(left) + 2)); py = Ey[:, cols].mean(1); my = float(np.median(py)) + 1e-3
        T = _peak(py, Y(max(0.0, fy1 - 3 * fhei)), Y(fy1), -1, 6 * my)
        B = _peak(py, Y(fy2), Y(min(1.0, fy2 + 3 * fhei)), +1, 6 * my)
        top = T / (sh - 1) if T is not None else (0.0 if fy1 < 0.15 else max(0.0, fy1 - 0.4 * fhei))
        bot = B / (sh - 1) if B is not None else (1.0 if fy2 > 0.8 else min(1.0, fy2 + 0.6 * fhei))
        found = sum(v is not None for v in (L, R, T, B))
        return found, top0[0], (left, top, right, bot), (L, R, T, B)

    # try each persistent face group; the real webcam is the one whose rectangle snaps to crisp overlay edges
    tried = [refine(r) for r in reps[:5]]
    tried.sort(key=lambda x: (x[0], x[1]), reverse=True)
    found, _cnt, (left, top, right, bot), (L, R, T, B) = tried[0]
    corner = (left <= 0.01 or right >= 0.99) and (top <= 0.01 or bot >= 0.99)
    if (right - left) > 0.55 or (bot - top) > 0.55 or not (found >= 2 or corner):
        return _detect_webcam_haar(video, duration, fw, fh, n, None)
    # an overlay sits on top of CHANGING content. If everything outside the box barely changes between frames
    # taken minutes apart, this is just a camera video, not a webcam on a game or screen.
    st = np.std(np.stack(smalls), axis=0); m = np.ones(st.shape, bool)
    m[int(top * 107):int(bot * 107) + 1, int(left * 191):int(right * 191) + 1] = False
    outside = float(st[m].mean()) if m.any() else 0.0
    if os.environ.get("CS_DEBUG"): print("outside variation", round(outside, 1), "edges", L, R, T, B)
    if outside < 14:
        return None
    if left < 0.03: left = 0.0          # a thin border line next to the frame edge is part of the overlay
    if right > 0.97: right = 1.0
    if top < 0.03: top = 0.0
    if bot > 0.97: bot = 1.0
    ins = 0.003      # step in from the border line itself
    return (float(min(left + (ins if left > 0 else 0), 0.9)), float(top + (ins if top > 0 else 0)),
            float(right - (ins if right < 1 else 0)), float(bot - (ins if bot < 1 else 0)))

def track_faces(video, start, end, fw, fh, step=0.4, prog=None):
    """Returns times, x-centers (0-1, nan = none), face_ratio, webcam box or None.
    Webcam box = (x1, y1, x2, y2) as fractions: a static face group anchored to a frame edge.
    Frames come from ffmpeg (fast even for AV1), scaled to 640 wide."""
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    sw = 640
    sh = int(round(fh * sw / fw / 2)) * 2
    ts, xs, unions = [], [], []
    p = subprocess.Popen([FFMPEG, "-v", "error", "-ss", str(start), "-t", str(end - start),
                          "-i", str(video), "-vf", f"fps={1 / step},scale={sw}:{sh}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, env=_ENV)
    total = max(1, int((end - start) / step))
    n = 0
    while True:
        buf = p.stdout.read(sw * sh * 3)
        if len(buf) < sw * sh * 3:
            break
        sm = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
        f = cas.detectMultiScale(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), 1.2, 5, minSize=(30, 30))
        if len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])
            xs.append((x + w / 2) / sw)
            unions.append((min(r[0] for r in f) / sw, min(r[1] for r in f) / sh,
                           max(r[0] + r[2] for r in f) / sw, max(r[1] + r[3] for r in f) / sh))
        else:
            xs.append(np.nan)
        ts.append(n * step)
        n += 1
        if prog and n % 5 == 0:
            prog(min(1.0, n / total))
    p.stdout.close(); p.wait()
    xs = np.array(xs, dtype=float)
    ratio = float(np.mean(~np.isnan(xs))) if len(xs) else 0.0
    cam = _cam_from_unions(unions, min_frames=4)
    return np.array(ts), xs, ratio, cam

def smooth_path(ts, xs, fps, n_frames):
    ok = ~np.isnan(xs)
    if ok.sum() == 0:
        return np.full(n_frames, 0.5)
    path = np.interp(np.arange(n_frames) / fps, ts[ok], xs[ok])
    a, out = 0.08, np.empty(n_frames)
    out[0] = path[0]
    for i in range(1, n_frames):
        out[i] = out[i - 1] + a * (path[i] - out[i - 1])
    return out

# ---------- captions (ASS: opens in Aegisub too) ----------
def _ts(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"

STYLES = {  # font, size, text BGR, highlight BGR, outline
    "pop":   ("Arial", 84, "FFFFFF", "3DFFC6", 6),
    "clean": ("Arial", 70, "FFFFFF", "FFFFFF", 4),
    "fire":  ("Arial", 90, "FFFFFF", "3D8AFF", 7),
}
POS = {"bottom": (2, 420), "middle": (5, 0), "top": (8, 260)}

def _bgr(hexrgb):
    h = hexrgb.lstrip("#")
    return (h[4:6] + h[2:4] + h[0:2]).upper() if len(h) == 6 else None

def write_ass(path, words, start, end, style="pop", opts=None):
    opts = opts or {}
    font, size, col, hi, ol = STYLES.get(style, STYLES["pop"])
    base = settings.get()["video"]["caption_size"]
    size = int((opts.get("size") or size * base / 84))
    hi = _bgr(opts.get("hi") or "") or hi
    per = max(1, min(6, int(opts.get("per") or 3)))
    align, mv = POS.get(opts.get("pos") or "bottom", POS["bottom"])
    upper = opts.get("upper", True)
    edits = opts.get("edits") or {}
    tt = opts.get("title")          # {"text", "t0", "t1"}: separate on-screen title while it is narrated
    tmv, tal = (180, 8) if (opts.get("pos") or "bottom") != "top" else (760, 2)
    tstyle = (f"Style: Title,{font},{int(size * 0.9)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,"
              f"100,100,0,0,3,16,0,{tal},90,90,{tmv},1\n")
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n"
            "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,"
            "Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Default,{font},{size},&H00{col},&H00{col},&H00000000,&H80000000,-1,0,0,0,"
            f"100,100,0,0,1,{ol},2,{align},60,60,{mv},1\n{tstyle}\n[Events]\nFormat: Layer,Start,End,Style,"
            "Name,MarginL,MarginR,MarginV,Effect,Text\n")
    ws = [dict(w, i=i) for i, w in enumerate(words) if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]
    ws = [w for w in ws if str(edits.get(str(w["i"]), w["w"])).strip()]   # cleaned-out words
    for i in range(1, len(ws)):               # starts must increase
        ws[i]["s"] = max(ws[i]["s"], ws[i - 1]["s"] + 0.06)
    lines = []
    for g in range(0, len(ws), per):
        grp = ws[g:g + per]
        nxt = ws[g + per]["s"] if g + per < len(ws) else None
        for k, w in enumerate(grp):
            s0 = w["s"] - start
            if k + 1 < len(grp):
                e = grp[k + 1]["s"] - start
            else:
                e = w["e"] + 0.2
                if nxt is not None:
                    e = min(e, nxt)
                e -= start
            e = max(e, s0 + 0.05)
            parts = []
            for m, x in enumerate(grp):
                txt = str(edits.get(str(x["i"]), x["w"])).replace("{", "").replace("}", "")
                txt = txt.upper() if upper else txt
                parts.append(("{\\c&H%s&}%s{\\c&H%s&}" % (hi, txt, col)) if m == k else txt)
            line = " ".join(parts)
            if any("\u0590" <= ch <= "\u08ff" for ch in line):   # Arabic/Hebrew: force right-to-left
                line = "\u202b" + line + "\u202c"
            lines.append(f"Dialogue: 0,{_ts(s0)},{_ts(e)},Default,,0,0,0,,{{\\fscx92\\fscy92"
                         f"\\t(0,80,\\fscx100\\fscy100)}}{line}")
    if tt and tt.get("text"):
        line = str(tt["text"]).replace("{", "").replace("}", "")
        if any("\u0590" <= ch <= "\u08ff" for ch in line):
            line = "\u202b" + line + "\u202c"
        lines.append(f"Dialogue: 1,{_ts(tt['t0'])},{_ts(tt['t1'])},Title,,0,0,0,,{{\\fad(250,350)}}{line}")
    Path(path).write_text(head + "\n".join(lines) + "\n", "utf-8")
    return len(lines)

# ---------- encode ----------
@lru_cache(maxsize=1)
def _nvenc_ok():
    r = subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
                        "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, env=_ENV)
    return r.returncode == 0

def _enc():
    choice = settings.get()["video"]["encoder"]
    if choice == "nvenc" or (choice == "auto" and _nvenc_ok()):
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

def _normalize(raw, final):
    cfg = settings.get()
    if not cfg["features"]["loudness"]:
        shutil.copy2(raw, final)
        return True
    lufs = str(cfg["video"]["lufs"])
    """Loudness balance to -14 LUFS with ffmpeg-normalize; falls back to the raw file."""
    try:
        r = subprocess.run([sys.executable, "-m", "ffmpeg_normalize", str(raw), "-o", str(final), "-f", "-nt", "ebu",
                        "-t", lufs, "-tp", "-1.5", "-c:a", "aac", "-b:a", "160k"],
                           capture_output=True, text=True, env=_ENV)
        good = r.returncode == 0 and Path(final).exists()
    except Exception:
        good = False
    if not good:
        shutil.copy2(raw, final)
        return False
    return True

# ---------- per-clip edits: audio / video effects ----------
def _pitch(p):
    return f"aresample=48000,asetrate=48000*{p},aresample=48000,atempo={1 / p:.4f}"

VOICE = {
    "deep": _pitch(0.82), "high": _pitch(1.2), "chipmunk": _pitch(1.45), "monster": _pitch(0.7),
    "robot": "afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75",
    "radio": "highpass=f=300,lowpass=f=3400,acompressor=threshold=-18dB:ratio=6,volume=1.5",
    "telephone": "highpass=f=500,lowpass=f=2800,volume=1.3",
    "megaphone": "highpass=f=400,lowpass=f=4000,acompressor=threshold=-20dB:ratio=9,volume=1.6",
    "echo": "aecho=0.8:0.88:60:0.4",
    "stadium": "aecho=0.8:0.9:1000|1800:0.3|0.25",
}

def _post(src, dst, ed, dur, log):
    """Apply the clip's audio/video edits. Returns True if a new file was written."""
    au, vi = ed.get("audio") or {}, ed.get("video") or {}
    speed = float(vi.get("speed") or 1.0)
    out_dur = dur / speed
    a = []                                   # audio chain
    if speed != 1.0: a.append(f"atempo={speed}")
    if au.get("denoise"): a.append("afftdn=nr=14:nf=-28")
    if au.get("voice") in VOICE: a.append(VOICE[au["voice"]])
    if float(au.get("bass") or 0): a.append(f"bass=g={float(au['bass'])}")
    if float(au.get("treble") or 0): a.append(f"treble=g={float(au['treble'])}")
    if au.get("leveler"): a.append("acompressor=threshold=-21dB:ratio=3:attack=20:release=250:makeup=4")
    if float(au.get("gain") or 0): a.append(f"volume={float(au['gain'])}dB")
    if au.get("mute"): a.append("volume=0")
    fi, fo = float(vi.get("fade_in") or 0), float(vi.get("fade_out") or 0)
    if fi: a.append(f"afade=t=in:st=0:d={fi}")
    if fo: a.append(f"afade=t=out:st={max(0, out_dur - fo):.2f}:d={fo}")
    v = []                                   # video chain
    if speed != 1.0: v.append(f"setpts=PTS/{speed}")
    br, ct, sa = float(vi.get("brightness") or 0), float(vi.get("contrast") or 1), float(vi.get("saturation") or 1)
    if br or ct != 1 or sa != 1: v.append(f"eq=brightness={br}:contrast={ct}:saturation={sa}")
    if fi: v.append(f"fade=t=in:st=0:d={fi}")
    if fo: v.append(f"fade=t=out:st={max(0, out_dur - fo):.2f}:d={fo}")
    music = au.get("music") if au.get("music") and Path(str(au.get("music"))).is_file() else None
    if not (a or v or music):
        return False
    cmd = [FFMPEG, "-y", "-v", "error", "-i", str(src)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    voice = ",".join(a) if a else "anull"
    mv = float(au.get("music_vol") or 0.25)
    if music:
        duck = au.get("duck", True)
        if duck:
            fc = (f"[0:a]{voice},asplit[v1][v2];[1:a]atrim=0:{out_dur:.2f},volume={mv}[m];"
                  f"[m][v2]sidechaincompress=threshold=0.04:ratio=10:attack=20:release=500[md];"
                  f"[v1][md]amix=inputs=2:normalize=0:duration=first[a]")
        else:
            fc = (f"[0:a]{voice}[v1];[1:a]atrim=0:{out_dur:.2f},volume={mv}[m];"
                  f"[v1][m]amix=inputs=2:normalize=0:duration=first[a]")
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
        if v: cmd += ["-vf", ",".join(v)]
    else:
        cmd += ["-map", "0:v", "-map", "0:a?"]
        if v: cmd += ["-vf", ",".join(v)]
        if a: cmd += ["-af", ",".join(a)]
    cmd += (_enc() if v else ["-c:v", "copy"]) + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=_ENV)
    if r.returncode:
        raise RuntimeError("effects failed: " + r.stderr[-300:])
    return True

# ---------- title narration ----------
NARR_VOICES = {"en": "en-US-AndrewNeural", "ar": "ar-EG-ShakirNeural", "es": "es-ES-AlvaroNeural", "fr": "fr-FR-HenriNeural",
               "de": "de-DE-ConradNeural", "tr": "tr-TR-AhmetNeural", "ru": "ru-RU-DmitryNeural", "hi": "hi-IN-MadhurNeural",
               "ur": "ur-PK-AsadNeural", "fa": "fa-IR-FaridNeural", "he": "he-IL-AvriNeural", "pt": "pt-BR-AntonioNeural",
               "it": "it-IT-DiegoNeural", "ja": "ja-JP-KeitaNeural", "ko": "ko-KR-InJoonNeural", "zh": "zh-CN-YunxiNeural"}

def _clean_title(t):
    import re
    t = re.sub(r"#\w+", " ", t or "")
    t = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", " ", t)      # emoji
    return re.sub(r"\s+", " ", t).strip(" -|:")

def _tts(text, voice, lang, work, cid, log):
    """Synthesize the narration. Returns (mp3 path, seconds, voice) or None."""
    import asyncio, edge_tts, re
    voice = voice if voice and voice != "auto" else NARR_VOICES.get((lang or "en")[:2], NARR_VOICES["en"])
    mp3 = work / f"clip{cid}_nar.mp3"
    try:
        for attempt in range(3):          # the free voice service sometimes returns nothing: retry
            try:
                asyncio.run(edge_tts.Communicate(text, voice).save(str(mp3)))
                break
            except edge_tts.exceptions.NoAudioReceived:
                if attempt == 2: raise
                import time; time.sleep(1.5)
        r = subprocess.run([FFMPEG, "-i", str(mp3), "-f", "null", "-"], capture_output=True, text=True, env=_ENV)
        m = (re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr) or [None])[-1]
        secs = int(m[0]) * 3600 + int(m[1]) * 60 + float(m[2]) if m else 3.0
        return mp3, secs, voice
    except Exception as e:
        log(f"clip {cid}: narration skipped ({type(e).__name__}: {str(e)[:120]})")
        mp3.unlink(missing_ok=True)
        return None

def _narr_cfg(ed, job_narr, clip):
    """global < this video < this clip."""
    g = dict(settings.get().get("narration") or {})
    on, voice, vol, cap = g.get("enabled", False), g.get("voice"), g.get("volume", 1.0), g.get("title_caption", False)
    text = None
    for lay in (job_narr or {}, ed.get("narration") or {}):
        if lay.get("on") is not None: on = bool(lay["on"])
        if lay.get("voice"): voice = lay["voice"]
        if lay.get("vol"): vol = lay["vol"]
        if lay.get("title_caption") is not None: cap = bool(lay["title_caption"])
        if lay.get("text"): text = lay["text"]
    return {"on": on, "voice": voice, "vol": float(vol or 1.0), "caption": cap,
            "text": _clean_title(text or clip.get("title") or "")}

def _mix_narration(raw, mp3, secs, vol, work, cid, log, secs_total=3600.0):
    """Mix the voice over the start of the clip; the original sound ducks while it speaks."""
    mixed = work / f"clip{cid}_nar.mp4"
    try:
        fc = (f"[1:a]adelay=300|300,volume={vol},apad[n];[n]asplit[n1][n2];"
              f"[0:a][n2]sidechaincompress=threshold=0.015:ratio=14:attack=10:release=350:makeup=1[d];"
              f"[d][n1]amix=inputs=2:normalize=0:duration=first,atrim=duration={secs_total:.3f}[a]")
        r = subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(raw), "-i", str(mp3), "-filter_complex", fc,
                            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", str(mixed)], capture_output=True, text=True, env=_ENV)
        if r.returncode:
            raise RuntimeError(r.stderr[-200:])
        mixed.replace(raw)
        return True
    except Exception as e:
        log(f"clip {cid}: narration skipped ({type(e).__name__}: {str(e)[:120]})")
        return False
    finally:
        mp3.unlink(missing_ok=True); mixed.unlink(missing_ok=True)

# ---------- render ----------
def _run_ffmpeg(cmd, cwd, dur, prog, lo=0.0, hi=0.9):
    """Run ffmpeg with live progress (0-1 mapped into lo..hi)."""
    cmd = cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:]
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, env=_ENV)
    tail = []
    for line in p.stdout:
        if line.startswith("out_time_us="):
            try:
                if prog:
                    prog(lo + (hi - lo) * min(1.0, int(line.split("=")[1]) / 1e6 / dur))
            except ValueError:
                pass
        elif "=" not in line[:20]:
            tail.append(line)
    p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg failed: " + "".join(tail)[-400:])

def _plan_speaker(video, start, end, fw, fh, tr, prog, log, clip):
    try:
        from . import speaker
        if prog: prog(0.03, "Finding who is speaking")
        return speaker.plan(video, start, end, fw, fh, tr["words"],
                            prog=(lambda f: prog and prog(0.03 + 0.05 * f)))
    except Exception as e:
        log(f"clip {clip['id']}: speaker detection failed ({type(e).__name__}: {e})")
        return None

def render_clip(video, info, tr, clip, out_path, layout="auto", cap_style="pop",
                captions=True, log=print, prog=None, mode="auto", webcam=None, narr=None):
    ed = clip.get("edit") or {}
    layout = ed.get("layout") or layout
    cp = ed.get("captions") or {}
    cap_style = cp.get("style") or cap_style
    if cap_style == "off": captions = False
    start, end = float(clip["start"]), float(clip["end"])
    dur = end - start
    out_path = Path(out_path)
    work = out_path.parent
    raw = work / f"clip{clip['id']}_raw.mp4"
    ass_name = f"clip{clip['id']}.ass"
    nr = _narr_cfg(ed, narr, clip)
    tts = None
    if nr["on"] and nr["text"]:
        if prog: prog(0.01, "Recording title narration")
        tts = _tts(nr["text"], nr["voice"], tr.get("language"), work, clip["id"], log)
    title_ev = None
    if tts and nr["caption"]:
        sp = float((ed.get("video") or {}).get("speed") or 1.0)
        title_ev = {"text": nr["text"], "t0": 0.15 / sp, "t1": (0.3 + tts[1] + 0.5) / sp}
    n_cap = write_ass(work / ass_name, tr["words"] if captions else [], start, end, cap_style,
                      {**cp, "edits": ed.get("word_edits"), "title": title_ev}) if (captions or title_ev) else 0
    ass = f",ass={ass_name}" if n_cap else ""
    fw, fh = info["width"], info["height"]
    ts = xs = cam = spk = None
    used = layout
    if prog: prog(0.02, "Finding webcam and faces")
    if layout == "speaker":
        spk = _plan_speaker(video, start, end, fw, fh, tr, prog, log, clip)
        used = "speaker" if spk and spk["segments"] else "fit"
    elif layout in ("auto", "follow", "stack"):
        known = webcam is not None and webcam.get("checked")
        cam = tuple(webcam["box"]) if known and webcam.get("box") else None
        ratio = 0.0
        need_track = layout == "follow" or (not cam and mode != "gaming" and layout in ("auto", "stack"))
        if need_track or not known:
            ts, xs, ratio, c2 = track_faces(video, start, end, fw, fh,
                                            prog=(lambda f: prog and prog(0.02 + 0.06 * f)))
            if not known:
                cam = c2
        if layout == "auto" or (layout == "stack" and not cam):
            if cam:
                used = "stack"
            elif mode == "gaming":
                used = "fit"        # gameplay is the content: never zoom on faces
            else:
                used = "follow" if ratio >= 0.4 else "fit"
                if used == "follow":    # two or more people on screen: cut to whoever is talking
                    spk = _plan_speaker(video, start, end, fw, fh, tr, prog, log, clip)
                    if spk and spk["people"] >= 2 and spk["segments"]:
                        used = "speaker"
        log(f"clip {clip['id']}: webcam {'yes' if cam else 'no'} -> {used}")
    if prog: prog(0.08, "Encoding video")

    if used == "follow":
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cw = min(fw, int(fh * 9 / 16))
        n = int(dur * fps)
        path = smooth_path(ts, xs, fps, n)
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        cmd = [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
               "-ss", str(start), "-t", str(dur), "-i", str(video),
               "-map", "0:v", "-map", "1:a?", "-vf", "format=yuv420p" + ass,
               *_enc(), "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", raw.name]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, cwd=work, env=_ENV)
        for i in range(n):
            ok, fr = cap.read()
            if not ok:
                break
            x0 = int(np.clip(path[i] * fw - cw / 2, 0, fw - cw))
            pr.stdin.write(cv2.resize(fr[:, x0:x0 + cw], (W, H),
                                      interpolation=cv2.INTER_AREA).tobytes())
            if prog and i % 15 == 0:
                prog(0.08 + 0.82 * i / n)
        pr.stdin.close()
        pr.wait()
        cap.release()
        if pr.returncode:
            raise RuntimeError("ffmpeg failed (follow layout)")
    else:
        if used == "stack":     # webcam on top, gameplay below (gameplay slice avoids the webcam)
            bx1, by1, bx2, by2 = cam
            top_h = 700
            cropw = (bx2 - bx1) * fw
            croph = cropw * top_h / W
            if croph < (by2 - by1) * fh:
                croph = (by2 - by1) * fh
                cropw = croph * W / top_h
            croph = int(min(fh, croph))
            cropw = int(min(fw, croph * W / top_h, max(cropw, 1)))
            cropw = max(cropw, 2)
            x0 = int(np.clip((bx1 + bx2) / 2 * fw - cropw / 2, 0, fw - cropw))
            y0 = int(np.clip((by1 + by2) / 2 * fh - croph / 2, 0, fh - croph))
            bot_h = H - top_h
            gw = int(min(fw, fh * W / bot_h))
            gx = (fw - gw) // 2
            if bx2 <= 0.5:
                gx = int(np.clip(max(gx, bx2 * fw), 0, fw - gw))
            elif bx1 >= 0.5:
                gx = int(np.clip(min(gx, bx1 * fw - gw), 0, fw - gw))
            fc = (f"[0:v]split[a][b];[a]crop={cropw}:{croph}:{x0}:{y0},scale={W}:{top_h}[t];"
                  f"[b]crop={gw}:{fh}:{gx}:0,scale={W}:{bot_h}[g];[t][g]vstack,format=yuv420p{ass}[v]")
        elif used == "speaker":  # hard cuts between still crops of whoever is talking
            segs = spk["segments"]
            nseg = len(segs)
            parts, labels = [], []
            for k, sg in enumerate(segs):
                x0, y0, cw, ch = sg["crop"]
                t1 = dur if k == nseg - 1 else sg["t1"]
                parts.append(f"[s{k}]trim=start={sg['t0']:.3f}:end={t1:.3f},setpts=PTS-STARTPTS,"
                             f"crop={cw}:{ch}:{x0}:{y0},scale={W}:{H}:flags=lanczos,setsar=1[v{k}]")
                labels.append(f"[v{k}]")
            split = f"[0:v]split={nseg}" + "".join(f"[s{k}]" for k in range(nseg)) if nseg > 1 else None
            if nseg > 1:
                fc = split + ";" + ";".join(parts) + ";" + "".join(labels) + f"concat=n={nseg}:v=1:a=0,format=yuv420p{ass}[v]"
            else:
                x0, y0, cw, ch = segs[0]["crop"]
                fc = f"[0:v]crop={cw}:{ch}:{x0}:{y0},scale={W}:{H}:flags=lanczos,format=yuv420p{ass}[v]"
            log(f"clip {clip['id']}: speaker cuts {nseg} shots, {spk['people']} people")
        elif used == "manual":  # user-placed crop box, optional pan to a second position
            m = ed.get("manual") or {}
            ch = int(max(0.25, min(1.0, float(m.get("zoom", 1.0)))) * fh) // 2 * 2
            cw = int(ch * 9 / 16) // 2 * 2
            def px(c): return int(np.clip(float(c) * fw - cw / 2, 0, fw - cw))
            x0 = px(m.get("cx", 0.5))
            x1 = px(m["cx2"]) if m.get("cx2") not in (None, "") else x0
            y0 = int(np.clip(float(m.get("cy", 0.5)) * fh - ch / 2, 0, fh - ch))
            xe = f"{x0}+({x1}-{x0})*t/{dur:.3f}" if x1 != x0 else str(x0)
            fc = f"[0:v]crop={cw}:{ch}:x='{xe}':y={y0},scale={W}:{H}:flags=lanczos,format=yuv420p{ass}[v]"
        elif used == "game":    # gameplay only, centered 9:16 crop
            fc = f"[0:v]crop=ih*9/16:ih,scale={W}:{H},format=yuv420p{ass}[v]"
        else:                   # fit: full frame over a blurred copy
            fc = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},boxblur=30:5[bg];[b]scale={W}:-2[fg];"
                  f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p{ass}[v]")
        cmd = [FFMPEG, "-y", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(video),
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", *_enc(),
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", raw.name]
        _run_ffmpeg(cmd, work, dur, prog, 0.08, 0.9)
    if prog: prog(0.93, "Balancing loudness")
    if ed.get("audio") or ed.get("video"):
        if prog: prog(0.9, "Applying sound and video effects")
        fx = work / f"clip{clip['id']}_fx.mp4"
        if _post(raw, fx, ed, dur, log):
            raw.unlink(missing_ok=True); fx.replace(raw)
    if tts:
        if _mix_narration(raw, tts[0], tts[1], nr["vol"], work, clip["id"], log, dur / float((ed.get("video") or {}).get("speed") or 1.0)):
            log(f"clip {clip['id']}: narration ({tts[2]}){' + title caption' if title_ev else ''}: {nr['text'][:60]}")
    norm = (ed.get("audio") or {}).get("normalize", True)
    if norm:
        ok = _normalize(raw, out_path)
    else:
        shutil.copy2(raw, out_path); ok = True
    raw.unlink(missing_ok=True)
    if prog: prog(1.0, "Done")
    if not ok:
        log(f"clip {clip['id']}: loudness step skipped")
    return used
