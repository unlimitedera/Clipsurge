# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Stages 4-7: smart crop, captions, audio polish, export."""
import subprocess
from pathlib import Path
import cv2
import numpy as np
from .config import FFMPEG

W, H = 1080, 1920

# ---------- face tracking ----------
def track_faces(video, start, end, step=0.4):
    """Return (times, x_center_fraction or nan, face_ratio)."""
    cap = cv2.VideoCapture(str(video))
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    ts, xs = [], []
    t = start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            break
        small = cv2.resize(fr, (640, int(fr.shape[0] * 640 / fr.shape[1])))
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        f = cas.detectMultiScale(g, 1.2, 5, minSize=(40, 40))
        if len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])
            xs.append((x + w / 2) / small.shape[1])
        else:
            xs.append(np.nan)
        ts.append(t - start)
        t += step
    cap.release()
    xs = np.array(xs, dtype=float)
    ratio = float(np.mean(~np.isnan(xs))) if len(xs) else 0.0
    return np.array(ts), xs, ratio

def smooth_path(ts, xs, fps, n_frames):
    ok = ~np.isnan(xs)
    if ok.sum() == 0:
        return np.full(n_frames, 0.5)
    t = np.arange(n_frames) / fps
    path = np.interp(t, ts[ok], xs[ok])
    a, out = 0.08, np.empty(n_frames)   # exponential smoothing: no jitter
    out[0] = path[0]
    for i in range(1, n_frames):
        out[i] = out[i - 1] + a * (path[i] - out[i - 1])
    return out

# ---------- captions (ASS, word-by-word pop) ----------
def _ts(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"

STYLES = {  # name: (font, size, primary BGR, highlight BGR, outline)
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

# ---------- render ----------
def _encoder_args():
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

def render_clip(video, info, tr, clip, out_path, layout="auto", cap_style="pop",
                captions=True, log=print):
    start, end = float(clip["start"]), float(clip["end"])
    dur = end - start
    work = Path(out_path).parent
    ass_name = f"clip{clip['id']}.ass"
    n_cap = write_ass(work / ass_name, tr["words"], start, end, cap_style) if captions else 0
    vf_ass = f",ass={ass_name}" if n_cap else ""
    af = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    used = layout
    ts = xs = None
    if layout in ("auto", "follow"):
        ts, xs, ratio = track_faces(video, start, end)
        used = "follow" if (layout == "follow" or ratio >= 0.4) else "fit"
        log(f"face ratio {ratio:.0%} -> layout {used}")
    if used == "follow":
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        fw, fh = int(cap.get(3)), int(cap.get(4))
        cw = min(fw, int(fh * 9 / 16))
        n = int(dur * fps)
        path = smooth_path(ts, xs, fps, n)
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        cmd = [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
               "-ss", str(start), "-t", str(dur), "-i", str(video),
               "-map", "0:v", "-map", "1:a?", "-vf", "format=yuv420p" + vf_ass, *af,
               *_encoder_args(), "-c:a", "aac", "-b:a", "160k", "-shortest",
               "-movflags", "+faststart", Path(out_path).name]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=work)
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
    else:  # fit: blurred background + full frame centered
        fc = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},boxblur=30:5[bg];[b]scale={W}:-2[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p{vf_ass}[v]")
        cmd = [FFMPEG, "-y", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(video),
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", *af,
               *_encoder_args(), "-c:a", "aac", "-b:a", "160k",
               "-movflags", "+faststart", Path(out_path).name]
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("ffmpeg failed: " + r.stderr[-400:])
    return used
