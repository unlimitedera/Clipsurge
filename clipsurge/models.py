# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Model hub: hardware detection, speech-model catalog, Hugging Face search and downloads,
local GGUF language models run through a managed llama.cpp server, and automatic memory planning."""
import ctypes, json, os, re, shutil, struct, subprocess, threading, time, zipfile
from pathlib import Path
import httpx
from .config import DATA
from . import settings

MODELS = DATA / "models"; LLM_DIR = MODELS / "llm"; RUNTIME = DATA / "runtime" / "llama"
for d in (LLM_DIR, RUNTIME): d.mkdir(parents=True, exist_ok=True)
HF = "https://huggingface.co"
LOCAL_PORT = 8081
LOCAL_ID = "clipsurge-local"
_UA = {"User-Agent": "clipsurge"}

# ============================== hardware ==============================
class _MEM(ctypes.Structure):
    _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ex", ctypes.c_ulonglong)]

def hardware():
    gb = 1024 ** 3
    m = _MEM(); m.l = ctypes.sizeof(_MEM); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    hw = {"ram_total": m.total / gb, "ram_free": m.avail / gb, "cores": os.cpu_count() or 4, "gpus": []}
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,driver_version",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8).stdout
        for line in out.strip().splitlines():
            n, t, u, f, drv = [x.strip() for x in line.split(",")]
            hw["gpus"].append({"name": n, "total": int(t) / 1024, "used": int(u) / 1024, "free": int(f) / 1024, "driver": drv})
    except Exception:
        pass
    g = hw["gpus"][0] if hw["gpus"] else None
    hw["vram_total"] = g["total"] if g else 0.0
    hw["vram_free"] = g["free"] if g else 0.0
    return hw

def _budget(hw):
    """Memory Clipsurge may use right now (GB). Manual limits in Settings are respected."""
    cfg = settings.get().get("memory", {})
    vf = hw["vram_free"]; rf = hw["ram_free"]
    if cfg.get("mode") == "manual":
        vf = min(vf, float(cfg.get("vram_gb") or vf)); rf = min(rf, float(cfg.get("ram_gb") or rf))
    return max(0.0, vf - 0.6), max(0.0, rf * 0.8)       # keep headroom for the system

# ============================== downloads (shared) ==============================
DL = {}          # key -> {kind,name,f,detail,state,error,t0}
_dl_lock = threading.Lock()

def _set(key, **kw):
    with _dl_lock:
        DL.setdefault(key, {"state": "run", "f": 0.0, "detail": "", "error": None, "t0": time.time()}).update(kw)

def downloads():
    with _dl_lock:
        return {k: dict(v) for k, v in DL.items()}

def _stream(url, dest, key, label):
    """Resumable download with progress."""
    dest = Path(dest); part = dest.with_suffix(dest.suffix + ".part")
    pos = part.stat().st_size if part.exists() else 0
    with httpx.stream("GET", url, headers={**_UA, **({"Range": f"bytes={pos}-"} if pos else {})}, follow_redirects=True, timeout=30) as r:
        if r.status_code == 416:
            part.rename(dest); return
        r.raise_for_status()
        total = pos + int(r.headers.get("content-length") or 0)
        t0, got0 = time.time(), pos
        with open(part, "ab" if pos else "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk); pos += len(chunk)
                sp = (pos - got0) / max(0.1, time.time() - t0)
                _set(key, f=pos / total if total else 0.0,
                     detail=f"{pos/1e9:.2f} of {total/1e9:.2f} GB · {sp/1e6:.1f} MB/s" + (f" · {int((total-pos)/max(sp,1))} s left" if total and sp > 0 else ""))
    part.replace(dest)

def _bg(key, kind, name, fn):
    _set(key, kind=kind, name=name, state="run", f=0.0, detail="Starting", error=None, t0=time.time())
    def run():
        try:
            fn(); _set(key, state="done", f=1.0, detail="Installed")
        except Exception as e:
            _set(key, state="error", error=f"{type(e).__name__}: {str(e)[:160]}", detail="Failed")
    threading.Thread(target=run, daemon=True).start()

# ============================== speech models ==============================
SPEECH = [
 # id, repo, size GB, VRAM GB (int8 / fp16), speed 1-5, accuracy 1-5, note
 ("tiny", "Systran/faster-whisper-tiny", 0.08, (0.4, 0.6), 5, 1, "Fastest. Only for quick tests."),
 ("base", "Systran/faster-whisper-base", 0.15, (0.5, 0.8), 5, 2, "Very fast, rough accuracy."),
 ("small", "Systran/faster-whisper-small", 0.48, (0.8, 1.3), 4, 3, "Good for clear English."),
 ("medium", "Systran/faster-whisper-medium", 1.5, (1.6, 2.8), 3, 4, "Solid for most languages."),
 ("distil-large-v3", "Systran/faster-distil-whisper-large-v3", 1.5, (1.6, 2.6), 5, 4, "English only. Fast and accurate."),
 ("large-v3-turbo", "deepdml/faster-whisper-large-v3-turbo-ct2", 1.6, (1.8, 3.2), 4, 4, "Near large-v3 accuracy at about 3x the speed."),
 ("large-v2", "Systran/faster-whisper-large-v2", 3.1, (3.0, 5.0), 2, 5, "Often steadier than v3 on noisy Arabic."),
 ("large-v3", "Systran/faster-whisper-large-v3", 3.1, (3.0, 5.0), 2, 5, "Best accuracy. Needed for dialects like Egyptian Arabic."),
]
_SP = {s[0]: s for s in SPEECH}

def hf_home():
    return Path(os.environ.get("HF_HUB_CACHE") or (Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"))

def _repo_dir(repo): return hf_home() / ("models--" + repo.replace("/", "--"))

def speech_installed(repo):
    for snap in (_repo_dir(repo) / "snapshots").glob("*"):
        if (snap / "model.bin").exists():
            return True
    return False

def speech_repo(name):
    if name in _SP: return _SP[name][1]
    for e in _reg().get("speech", []):
        if e["id"] == name: return e["path"]            # an imported local folder
    return name                                        # custom Hugging Face repo id

def speech_catalog():
    sel = settings.get()["transcribe"]["model"]
    hw = hardware(); vb, _ = _budget(hw)
    out = []
    for i, repo, size, (v8, v16), sp, ac, note in SPEECH:
        key = "speech:" + i
        out.append({"id": i, "repo": repo, "size": size, "vram_int8": v8, "vram_fp16": v16, "speed": sp, "accuracy": ac, "note": note,
                    "installed": speech_installed(repo), "selected": sel == i,
                    "fits": "gpu" if vb >= v8 else ("cpu" if hw["ram_free"] > size * 3 else "no")})
    for e, p, gb in _custom_speech():
        v8 = gb + 0.4; v16 = gb * 1.6 + 0.6
        out.append({"id": e["id"], "repo": e["path"], "size": gb, "vram_int8": v8, "vram_fp16": v16, "speed": 0, "accuracy": 0, "note": "Imported from your PC. Files stay where they are.",
                    "installed": (p / "model.bin").exists(), "selected": sel == e["id"], "custom": True, "path": e["path"],
                    "fits": "gpu" if vb >= v8 else ("cpu" if hw["ram_free"] > gb * 3 else "no")})
    return {"models": out, "selected": sel, "auto_choice": choose_whisper(None)[0]}

def delete_speech(name):
    reg = _reg()
    if any(e["id"] == name for e in reg.get("speech", [])):        # imported: forget it, never delete the user's folder
        reg["speech"] = [e for e in reg["speech"] if e["id"] != name]; _reg_save(reg); return
    shutil.rmtree(_repo_dir(speech_repo(name)), ignore_errors=True)

def download_speech(name):
    repo = speech_repo(name); key = "speech:" + name
    def fn():
        from huggingface_hub import HfApi, snapshot_download
        info = HfApi().model_info(repo, files_metadata=True)
        total = sum((s.size or 0) for s in info.siblings) or 1
        stop = threading.Event()
        def watch():
            t0 = time.time()
            while not stop.wait(0.7):
                got = sum(p.stat().st_size for p in (_repo_dir(repo) / "blobs").glob("*") if p.is_file())
                sp = got / max(1, time.time() - t0)
                _set(key, f=min(.99, got / total), detail=f"{got/1e9:.2f} of {total/1e9:.2f} GB")
        threading.Thread(target=watch, daemon=True).start()
        try: snapshot_download(repo)
        finally: stop.set()
    _bg(key, "speech", name, fn)

def choose_whisper(lang):
    """Best speech model that fits the memory available right now."""
    hw = hardware(); vb, rb = _budget(hw)
    en = lang in ("en", "english")
    order = (["distil-large-v3", "large-v3-turbo", "medium", "small"] if en else ["large-v3", "large-v3-turbo", "medium", "small"])
    for n in order:
        if vb >= _SP[n][3][0]:
            return n, "gpu"
    for n in ["medium", "small", "base"]:
        if rb >= _SP[n][2] * 3:
            return n, "cpu"
    return "tiny", "cpu"

def whisper_plan(name, lang=None):
    """-> dict(model, repo, device, compute_type, cpu_threads, reason). Honors the user's choice; picks the safest precision."""
    ts = settings.get()["transcribe"]
    hw = hardware(); vb, rb = _budget(hw)
    if name in (None, "", "auto"):
        name, _ = choose_whisper(lang)
    sp = _SP.get(name)
    v8, v16 = sp[3] if sp else (3.0, 5.0)
    for e, p_, gb in _custom_speech():
        if e["id"] == name and gb: v8, v16 = gb + 0.4, gb * 1.6 + 0.6
    dev = ts.get("device", "auto")
    threads = max(2, min(hw["cores"], 8))
    if dev != "cpu" and hw["vram_total"] and vb >= v8:
        ct = "float16" if vb >= v16 else "int8_float16"
        return {"model": name, "repo": speech_repo(name), "device": "cuda", "compute_type": ct, "cpu_threads": threads,
                "reason": f"{vb:.1f} GB of video memory free: {ct} on the GPU"}
    return {"model": name, "repo": speech_repo(name), "device": "cpu", "compute_type": "int8", "cpu_threads": threads,
            "reason": f"Not enough free video memory ({vb:.1f} GB, needs {v8:.1f}): running on the CPU with {threads} threads"}

