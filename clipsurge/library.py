# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Explorer-friendly library: data/library/<Project>/<Video> folders that point (directory junctions) at the real
job folders in data/jobs. Nothing is moved or copied, so every other part of the app keeps working. Deleting a link
never deletes the files (os.rmdir on a junction only removes the link)."""
import os, re, subprocess, threading
from .config import DATA, JOBS
from . import projects

LIB = DATA / "library"
_lock = threading.RLock()
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}

def safe(name, fallback="Untitled", limit=60):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(name or "")).strip(" .")
    s = re.sub(r"\s+", " ", s)[:limit].strip(" .")
    return fallback if not s or s.lower() in _RESERVED else s

def _is_link(p):
    try: return bool(os.lstat(p).st_file_attributes & 0x400)      # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError): return False

def _unlink(p):
    try: os.rmdir(p)                      # removes only the junction, never what it points to
    except OSError: pass

def project_dir(pid):
    try: return LIB / safe(projects.get(pid)["name"], "Project")
    except Exception: return None

def sync():
    """Make the library match the projects and videos that exist now. Safe to call often."""
    from . import jobs
    with _lock:
        try:
            LIB.mkdir(parents=True, exist_ok=True)
            want = {}                                  # link path -> target
            names = {}
            for pr in projects.all_projects():
                pn = safe(pr["name"], "Project")
                if pn.lower() in names and names[pn.lower()] != pr["id"]: pn = f"{pn} ({pr['id'][-4:]})"
                names[pn.lower()] = pr["id"]
                for j in jobs.list_jobs():
                    if j.get("project") != pr["id"]: continue
                    t = safe(j.get("title") or j.get("source"), "Video")
                    want[LIB / pn / f"{t} [{j['id'][-4:]}]"] = JOBS / j["id"]
                (LIB / pn).mkdir(exist_ok=True)
            for p in LIB.iterdir():                    # remove stale links and empty project folders
                if not p.is_dir() or _is_link(p): continue
                for c in list(p.iterdir()):
                    if _is_link(c) and (c not in want or not c.exists()):
                        _unlink(c)
                if p.name.lower() not in names and not any(p.iterdir()):
                    try: p.rmdir()
                    except OSError: pass
            for link, target in want.items():
                if link.exists() or _is_link(link) or not target.is_dir(): continue
                subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, creationflags=0x08000000)
        except Exception:
            pass

def sync_async():
    threading.Thread(target=sync, daemon=True).start()
