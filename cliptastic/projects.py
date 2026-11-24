# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Projects: a named collection of videos (jobs) that share a brief (what to look for) and defaults."""
import json, shutil, threading, time, uuid
from .config import DATA, JOBS

DIR = DATA / "projects"
DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.RLock()

def _p(pid): return DIR / pid / "project.json"

def _save(pr):
    with _lock:
        _p(pr["id"]).parent.mkdir(parents=True, exist_ok=True)
        _p(pr["id"]).write_text(json.dumps(pr, indent=1), "utf-8")

def get(pid):
    return json.loads(_p(pid).read_text("utf-8"))

def ensure_inbox():
    """Every job belongs to a project. Older jobs and quick adds land in 'Inbox'."""
    if not _p("inbox").exists():
        _save({"id": "inbox", "name": "Inbox", "description": "Videos added without a project",
               "created": time.time(), "brief": {"ideas": [], "avoid": []}, "defaults": {}})
    for p in JOBS.glob("*/job.json"):
        try:
            j = json.loads(p.read_text("utf-8"))
            if not j.get("project"):
                j["project"] = "inbox"
                p.write_text(json.dumps(j, indent=1), "utf-8")
        except Exception:
            pass

def create(name, description="", brief=None, defaults=None):
    pr = {"id": time.strftime("%y%m%d") + "-" + uuid.uuid4().hex[:5], "name": name.strip() or "Untitled project",
          "description": description, "created": time.time(),
          "brief": _brief(brief), "defaults": _defaults(defaults)}
    _save(pr)
    return pr

def _lines(v):
    if isinstance(v, str):
        v = v.splitlines()
    return [x.strip() for x in (v or []) if x and x.strip()][:30]

def _brief(b):
    b = b or {}
    return {"ideas": _lines(b.get("ideas")), "avoid": _lines(b.get("avoid"))}

DEF_KEYS = ("mode", "count", "minlen", "maxlen", "layout", "captions", "language", "whisper_model")

def _defaults(d):
    return {k: d[k] for k in DEF_KEYS if d and d.get(k) not in (None, "")}

def update(pid, data):
    pr = get(pid)
    if "name" in data and data["name"].strip(): pr["name"] = data["name"].strip()
    if "description" in data: pr["description"] = data["description"]
    if "brief" in data: pr["brief"] = _brief(data["brief"])
    if "defaults" in data: pr["defaults"] = _defaults(data["defaults"])
    _save(pr)
    return pr

def delete(pid):
    shutil.rmtree(DIR / pid, ignore_errors=True)

def all_projects():
    out = []
    for p in DIR.glob("*/project.json"):
        try: out.append(json.loads(p.read_text("utf-8")))
        except Exception: pass
    return sorted(out, key=lambda x: (x["id"] != "inbox", -x["created"]))