# ============================== Hugging Face search ==============================
CURATED = [
 ("bartowski/Qwen2.5-7B-Instruct-GGUF", "Qwen2.5 7B Instruct", "Strong all-rounder, multilingual"),
 ("bartowski/Qwen2.5-3B-Instruct-GGUF", "Qwen2.5 3B Instruct", "Small and quick, fits almost anywhere"),
 ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama 3.2 3B Instruct", "Light and fast"),
 ("unsloth/gemma-3-4b-it-GGUF", "Gemma 3 4B", "Good multilingual quality for its size"),
 ("bartowski/Mistral-7B-Instruct-v0.3-GGUF", "Mistral 7B Instruct v0.3", "Reliable instruction following"),
 ("bartowski/Qwen2.5-0.5B-Instruct-GGUF", "Qwen2.5 0.5B Instruct", "Tiny test model (under 1 GB)"),
]

def hf_search(q):
    q = (q or "").strip()
    if not q:
        return [{"repo": r, "name": n, "note": note, "downloads": None} for r, n, note in CURATED]
    r = httpx.get(f"{HF}/api/models", params={"search": q, "filter": "gguf", "sort": "downloads", "direction": -1, "limit": 20},
                  headers=_UA, timeout=15)
    r.raise_for_status()
    return [{"repo": m["id"], "name": m["id"].split("/")[-1], "note": m["id"].split("/")[0], "downloads": m.get("downloads")} for m in r.json()]

