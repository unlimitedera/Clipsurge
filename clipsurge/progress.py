# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Live progress for a job: stages, sub-steps with percentages, detail text, cancel flag."""
import threading, time

class Cancelled(Exception):
    pass

def fmt_bytes(n):
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024

def fmt_time(s):
    s = int(max(0, s or 0))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"

class Tracker:
    def __init__(self, jid):
        self.jid = jid
        self.lock = threading.Lock()
        self.cancel = False
        self.clips = {}          # clip id -> {"f": 0-1, "note": str}
        self.reset()

    def reset(self):
        self.subs, self.note, self.detail = [], "", ""
        self.touched = time.time()

    def plan(self, names, note=""):
        """Start a stage with a list of sub-steps (name, or (name, weight))."""
        with self.lock:
            self.subs = [{"name": n if isinstance(n, str) else n[0], "w": 1 if isinstance(n, str) else n[1],
                          "f": 0.0, "detail": "", "state": "wait"} for n in names]
            self.note, self.detail, self.touched = note, "", time.time()

    def _find(self, name):
        for s in self.subs:
            if s["name"] == name:
                return s
        s = {"name": name, "w": 1, "f": 0.0, "detail": "", "state": "wait"}
        self.subs.append(s)
        return s

    def set(self, name, f=None, detail=None):
        """f in 0..1, or None for 'working, unknown length'."""
        if self.cancel:
            raise Cancelled()
        with self.lock:
            s = self._find(name)
            s["state"] = "run"
            if f is not None:
                s["f"] = max(0.0, min(1.0, float(f)))
            else:
                s["f"] = s["f"] if s["f"] else 0.0
                s["unk"] = True
            if f is not None:
                s["unk"] = False
            if detail is not None:
                s["detail"] = detail
            self.note = name
            self.detail = s["detail"]
            self.touched = time.time()
            for o in self.subs:                     # anything before the active one is finished
                if o is s:
                    break
                if o["state"] != "skip":
                    o["state"], o["f"], o["unk"] = "done", 1.0, False

    def done(self, name, detail=""):
        with self.lock:
            s = self._find(name)
            s.update(state="done", f=1.0, unk=False, detail=detail or s["detail"])
            self.touched = time.time()

    def skip(self, name, why=""):
        with self.lock:
            s = self._find(name)
            s.update(state="skip", f=1.0, unk=False, detail=why)

    def finish_all(self):
        with self.lock:
            for s in self.subs:
                if s["state"] != "skip":
                    s.update(state="done", f=1.0, unk=False)

    @property
    def sp(self):
        with self.lock:
            live = [s for s in self.subs if s["state"] != "skip"]
            tot = sum(s["w"] for s in live)
            return sum(s["w"] * s["f"] for s in live) / tot if tot else 0.0

    def snapshot(self):
        with self.lock:
            return {"sp": self.sp_unlocked(), "note": self.note, "detail": self.detail,
                    "subs": [dict(s) for s in self.subs], "idle": int(time.time() - self.touched),
                    "clips": {k: dict(v) for k, v in self.clips.items()}}

    def sp_unlocked(self):
        live = [s for s in self.subs if s["state"] != "skip"]
        tot = sum(s["w"] for s in live)
        return sum(s["w"] * s["f"] for s in live) / tot if tot else 0.0

    def check(self):
        if self.cancel:
            raise Cancelled()
