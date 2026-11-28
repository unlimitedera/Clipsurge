# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""What is loaded in memory right now, and offloading it. Clipsurge's own models can always be offloaded. Models inside LM Studio
or Ollama are listed too and offloaded only when you press the button for that one."""
import json, re, shutil, subprocess
from pathlib import Path
import httpx
from . import models, settings, jobs

def _host(p):
    return re.sub(r"/v1/?$", "", (p.get("base_url") or "").rstrip("/"))

def _kind(p):
    u = (p.get("base_url") or "").lower()
    if p.get("kind") == "ollama" or ":11434" in u: return "ollama"
    if p.get("kind") == "lmstudio" or ":1234" in u: return "lmstudio"
    return None

def _gb(n): return round((n or 0) / 1024 ** 3, 1)

def _external(p):
    out = []; k = _kind(p); host = _host(p)
    try:
        if k == "ollama":
            for m in httpx.get(host + "/api/ps", timeout=2).json().get("models", []):
                out.append({"id": f"ext:{p['id']}:{m['name']}", "kind": "external", "name": m["name"], "source": p.get("name") or "Ollama",
                            "detail": f"{_gb(m.get('size_vram') or m.get('size'))} GB in video memory" if m.get("size_vram") else f"{_gb(m.get('size'))} GB", "can_offload": True, "external": True})
        elif k == "lmstudio":
            for m in httpx.get(host + "/api/v0/models", timeout=2).json().get("data", []):
                if m.get("state") == "loaded" and m.get("type") != "embeddings":
                    out.append({"id": f"ext:{p['id']}:{m['id']}", "kind": "external", "name": m["id"], "source": p.get("name") or "LM Studio",
                                "detail": (f"context {m['loaded_context_length']}" if m.get("loaded_context_length") else "loaded"), "can_offload": True, "external": True})
    except Exception: pass
    return out

def listing():
    from . import analyze
    items = []; ls = models.local_status()
    busy = [j for j in jobs.list_jobs() if j["state"] in ("running", "queued")]
    if ls["running"]:
        pl = ls.get("plan") or {}
        items.append({"id": "clipsurge:llm", "kind": "llm", "name": Path(ls["file"] or "").stem or "language model", "source": "Clipsurge local model",
                      "detail": ("Ready" if ls["ready"] else "Loading") + (f" · {pl['description']}" if pl.get("description") else "") + (f" · context {pl['ctx']}" if pl.get("ctx") else ""),
                      "can_offload": True, "external": False})
    sp = getattr(analyze, "ACTIVE", {}).get("speech")
    if sp and busy:
        items.append({"id": "clipsurge:speech", "kind": "speech", "name": sp["name"], "source": "Clipsurge speech recognition", "detail": f"On the {sp['device']}. In use for a video right now and unloaded automatically when the speech step finishes.",
                      "can_offload": False, "external": False})
    for p in settings.get()["ai"]["providers"]:
        if p.get("enabled") and p.get("base_url") and p["id"] != models.LOCAL_ID: items += _external(p)
    return {"items": items, "busy": len(busy)}

def offload(item_id):
    if item_id == "clipsurge:llm":
        was = models.local_status()["running"]; models.stop_local(); return {"offloaded": ["language model"] if was else []}
    if item_id == "all":
        was = models.local_status()["running"]; models.stop_local(); return {"offloaded": ["language model"] if was else []}
    m = re.match(r"ext:([^:]+):(.+)$", item_id or "")
    if not m: raise ValueError("Unknown model")
    p = next((x for x in settings.get()["ai"]["providers"] if x["id"] == m.group(1)), None)
    if not p: raise ValueError("Unknown connection")
    name = m.group(2); k = _kind(p); host = _host(p)
    if k == "ollama":
        r = httpx.post(host + "/api/generate", json={"model": name, "keep_alive": 0}, timeout=15); r.raise_for_status()
        return {"offloaded": [name]}
    if k == "lmstudio":
        try:
            r = httpx.post(host + "/api/v1/models/unload", json={"instance_id": name}, timeout=15)
            if r.status_code < 300: return {"offloaded": [name]}
        except Exception: pass
        exe = shutil.which("lms") or next((str(c) for c in (Path.home() / ".lmstudio" / "bin" / "lms.exe", Path.home() / ".lmstudio" / "bin" / "lms") if c.exists()), None)
        if exe:
            r = subprocess.run([exe, "unload", name], capture_output=True, text=True, timeout=30, creationflags=0x08000000)
            if r.returncode == 0: return {"offloaded": [name]}
            raise RuntimeError((r.stderr or r.stdout or "LM Studio could not unload it").strip()[:200])
        raise RuntimeError(f"This version of LM Studio cannot be told to unload from here. Eject \"{name}\" in the LM Studio window instead.")
    raise ValueError("Cannot offload that")