def hf_files(repo):
    """GGUF files in a repo with size, quant label, and how it would fit right now."""
    r = httpx.get(f"{HF}/api/models/{repo}/tree/main", headers=_UA, timeout=15, params={"recursive": "false"})
    r.raise_for_status()
    hw = hardware(); vb, rb = _budget(hw)
    out = []
    for f in r.json():
        p = f.get("path", "")
        if not p.lower().endswith(".gguf") or "mmproj" in p.lower() or re.search(r"-\d{5}-of-\d{5}", p):
            continue
        size = (f.get("lfs") or {}).get("size") or f.get("size") or 0
        gb = size / 1024 ** 3
        q = re.search(r"(IQ\d_\w+|Q\d_K_\w|Q\d_K|Q\d_\d|Q\d|F16|BF16)", p, re.I)
        fit = "gpu" if gb * 1.25 <= vb else ("part" if gb * 1.1 <= vb + rb and vb > 1 else ("cpu" if gb * 1.2 <= rb else "no"))
        out.append({"file": p, "size": size, "gb": round(gb, 2), "quant": q.group(1).upper() if q else "", "fit": fit})
    out.sort(key=lambda x: x["size"])
    pick = [x for x in out if x["fit"] == "gpu"]
    rec = next((x for x in reversed(pick) if x["quant"].startswith(("Q4_K_M", "Q5_K_M", "Q6_K", "Q8"))), None) or (pick[-1] if pick else None)
    for x in out: x["recommended"] = bool(rec and x["file"] == rec["file"])
    return out

