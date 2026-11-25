# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Cut-to-speaker planning: who is talking, when, and a still crop box for each shot.

Idea: audio alone cannot say WHO talks on a single mic, so combine
  1. a speech mask from the transcript words (someone is talking),
  2. lip motion per person (frame difference around the mouth, minus head motion),
  3. hysteresis (min shot length, margin to switch) so the cut does not flicker.
Faces come from YuNet (OpenCV FaceDetectorYN, much better than Haar on small or turned faces),
Haar is the fallback when the model file is missing.
"""
import subprocess
from pathlib import Path
import cv2
import numpy as np
from .config import FFMPEG
from .render import _ENV

MODEL = Path(__file__).resolve().parent.parent / "models" / "face_detection_yunet_2023mar.onnx"
FPS = 6.0           # analysis rate
DET_W = 1280        # detector width (faces in wide podcast shots are tiny)
MIN_SHOT = 1.6      # seconds a shot must last before we may cut again
SWITCH_RATIO = 1.35 # newcomer must beat the current speaker by this factor
SWITCH_HOLD = 0.5   # ... for this long
LIVE_MIN = 0.8      # a real face moves at least this much (frame diff, 0-255)
SMOOTH = 1.0        # seconds of lip motion averaged


def _detector(w, h):
    if MODEL.exists():
        try:
            return cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), 0.6, 0.3, 50)
        except Exception:
            pass
    return None


def _faces(det, cas, img):
    """-> list of dicts {box:(x,y,w,h), mouth:(x,y), eyes:(x,y)} in image pixels."""
    out = []
    if det is not None:
        _, f = det.detect(img)
        for r in (f if f is not None else []):
            x, y, w, h = r[:4]
            re, le, mr, ml = (r[4], r[5]), (r[6], r[7]), (r[10], r[11]), (r[12], r[13])
            out.append({"box": (x, y, w, h), "mouth": ((mr[0] + ml[0]) / 2, (mr[1] + ml[1]) / 2),
                        "eyes": ((re[0] + le[0]) / 2, (re[1] + le[1]) / 2)})
    elif cas is not None:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        for x, y, w, h in cas.detectMultiScale(g, 1.15, 5, minSize=(24, 24)):
            out.append({"box": (x, y, w, h), "mouth": (x + w / 2, y + h * 0.75), "eyes": (x + w / 2, y + h * 0.38)})
    return out


def _roi(gray, cx, cy, hw, hh):
    H, W = gray.shape
    x1, x2 = int(max(0, cx - hw)), int(min(W, cx + hw))
    y1, y2 = int(max(0, cy - hh)), int(min(H, cy + hh))
    if x2 - x1 < 4 or y2 - y1 < 3:
        return None
    return x1, y1, x2, y2


def _motion(prev, cur, roi):
    if roi is None:
        return 0.0
    x1, y1, x2, y2 = roi
    a = cv2.resize(prev[y1:y2, x1:x2], (24, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
    b = cv2.resize(cur[y1:y2, x1:x2], (24, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
    # remove brightness drift so camera exposure changes do not read as lip movement
    return float(np.mean(np.abs((b - b.mean()) - (a - a.mean()))))


def analyse(video, start, end, fw, fh, words, prog=None):
    """Returns dict(times, ids, tracks, scores, speech, fw, fh). tracks[id] = list of (frame_idx, box)."""
    sw = DET_W if fw > DET_W else fw
    sh = int(round(fh * sw / fw / 2)) * 2
    det = _detector(sw, sh)
    cas = None if det is not None else cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    p = subprocess.Popen([FFMPEG, "-v", "error", "-ss", str(start), "-t", str(end - start), "-i", str(video),
                          "-vf", f"fps={FPS},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, env=_ENV)
    total = max(1, int((end - start) * FPS))
    centers = []                 # identity -> running (cx, cy, size) in detector pixels
    tracks = {}                  # identity -> {frame: (x,y,w,h) in source pixels}
    raw = []                     # per frame: {id: (mouth_motion, eye_motion)}
    last_box = {}                # identity -> (frame, face dict)
    prev = None
    cuts = [0]                   # first frame of every shot (camera cut = new shot)
    k = sw / fw
    n = 0
    while True:
        buf = p.stdout.read(sw * sh * 3)
        if len(buf) < sw * sh * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cut = prev is not None and float(np.mean(np.abs(gray.astype(np.int16) - prev.astype(np.int16)))) > 28
        if cut:
            cuts.append(n)
            last_box.clear()     # a new camera angle: nobody carries over
        fs = _faces(det, cas, img)
        row = {}
        seen = set()
        for f in sorted(fs, key=lambda d: -d["box"][2] * d["box"][3]):
            x, y, w, h = f["box"]
            cx, cy = x + w / 2, y + h / 2
            # match to an identity by 2D position (people keep their seat); new seat -> new identity
            best, bd = None, 1.0
            for i, (ox, oy, os_) in enumerate(centers):
                d = float(np.hypot(ox - cx, oy - cy)) / max(w, os_, 8)
                if d < bd and i not in seen:
                    best, bd = i, d
            if best is None:
                centers.append((cx, cy, w))
                best = len(centers) - 1
            else:
                ox, oy, os_ = centers[best]
                centers[best] = (0.8 * ox + 0.2 * cx, 0.8 * oy + 0.2 * cy, 0.8 * os_ + 0.2 * w)
            seen.add(best)
            tracks.setdefault(best, {})[n] = (x / k, y / k, w / k, h / k)
            last_box[best] = (n, f)
        # people whose face was missed this frame keep their last box for up to 1.5 s
        for i, (fn, f) in list(last_box.items()):
            if i not in seen and n - fn <= int(3.0 * FPS):
                seen.add(i)
        for i in seen:
            f = last_box[i][1]
            if prev is None or cut:
                row[i] = None
                continue
            x, y, w, h = f["box"]
            mx, my = f["mouth"]
            ex, ey = f["eyes"]
            hw, hh = max(5, w * 0.30), max(4, h * 0.17)
            row[i] = (_motion(prev, gray, _roi(gray, mx, my, hw, hh)),
                      _motion(prev, gray, _roi(gray, ex, ey, hw, hh)))
        raw.append(row)
        prev = gray
        n += 1
        if prog and n % 6 == 0:
            prog(min(1.0, n / total))
    p.stdout.close(); p.wait()
    ids = sorted(i for i in tracks if len(tracks[i]) >= 3)
    # drop faces that never move at all (paintings, posters, photos on the wall)
    live = {}
    for i in ids:
        v = [max(r[i]) for r in raw if r.get(i)]
        live[i] = float(np.percentile(v, 90)) if v else 0.0
    ids = [i for i in ids if live[i] >= LIVE_MIN]
    # lip score = mouth motion minus part of head motion
    sc = {i: np.full(n, np.nan) for i in ids}
    for t, row in enumerate(raw):
        for i in ids:
            v = row.get(i)
            if v:
                sc[i][t] = max(0.0, v[0] - 0.7 * v[1])
    # speech mask from transcript words
    times = np.arange(n) / FPS
    speech = np.zeros(n, bool)
    for w in words:
        a, b = w["s"] - start, w["e"] - start
        if b < 0 or a > end - start:
            continue
        speech[int(max(0, a) * FPS):int(min(end - start, b) * FPS) + 1] = True
    a = {"cuts": cuts, "times": times, "ids": ids, "tracks": {i: tracks[i] for i in ids}, "scores": sc,
         "speech": speech, "live": live, "n": n, "fw": fw, "fh": fh}
    # a "face" much bigger than the others in the same shot is a painting or poster, not a person
    med = {i: float(np.median([b[2] for b in tracks[i].values()])) for i in ids}
    bad = set()
    for s0, s1 in _shots(a):
        vis = [i for i in ids if _visible(a, s0, s1, i)]
        for i in vis:
            others = [med[j] for j in vis if j != i]
            if len(others) >= 2 and med[i] > 2.2 * float(np.median(others)):
                bad.add(i)
    if bad:
        a["ids"] = [i for i in ids if i not in bad]
        a["tracks"] = {i: a["tracks"][i] for i in a["ids"]}
    return a


def _shots(a):
    n, cuts = a["n"], a["cuts"] + [a["n"]]
    return [(cuts[k], cuts[k + 1]) for k in range(len(cuts) - 1) if cuts[k + 1] > cuts[k]]


def _visible(a, s, t, i):
    """Is person i really seen (detected, not just remembered) in frames [s, t)?"""
    c = sum(1 for f in a["tracks"].get(i, {}) if s <= f < t)
    return c >= 2 and c >= 0.25 * (t - s) or c >= 1 and t - s <= 2


def decide(a):
    """Active speaker per frame, decided shot by shot. -1 = nobody visible."""
    ids, n = a["ids"], a["n"]
    out = np.full(n, -1)
    if not ids or n == 0:
        return out
    win = max(2, int(SMOOTH * FPS))
    allv = np.concatenate([a["scores"][i][~np.isnan(a["scores"][i])] for i in ids] + [np.zeros(1)])
    scale = max(float(np.percentile(allv, 75)) if allv.size else 1.0, 0.5)
    sm = {i: np.convolve(np.nan_to_num(a["scores"][i], nan=0.0), np.ones(win) / win, mode="same") / scale for i in ids}
    cur = None
    last_switch = -999
    pending, pend_t = None, 0
    for s0, s1 in _shots(a):
        vis = [i for i in ids if _visible(a, s0, s1, i)]
        if not vis:
            cur = None
            continue
        if cur not in vis:      # new shot or the speaker left the frame: look ahead 1.5 s and pick the most active
            hz = min(s1, s0 + int(1.5 * FPS))
            cur = max(vis, key=lambda i: float(np.mean(sm[i][s0:hz])))
            last_switch, pending = s0, None
        for t in range(s0, s1):
            if len(vis) > 1 and a["speech"][t]:      # only cut while somebody is actually talking
                vals = {i: sm[i][t] for i in vis}
                top = max(vals, key=vals.get)
                if top != cur and vals[top] > SWITCH_RATIO * vals[cur] + 0.15:
                    if pending == top:
                        pend_t += 1
                    else:
                        pending, pend_t = top, 1
                    if pend_t >= SWITCH_HOLD * FPS and (t - last_switch) >= MIN_SHOT * FPS:
                        cur, last_switch, pending = top, t, None
                else:
                    pending = None
            out[t] = cur
    return out


def segments(a, who):
    """-> list of dict(t0, t1, id, box). box = median face box of that person in the segment (None = no face)."""
    n = a["n"]
    if n == 0:
        return []
    bounds = {s0 for s0, _ in _shots(a)}
    segs, s = [], 0
    for t in range(1, n + 1):
        if t == n or who[t] != who[s] or t in bounds:
            segs.append((s, t, int(who[s])))
            s = t
    out = []
    for s, t, i in segs:
        fr = [b for f, b in a["tracks"].get(i, {}).items() if s <= f < t] if i >= 0 else []
        box = tuple(float(np.median([b[k] for b in fr])) for k in range(4)) if fr else None
        out.append({"t0": s / FPS, "t1": t / FPS, "id": i, "box": box})
    if out:
        out[0]["t0"] = 0.0
    return out


def crop_for(box, fw, fh, aspect=9 / 16, min_frac=0.5):
    """Still crop (x, y, w, h ints) around a face: tight but never below min_frac of the frame height."""
    x, y, w, h = box
    ch = float(np.clip(h * 4.2, fh * min_frac, fh))
    cw = ch * aspect
    if cw < w * 2.2:               # very wide face box: make room
        cw = w * 2.2
        ch = cw / aspect
    ch = min(ch, fh); cw = ch * aspect
    cx = x + w / 2
    cy = y + h / 2 + ch * 0.12     # face in the upper third, a bit of shoulders below
    x0 = float(np.clip(cx - cw / 2, 0, fw - cw))
    y0 = float(np.clip(cy - ch / 2, 0, fh - ch))
    return int(x0) // 2 * 2, int(y0) // 2 * 2, int(cw) // 2 * 2, int(ch) // 2 * 2


def plan(video, start, end, fw, fh, words, prog=None):
    a = analyse(video, start, end, fw, fh, words, prog)
    who = decide(a)
    segs = segments(a, who)
    for s in segs:
        if s["box"]:
            s["crop"] = crop_for(s["box"], fw, fh)
        else:                   # nobody found in this shot: centred vertical slice
            cw = int(fh * 9 / 16) // 2 * 2
            s["crop"] = ((fw - cw) // 2 // 2 * 2, 0, cw, fh // 2 * 2)
    people = max([sum(1 for i in a["ids"] if _visible(a, s0, s1, i)) for s0, s1 in _shots(a)] + [0])
    return {"people": people, "segments": segs, "analysis": a, "who": who}
