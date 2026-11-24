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

def detect_webcam(video, duration, fw, fh, n=30, prog=None):
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

def write_ass(path, words, start, end, style="pop"):
    font, size, col, hi, ol = STYLES.get(style, STYLES["pop"])
    size = int(size * settings.get()["video"]["caption_size"] / 84)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n"
            "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,"
            "Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Default,{font},{size},&H00{col},&H00{col},&H00000000,&H80000000,-1,0,0,0,"
            f"100,100,0,0,1,{ol},2,2,60,60,420,1\n\n[Events]\nFormat: Layer,Start,End,Style,"
            "Name,MarginL,MarginR,MarginV,Effect,Text\n")
    ws = [dict(w) for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]
    for i in range(1, len(ws)):               # starts must increase
        ws[i]["s"] = max(ws[i]["s"], ws[i - 1]["s"] + 0.06)
    lines = []
    for g in range(0, len(ws), 3):
        grp = ws[g:g + 3]
        nxt = ws[g + 3]["s"] if g + 3 < len(ws) else None
        for k, w in enumerate(grp):
            s = w["s"] - start
            if k + 1 < len(grp):
                e = grp[k + 1]["s"] - start          # hold until the next word starts
            else:
                e = w["e"] + 0.2
                if nxt is not None:
                    e = min(e, nxt)                  # never overlap the next group
                e -= start
            e = max(e, s + 0.05)
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

def render_clip(video, info, tr, clip, out_path, layout="auto", cap_style="pop",
                captions=True, log=print, prog=None, mode="auto", webcam=None):
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
    if prog: prog(0.02, "Finding webcam and faces")
    if layout in ("auto", "follow", "stack"):
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
    ok = _normalize(raw, out_path)
    raw.unlink(missing_ok=True)
    if prog: prog(1.0, "Done")
    if not ok:
        log(f"clip {clip['id']}: loudness step skipped")
    return used
