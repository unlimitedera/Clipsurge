# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Browse this PC's folders for video files (local app, read-only listing + thumbnails)."""
import hashlib, os, subprocess
from pathlib import Path
from .config import DATA, FFMPEG

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".flv", ".ts", ".wmv", ".mpg", ".mpeg"}
THUMBS = DATA / "thumbs"
THUMBS.mkdir(parents=True, exist_ok=True)

def roots():
    home = Path.home()
    quick = [("Videos", home / "Videos"), ("Downloads", home / "Downloads"), ("Desktop", home / "Desktop"),
             ("Documents", home / "Documents")]
    drives = [f"{c}:/" for c in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:/")]
    return {"quick": [{"name": n, "path": str(p).replace("\\", "/")} for n, p in quick if p.exists()],
            "drives": [{"name": d, "path": d} for d in drives]}

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

def listdir(path, kind="video"):
    p = Path(path)
    if not p.is_dir():
        raise FileNotFoundError(path)
    dirs, files = [], []
    try:
        with os.scandir(p) as it:
            for e in it:
                try:
                    if e.name.startswith((".", "$")):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        dirs.append({"name": e.name, "path": e.path.replace("\\", "/")})
                    elif Path(e.name).suffix.lower() in {"audio": AUDIO_EXT, "gguf": {".gguf"}, "folder": set()}.get(kind, VIDEO_EXT):
                        st = e.stat()
                        files.append({"name": e.name, "path": e.path.replace("\\", "/"),
                                      "size": st.st_size, "mtime": st.st_mtime})
                except OSError:
                    continue
    except PermissionError:
        pass
    dirs.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: x["name"].lower())
    parent = str(p.parent).replace("\\", "/") if p.parent != p else ""
    return {"path": str(p).replace("\\", "/"), "parent": parent, "dirs": dirs, "files": files}

def thumb(path, at=None):
    """Small JPEG frame of a video (cached). Returns file path or None."""
    p = Path(path)
    if p.suffix.lower() not in VIDEO_EXT or not p.is_file():
        return None
    key = hashlib.sha1(f"{p}|{p.stat().st_mtime}|{at}".encode()).hexdigest()[:16]
    out = THUMBS / f"{key}.jpg"
    if out.exists():
        return out
    for ss in ([at] if at is not None else [8, 2, 0]):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", str(ss), "-i", str(p), "-frames:v", "1",
                        "-vf", "scale=320:-2", "-q:v", "5", str(out)], capture_output=True)
        if out.exists() and out.stat().st_size > 0:
            return out
    return None