def download_gguf(repo, file):
    dest = LLM_DIR / repo.replace("/", "__") / Path(file).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    key = "gguf:" + repo + "/" + file
    _bg(key, "gguf", Path(file).name, lambda: _stream(f"{HF}/{repo}/resolve/main/{file}", dest, key, file))
    return key

def local_models():
    out = []; seen = set()
    for p in LLM_DIR.rglob("*.gguf"):
        k = str(p).replace("\\", "/"); seen.add(k.lower())
        out.append({"path": k, "name": p.name, "repo": p.parent.name.replace("__", "/"), "size": p.stat().st_size})
    for e in _reg().get("llm", []):                              # models the user imported from anywhere on this PC
        k = e["path"]
        if k.lower() in seen: continue
        seen.add(k.lower()); p = Path(k); ok = p.is_file()
        out.append({"path": k, "name": p.name, "repo": "Imported", "size": p.stat().st_size if ok else 0, "imported": True, "missing": not ok})
    return sorted(out, key=lambda x: x["name"].lower())

def delete_gguf(path):
    k = str(path).replace("\\", "/")
    reg = _reg()
    if any(e["path"].lower() == k.lower() for e in reg.get("llm", [])):          # imported: forget it, never delete the user's file
        reg["llm"] = [e for e in reg["llm"] if e["path"].lower() != k.lower()]; _reg_save(reg)
        if _proc.get("file") and str(_proc["file"]).replace("\\", "/").lower() == k.lower(): stop_local()
        return
    p = Path(path).resolve()
    if LLM_DIR.resolve() in p.parents and p.suffix == ".gguf":
        stop_local(); p.unlink(missing_ok=True)

# ============================== models the user already has ==============================
REGF = DATA / "imported_models.json"

def _reg():
    try: return json.loads(REGF.read_text("utf-8"))
    except Exception: return {"llm": [], "speech": []}

def _reg_save(r): REGF.write_text(json.dumps(r, indent=1), "utf-8")

def _is_main_gguf(name):
    n = name.lower()
    if not n.endswith(".gguf") or "mmproj" in n: return False
    return "-00001-of-" in n or not re.search(r"-\d{5}-of-\d{5}", n)      # split models: only the first part is loaded, it finds the rest

def import_gguf(path):
    """Register a GGUF file that lives anywhere on this PC. The file stays where it is."""
    p = Path(path)
    if not p.is_file() or p.suffix.lower() != ".gguf": raise ValueError("Choose a .gguf model file.")
    if "mmproj" in p.name.lower(): raise ValueError("That is a vision helper file, not a model. Import the main model file instead.")
    try: gguf_info(str(p))
    except Exception: raise ValueError("That file is not a valid GGUF model.")
    k = str(p.resolve()).replace("\\", "/"); reg = _reg()
    if any(e["path"].lower() == k.lower() for e in reg["llm"]) or LLM_DIR.resolve() in p.resolve().parents: return {"path": k, "new": False}
    reg["llm"].append({"path": k, "name": p.name, "added": time.time()}); _reg_save(reg)
    return {"path": k, "new": True}

def scan_models(folder, limit=300):
    """Every GGUF model in a folder and its subfolders."""
    f = Path(folder)
    if not f.is_dir(): raise ValueError("That folder does not exist.")
    found = []
    for p in f.rglob("*.gguf"):
        if _is_main_gguf(p.name): found.append(p)
        if len(found) >= limit: break
    return found

def import_folder(folder):
    added, skipped = [], []
    for p in scan_models(folder):
        try: r = import_gguf(str(p)); (added if r["new"] else skipped).append(p.name)
        except Exception as e: skipped.append(f"{p.name} ({e})")
    return {"added": added, "skipped": skipped}

def suggest_folders():
    home = Path.home(); out = []
    for label, c in (("LM Studio", home / ".lmstudio" / "models"), ("LM Studio", home / ".cache" / "lm-studio" / "models"), ("Jan", home / "jan" / "models"),
                     ("GPT4All", Path(os.environ.get("LOCALAPPDATA", "")) / "nomic.ai" / "GPT4All"), ("Downloads", home / "Downloads")):
        try:
            if c.is_dir():
                n = len(scan_models(c, 60))
                if n: out.append({"name": label, "path": str(c).replace("\\", "/"), "count": n})
        except Exception: pass
    return out

