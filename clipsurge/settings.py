# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""User settings, stored in data/settings.json (never committed)."""
import copy, json, threading
from .config import DATA

FILE = DATA / "settings.json"
_lock = threading.Lock()

DEFAULTS = {
    "defaults": {"mode": "auto", "count": 5, "minlen": 20, "maxlen": 55,
                 "layout": "auto", "captions": "pop"},
    "features": {"llm_rating": True, "ocr": True, "chat_replay": True,
                 "webcam_detect": True, "loudness": True, "native_only": True},
    "memory": {"mode": "auto", "vram_gb": 0, "ram_gb": 0},
    "transcribe": {"model": "auto", "language": "auto", "device": "auto"},
    "video": {"encoder": "auto", "lufs": -14, "caption_size": 84, "max_height": 1080},
    "ai": {
        "providers": [{"id": "lmstudio", "name": "LM Studio (local)", "kind": "lmstudio",
                       "base_url": "http://127.0.0.1:1234/v1", "api_key": "", "model": "",
                       "enabled": True}],
        "roles": {"rating": "", "search": ""},     # "" = first enabled provider
    },
    "narration": {"enabled": False, "voice": "auto", "volume": 1.0, "title_caption": False},
    "youtube": {"privacy": "private"},
    "obs": {"host": "localhost", "port": 4455, "password": ""},
}

def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k == "providers":
            out[k] = v
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out

def get():
    try:
        return _merge(DEFAULTS, json.loads(FILE.read_text("utf-8")))
    except Exception:
        return copy.deepcopy(DEFAULTS)

def save(new):
    cur = get()
    # keep stored secrets when the UI sends the masked placeholder back
    old = {p["id"]: p for p in cur["ai"]["providers"]}
    for p in new.get("ai", {}).get("providers", []):
        if p.get("api_key") == MASK and p["id"] in old:
            p["api_key"] = old[p["id"]]["api_key"]
    if new.get("obs", {}).get("password") == MASK:
        new["obs"]["password"] = cur["obs"]["password"]
    merged = _merge(cur, new)
    with _lock:
        FILE.write_text(json.dumps(merged, indent=1), "utf-8")
    return merged

MASK = "********"

def public():
    s = get()
    for p in s["ai"]["providers"]:
        p["api_key"] = MASK if p.get("api_key") else ""
    if s["obs"]["password"]:
        s["obs"]["password"] = MASK
    return s
