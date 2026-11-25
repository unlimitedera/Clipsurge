# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Upload and download history. Uploads run in the background with live progress."""
import json, threading, time, uuid
from .config import DATA, JOBS

FILE = DATA / "transfers.json"
_lock = threading.RLock()
_state = {"uploads": [], "clips": []}

def _load():
    try: d = json.loads(FILE.read_text("utf-8"))
    except Exception: d = {}
    _state["uploads"] = d.get("uploads", [])
    _state["clips"] = d.get("clips", [])
    for u in _state["uploads"]:           # an upload cannot survive a restart
        if u["state"] in ("queued", "uploading"):
            u.update(state="error", error="Interrupted when Clipsurge restarted. Upload it again.")
_load()

def _save():
    with _lock:
        tmp = FILE.with_suffix(".tmp"); tmp.write_text(json.dumps(_state, indent=1), "utf-8"); tmp.replace(FILE)

def _set(u, **kw):
    with _lock:
        u.update(kw)

def list_uploads():
    with _lock: return [dict(u) for u in reversed(_state["uploads"])]

def start_upload(jid, cid, title, file, privacy, tags, description=None, meta=None):
    from . import youtube, jobs
    path = JOBS / jid / file
    u = {"id": uuid.uuid4().hex[:8], "jid": jid, "cid": cid, "title": title or "Clip", "file": file,
         "size": path.stat().st_size if path.exists() else 0, "privacy": privacy, "state": "queued",
         "progress": 0.0, "url": None, "error": None, "t0": time.time(), "t1": None,
         "tags": list(tags or []), "meta": meta or {}}
    with _lock: _state["uploads"].append(u); _save()
    def run():
        try:
            _set(u, state="uploading", note="Starting")
            def prog(f): _set(u, progress=round(float(f), 4), note="Uploading")
            url = youtube.upload(path, title, description if description is not None else " ".join(tags or []), tags, privacy, prog=prog)
            _set(u, state="done", progress=1.0, url=url, t1=time.time(), note="Done")
            def mark(j):
                for c in j["clips"]:
                    if c["id"] == cid: c["youtube"] = url
            try: jobs.update(jid, mark)
            except Exception: pass
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if "client" in msg.lower() or "token" in msg.lower() or "credentials" in msg.lower():
                msg = "YouTube is not connected. Sign in under Settings > Accounts, then try again."
            _set(u, state="error", error=msg[:300], t1=time.time())
        _save()
    threading.Thread(target=run, daemon=True).start()
    return dict(u)

def clear(uid=None):
    """Remove finished uploads from the list (the videos on YouTube are untouched)."""
    with _lock:
        _state["uploads"] = [u for u in _state["uploads"]
                             if u["state"] in ("queued", "uploading") or (uid is not None and u["id"] != uid)]
        _save()

def log_clip_download(jid, cid, title, kind, size):
    with _lock:
        _state["clips"].append({"id": uuid.uuid4().hex[:8], "jid": jid, "cid": cid, "title": title, "kind": kind,
                                "size": size, "t": time.time()})
        _state["clips"] = _state["clips"][-300:]; _save()

def clips_downloaded():
    with _lock: return list(reversed(_state["clips"]))

def clear_downloads():
    with _lock: _state["clips"] = []; _save()