def import_speech(folder):
    """A faster-whisper (CTranslate2) model folder: model.bin plus config.json and a tokenizer."""
    f = Path(folder)
    if not f.is_dir(): raise ValueError("Choose the model's folder.")
    if not (f / "model.bin").exists():
        if (f / "pytorch_model.bin").exists() or list(f.glob("*.safetensors")): raise ValueError("That is a standard Whisper model. Clipsurge needs the faster-whisper (CTranslate2) version, which has a model.bin file.")
        raise ValueError("No model.bin in that folder. Pick the folder of a faster-whisper model.")
    if not (f / "config.json").exists() or not ((f / "tokenizer.json").exists() or (f / "vocabulary.json").exists() or (f / "vocabulary.txt").exists()):
        raise ValueError("The folder is missing config.json or the tokenizer files.")
    reg = _reg(); k = str(f.resolve()).replace("\\", "/"); mid = "custom:" + f.name
    if any(e["path"].lower() == k.lower() for e in reg["speech"]): return {"id": next(e["id"] for e in reg["speech"] if e["path"].lower() == k.lower()), "new": False}
    n = 2; base = mid
    while any(e["id"] == mid for e in reg["speech"]): mid = f"{base}-{n}"; n += 1
    reg["speech"].append({"id": mid, "path": k, "added": time.time()}); _reg_save(reg)
    return {"id": mid, "new": True}

def _custom_speech():
    for e in _reg().get("speech", []):
        p = Path(e["path"]); gb = (p / "model.bin").stat().st_size / 1024 ** 3 if (p / "model.bin").exists() else 0
        yield e, p, gb

