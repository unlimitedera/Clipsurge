# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Stages 4-7: smart crop, captions, audio polish, export."""
import os, shutil, subprocess, sys
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from .config import FFMPEG

W, H = 1080, 1920
_ENV = dict(os.environ, PATH=str(Path(FFMPEG).parent) + os.pathsep + os.environ.get("PATH", ""))

# ---------- face / webcam detection ----------
def track_faces(video, start, end, step=0.4):
    """Returns times, x-centers (0-1, nan = none), face_ratio, facecam box or None.
    facecam box = (cx, cy, w) as fractions when a small, static face sits near a corner."""
    cap = cv2.VideoCapture(str(video))
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    ts, xs, boxes = [], [], []
    t = start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            break
        sm = cv2.resize(fr, (640, int(fr.shape[0] * 640 / fr.shape[1])))
        f = cas.detectMultiScale(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), 1.2, 5, minSize=(30, 30))
        if len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])
            sw, sh = sm.shape[1], sm.shape[0]
            xs.append((x + w / 2) / sw)
            boxes.append(((x + w / 2) / sw, (y + h / 2) / sh, w / sw))
        else:
            xs.append(np.nan)
        ts.append(t - start)
        t += step
    cap.release()
    xs = np.array(xs, dtype=float)
    ratio = float(np.mean(~np.isnan(xs))) if len(xs) else 0.0
    cam = None
    if len(boxes) >= 4:
        b = np.array(boxes)
        cx, cy, w = np.median(b, axis=0)
        static = b[:, 0].std() < 0.03 and b[:, 1].std() < 0.04
        corner = (cx < 0.3 or cx > 0.7) and (cy < 0.35 or cy > 0.65)
        if static and corner and w < 0.25:
            cam = (float(cx), float(cy), float(w))
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

def write_ass(path, words, start, end, style="pop"):
    font, size, col, hi, ol = STYLES.get(style, STYLES["pop"])
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n"
            "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,"
            "Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Default,{font},{size},&H00{col},&H00{col},&H00000000,&H80000000,-1,0,0,0,"
            f"100,100,0,0,1,{ol},2,2,60,60,420,1\n\n[Events]\nFormat: Layer,Start,End,Style,"
            "Name,MarginL,MarginR,MarginV,Effect,Text\n")
    ws = [w for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]
    lines = []
    for g in range(0, len(ws), 3):
        grp = ws[g:g + 3]
        for k, w in enumerate(grp):
            s = w["s"] - start
            e = (grp[k + 1]["s"] if k + 1 < len(grp) else w["e"] + 0.15) - start
            parts = []
            for m, x in enumerate(grp):
                txt = x["w"].upper().replace("{", "").replace("}", "")
                parts.append(("{\\c&H%s&}%s{\\c&H%s&}" % (hi, txt, col)) if m == k else txt)
            lines.append(f"Dialogue: 0,{_ts(s)},{_ts(e)},Default,,0,0,0,,{{\\fscx92\\fscy92"
                         f"\\t(0,80,\\fscx100\\fscy100)}}{' '.join(parts)}")
    Path(path).write_text(head + "\n".join(lines) + "\n", "utf-8")
    return len(lines)

# ---------- encode ----------
@lru_cache(maxsize=1)
def _nvenc_ok():
    r = subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
                        "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, env=_ENV)
    return r.returncode == 0

def _enc():
    if _nvenc_ok():
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

def _normalize(raw, final):
    """Loudness balance to -14 LUFS with ffmpeg-normalize; falls back to the raw file."""
    try:
        r = subprocess.run([sys.executable, "-m", "ffmpeg_normalize", str(raw), "-o", str(final), "-f", "-nt", "ebu",
                        "-t", "-14", "-tp", "-1.5", "-c:a", "aac", "-b:a", "160k"],
                           capture_output=True, text=True, env=_ENV)
        good = r.returncode == 0 and Path(final).exists()
    except Exception:
        good = False
    if not good:
        shutil.copy2(raw, final)
        return False
    return True

# ---------- render ----------
def render_clip(video, info, tr, clip, out_path, layout="auto", cap_style="pop",
                captions=True, log=print):
    start, end = float(clip["start"]), float(clip["end"])
    dur = end - start
    out_path = Path(out_path)
    work = out_path.parent
    raw = work / f"clip{clip['id']}_raw.mp4"
    ass_name = f"clip{clip['id']}.ass"
    n_cap = write_ass(work / ass_name, tr["words"], start, end, cap_style) if captions else 0
    ass = f",ass={ass_name}" if n_cap else ""
    fw, fh = info["width"], info["height"]
    ts = xs = cam = None
    used = layout
    if layout in ("auto", "follow", "stack"):
        ts, xs, ratio, cam = track_faces(video, start, end)
        if layout == "auto":
            used = "stack" if cam else ("follow" if ratio >= 0.4 else "fit")
        elif layout == "stack" and not cam:
            used = "follow" if ratio >= 0.4 else "fit"
        log(f"clip {clip['id']}: face {ratio:.0%}, webcam {'yes' if cam else 'no'} -> {used}")

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
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=work, env=_ENV)
        for i in range(n):
            ok, fr = cap.read()
            if not ok:
                break
            x0 = int(np.clip(path[i] * fw - cw / 2, 0, fw - cw))
            pr.stdin.write(cv2.resize(fr[:, x0:x0 + cw], (W, H),
                                      interpolation=cv2.INTER_AREA).tobytes())
        pr.stdin.close()
        pr.wait()
        cap.release()
        if pr.returncode:
            raise RuntimeError("ffmpeg failed (follow layout)")
    else:
        if used == "stack":     # webcam on top, gameplay below
            cx, cy, cwid = cam
            top_h = 700
            cropw = int(min(fw, max(cwid * fw * 2.6, 360)))
            croph = int(min(fh, cropw * top_h / W))
            cropw = int(min(fw, croph * W / top_h))
            x0 = int(np.clip(cx * fw - cropw / 2, 0, fw - cropw))
            y0 = int(np.clip(cy * fh - croph / 2, 0, fh - croph))
            bot_h = H - top_h
            gw = int(min(fw, fh * W / bot_h))
            gx = (fw - gw) // 2
            fc = (f"[0:v]split[a][b];[a]crop={cropw}:{croph}:{x0}:{y0},scale={W}:{top_h}[t];"
                  f"[b]crop={gw}:{fh}:{gx}:0,scale={W}:{bot_h}[g];[t][g]vstack,format=yuv420p{ass}[v]")
        else:                   # fit: full frame over a blurred copy
            fc = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},boxblur=30:5[bg];[b]scale={W}:-2[fg];"
                  f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p{ass}[v]")
        cmd = [FFMPEG, "-y", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(video),
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", *_enc(),
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", raw.name]
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, env=_ENV)
        if r.returncode:
            raise RuntimeError("ffmpeg failed: " + r.stderr[-400:])
    ok = _normalize(raw, out_path)
    raw.unlink(missing_ok=True)
    if not ok:
        log(f"clip {clip['id']}: loudness step skipped")
    return used
