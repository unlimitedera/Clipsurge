# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Update checker: compares this install with the main branch on GitHub and can update itself.

Zip installs (made by install.ps1) remember their commit in `.version`. Git clones use `git pull --ff-only`.
Your data, secrets, .venv and tools folders are never touched."""
import hashlib, json, os, py_compile, shutil, subprocess, sys, tempfile, threading, time, urllib.request, zipfile
from pathlib import Path
from .config import ROOT

REPO = "unlimitedera/Clipsurge"
BRANCH = "main"
KEEP = {"data", "secrets", ".venv", "tools", ".git", "_demo", "__pycache__"}
VFILE = ROOT / ".version"
_cache = {"t": 0, "v": None}
_state = {"stage": "idle", "pct": 0, "error": "", "note": ""}
_lock = threading.Lock()

def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Clipsurge-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def _git(*a):
    return subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True, timeout=120,
                          creationflags=0x08000000)

def mode():
    return "git" if (ROOT / ".git").exists() else "zip"

def current():
    """(sha, date) of what is installed right now, or (None, None) when unknown."""
    try:
        if VFILE.exists():
            d = json.loads(VFILE.read_text("utf-8")); return d.get("sha"), d.get("date")
    except Exception: pass
    if mode() == "git":
        try:
            r = _git("log", "-1", "--format=%H|%cI")
            if r.returncode == 0 and "|" in r.stdout: return tuple(r.stdout.strip().split("|", 1))
        except Exception: pass
    return None, None

def check(force=False):
    """Returns what the page needs to show. Cached for 20 minutes; never raises."""
    with _lock:
        if not force and _cache["v"] and time.time() - _cache["t"] < 1200:
            return _cache["v"]
    cur, cdate = current()
    out = {"mode": mode(), "current": (cur or "")[:7], "current_date": cdate, "available": False,
           "latest": "", "latest_date": "", "message": "", "commits": [], "error": ""}
    try:
        L = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"))
        sha = L["sha"]; out.update(latest=sha[:7], full=sha, latest_date=L["commit"]["committer"]["date"],
                                    message=L["commit"]["message"].split("\n")[0])
        if cur and cur != sha:
            try:
                C = json.loads(_get(f"https://api.github.com/repos/{REPO}/compare/{cur}...{sha}"))
                out["available"] = C.get("status") == "ahead"          # "behind"/"diverged" means local work: leave it alone
                out["commits"] = [{"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0],
                                   "date": c["commit"]["committer"]["date"]} for c in reversed(C.get("commits", []))][:30]
                out["count"] = C.get("ahead_by", len(out["commits"]))
            except Exception:
                out["available"] = True                               # our commit is unknown to GitHub: offer the latest
                out["commits"] = [{"sha": sha[:7], "message": out["message"], "date": out["latest_date"]}]
                out["count"] = 1
        elif not cur:
            out["available"] = True; out["unknown_version"] = True
            out["commits"] = [{"sha": sha[:7], "message": out["message"], "date": out["latest_date"]}]; out["count"] = 1
    except Exception as e:
        out["error"] = "Could not reach GitHub" + (" (rate limit, try later)" if "403" in str(e) else "")
    if not out["error"]:
        with _lock: _cache.update(t=time.time(), v=out)
    return out

def status():
    return dict(_state)

def _set(**k): _state.update(k)

def _hash(*names):
    h = hashlib.sha256()
    for n in names:
        p = ROOT / n
        if p.exists(): h.update(p.read_bytes())
    return h.hexdigest()

REQ = ("requirements.txt", "requirements-ocr.txt", "requirements-gpu.txt")

def _pip():
    py = sys.executable
    def run(*a): return subprocess.run([py, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *a],
                                       cwd=str(ROOT), capture_output=True, text=True, creationflags=0x08000000)
    r = run("-r", "requirements.txt")
    if r.returncode: raise RuntimeError("Installing packages failed: " + (r.stderr or r.stdout)[-300:])
    if (ROOT / "requirements-ocr.txt").exists(): run("-r", "requirements-ocr.txt", "--no-deps")
    try:
        if subprocess.run(["nvidia-smi"], capture_output=True, creationflags=0x08000000).returncode == 0 and (ROOT / "requirements-gpu.txt").exists():
            run("-r", "requirements-gpu.txt")
    except Exception: pass

def _apply(sha):
    try:
        before = _hash(*REQ)
        if mode() == "git":
            _set(stage="Downloading changes", pct=20)
            if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
                raise RuntimeError("This copy has local changes. Commit or stash them first, then update.")
            r = _git("pull", "--ff-only", "origin", BRANCH)
            if r.returncode: raise RuntimeError("git pull failed: " + (r.stderr or r.stdout)[-300:])
        else:
            _set(stage="Downloading the update", pct=10)
            tmp = Path(tempfile.mkdtemp(prefix="clipsurge-upd-"))
            try:
                z = tmp / "u.zip"; z.write_bytes(_get(f"https://github.com/{REPO}/archive/{sha}.zip", 180))
                _set(stage="Unpacking", pct=35)
                with zipfile.ZipFile(z) as f: f.extractall(tmp / "x")
                src = next((tmp / "x").iterdir())
                _set(stage="Checking the new files", pct=45)
                for p in src.rglob("*.py"):                         # a broken file must never replace a working install
                    py_compile.compile(str(p), cfile=str(tmp / "chk.pyc"), doraise=True)
                _set(stage="Installing the new files", pct=55)
                for p in src.rglob("*"):
                    rel = p.relative_to(src)
                    if rel.parts[0] in KEEP or p.is_dir(): continue
                    dst = ROOT / rel; dst.parent.mkdir(parents=True, exist_ok=True)
                    for k in range(20):
                        try: shutil.copy2(p, dst); break
                        except PermissionError:
                            if k == 19: raise
                            time.sleep(0.1)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        if _hash(*REQ) != before:
            _set(stage="Updating packages (can take a few minutes)", pct=70); _pip()
        VFILE.write_text(json.dumps({"sha": sha, "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}), "utf-8")
        _cache.update(t=0, v=None)
        _set(stage="restarting", pct=95)
        time.sleep(0.6)
        subprocess.Popen([sys.executable, "-m", "clipsurge.relaunch"], cwd=str(ROOT), close_fds=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000 | 0x00000200)
        time.sleep(0.7); os._exit(0)
    except Exception as e:
        _set(stage="error", error=str(e)[:400], pct=0)

def apply(busy):
    """Starts the update in the background. Refuses while videos are processing (the restart would interrupt them)."""
    if busy: raise RuntimeError(f"{busy} video{'s are' if busy > 1 else ' is'} still processing. Wait for them to finish, then update.")
    if _state["stage"] not in ("idle", "error"): return status()
    v = check(True)
    if v["error"]: raise RuntimeError(v["error"])
    if not v["available"]: raise RuntimeError("Already up to date.")
    _set(stage="Starting", pct=3, error="")
    threading.Thread(target=_apply, args=(v["full"],), daemon=True).start()
    return status()