# ============================== GGUF header + memory planner ==============================
def gguf_info(path):
    """Reads just the metadata we need (layers, size of the cache per token)."""
    with open(path, "rb") as f:
        buf = f.read(48 * 1024 * 1024)
    if buf[:4] != b"GGUF":
        raise ValueError("not a GGUF file")
    o = 4; ver, nt, nkv = struct.unpack_from("<IQQ", buf, o); o += 20
    sz = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    fmt = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
    def rstr():
        nonlocal o
        n = struct.unpack_from("<Q", buf, o)[0]; o += 8; s = buf[o:o + n].decode("utf-8", "ignore"); o += n; return s
    def rval(t):
        nonlocal o
        if t == 8: return rstr()
        if t == 9:
            et = struct.unpack_from("<I", buf, o)[0]; n = struct.unpack_from("<Q", buf, o + 4)[0]; o += 12
            if et == 8:
                for _ in range(n): rstr()
            else: o += sz[et] * n
            return None
        v = struct.unpack_from("<" + fmt[t], buf, o)[0]; o += sz[t]; return v
    kv = {}
    for _ in range(nkv):
        k = rstr(); t = struct.unpack_from("<I", buf, o)[0]; o += 4; v = rval(t)
        if v is not None: kv[k] = v
    arch = kv.get("general.architecture", "llama")
    g = lambda s, d=0: kv.get(f"{arch}.{s}", d)
    layers = int(g("block_count", 32)); emb = int(g("embedding_length", 4096)); heads = int(g("attention.head_count", 32) or 32)
    kvh = int(g("attention.head_count_kv", heads) or heads)
    kv_per_tok = 2 * layers * kvh * (emb // max(1, heads)) * 2          # fp16 bytes per token
    return {"arch": arch, "layers": layers, "ctx_max": int(g("context_length", 4096)), "kv_per_token": kv_per_tok,
            "name": kv.get("general.name", Path(path).stem)}

def plan_llm(path, want_ctx=8192):
    """Auto memory allocation: how many layers go to the GPU and how much context fits."""
    hw = hardware(); vb, rb = _budget(hw)
    info = gguf_info(path); w = Path(path).stat().st_size / 1024 ** 3
    ctx = min(want_ctx, info["ctx_max"]); L = info["layers"]
    def kvgb(c): return info["kv_per_token"] * c / 1024 ** 3
    notes = []
    while True:
        per = w / L + kvgb(ctx) / L
        ngl = int(max(0, (vb - 0.5) / per)) if hw["vram_total"] else 0
        if ngl >= L: ngl, where = 999, "all"
        elif ngl > 0: where = "partial"
        else: where = "cpu"
        cpu_part = (w + kvgb(ctx)) * (1 if where == "cpu" else max(0, (L - min(ngl, L)) / L))
        if cpu_part <= rb or ctx <= 2048: break
        ctx //= 2; notes.append(f"Context reduced to {ctx} to fit memory")
    ok = cpu_part <= rb
    thr = max(2, min(hw["cores"] - 1, 12))
    desc = {"all": f"Whole model on the GPU ({w:.1f} GB)", "partial": f"{min(ngl,L)} of {L} layers on the GPU, rest on the CPU",
            "cpu": "Runs on the CPU (not enough free video memory)"}[where]
    return {"ngl": ngl, "ctx": ctx, "threads": thr, "layers": L, "weights_gb": round(w, 2), "kv_gb": round(kvgb(ctx), 2),
            "where": where, "ok": ok, "description": desc, "notes": notes + ([] if ok else ["Not enough free memory. Close other apps or pick a smaller model."]),
            "vram_budget": round(vb, 1), "ram_budget": round(rb, 1)}

# ============================== llama.cpp runtime + server ==============================
def runtime_exe():
    for p in RUNTIME.rglob("llama-server.exe"): return p
    return None

def install_runtime():
    key = "runtime:llama"
    def fn():
        r = httpx.get("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10", headers=_UA, timeout=20); r.raise_for_status()
        assets = {}
        for rel in r.json():                      # newest release that actually ships Windows builds
            assets = {a["name"]: a["browser_download_url"] for a in rel["assets"] if "-bin-win-" in a["name"]}
            if assets: break
        gpu = bool(hardware()["gpus"])
        pick = []
        if gpu:
            cu = sorted([n for n in assets if re.search(r"bin-win-cuda-12\.\d-x64\.zip$", n) and n.startswith("llama-")])
            cr = sorted([n for n in assets if re.search(r"cudart.*cuda-12\.\d-x64\.zip$", n)])
            if cu: pick = [cu[-1]] + ([cr[-1]] if cr else [])
        if not pick:
            pick = [n for n in assets if re.search(r"bin-win-(vulkan|cpu)-x64\.zip$", n) and n.startswith("llama-")][:1]
        if not pick: raise RuntimeError("No Windows build found in the latest release")
        for i, n in enumerate(pick):
            z = RUNTIME / n
            _stream(assets[n], z, key, n)
            _set(key, detail=f"Unpacking {n}")
            with zipfile.ZipFile(z) as zf: zf.extractall(RUNTIME)
            z.unlink(missing_ok=True)
    _bg(key, "runtime", "llama.cpp runtime", fn)

_proc = {"p": None, "file": None, "plan": None}

def local_status():
    p = _proc["p"]; running = bool(p and p.poll() is None)
    ready = False
    if running:
        try: ready = httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=1.5).status_code == 200
        except Exception: pass
    return {"runtime": bool(runtime_exe()), "running": running, "ready": ready, "file": _proc["file"], "plan": _proc["plan"],
            "port": LOCAL_PORT, "error": _proc.get("error")}

def stop_local():
    p = _proc["p"]
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(8)
        except Exception: p.kill()
    _proc.update(p=None, file=None, plan=None)

def run_local(path, ctx=8192, ngl=None):
    exe = runtime_exe()
    if not exe: raise RuntimeError("Install the runtime first")
    stop_local()
    plan = plan_llm(path, ctx)
    if ngl is not None: plan["ngl"] = int(ngl)
    if not plan["ok"]: raise RuntimeError(plan["notes"][-1])
    name = Path(path).stem
    cmd = [str(exe), "-m", path, "--host", "127.0.0.1", "--port", str(LOCAL_PORT), "-c", str(plan["ctx"]),
           "-ngl", str(plan["ngl"]), "-t", str(plan["threads"]), "--alias", name, "--no-webui"]
    log = open(DATA / "llama-server.log", "wb")
    _proc.update(p=subprocess.Popen(cmd, cwd=str(exe.parent), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                    creationflags=0x08000000), file=path, plan=plan, error=None)
    cfg = settings.get()["ai"]; provs = [p for p in cfg["providers"] if p["id"] != LOCAL_ID]
    provs.append({"id": LOCAL_ID, "kind": "custom", "name": "Clipsurge local model", "base_url": f"http://127.0.0.1:{LOCAL_PORT}/v1",
                  "api_key": "", "model": name, "enabled": True})
    settings.save({"ai": {"providers": provs, "roles": cfg["roles"]}})
    return plan
