# Copyright (c) 2026 unlimitedera. All Rights Reserved.
import os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JOBS = DATA / "jobs"
WEB = ROOT / "web"
JOBS.mkdir(parents=True, exist_ok=True)

LLM_URL = os.environ.get("CLIPTASTIC_LLM", "http://127.0.0.1:1234/v1")
WHISPER_MODEL = os.environ.get("CLIPTASTIC_WHISPER", "small")

def _find(name):
    p = shutil.which(name)
    if p:
        return p
    for d in (Path.home() / "AppData/Local/Microsoft/WinGet/Links",):
        c = d / (name + ".exe")
        if c.exists():
            return str(c)
    return name

FFMPEG = _find("ffmpeg")
FFPROBE = _find("ffprobe")

# Make pip-installed CUDA libraries (cublas/cudnn) visible to the GPU speech model.
def _cuda_dlls():
    import site, sys
    bases = [Path(p) for p in site.getsitepackages()] + [Path(sys.prefix) / "Lib/site-packages"]
    for b in bases:
        for d in (b / "nvidia").glob("*/bin") if (b / "nvidia").exists() else []:
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
            try: os.add_dll_directory(str(d))
            except Exception: pass
_cuda_dlls()
