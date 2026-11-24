# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Detached helper: waits for the old server to release the port, then starts a new one."""
import socket, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8420

def port_busy():
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0

if __name__ == "__main__":
    t0 = time.time()
    while port_busy() and time.time() - t0 < 20:
        time.sleep(0.2)
    log = open(ROOT / "data" / "server.log", "ab")
    subprocess.Popen([sys.executable, "-m", "clipsurge.server"], cwd=str(ROOT), stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, creationflags=0x08000000 | 0x00000200, close_fds=True)  # NO_WINDOW | NEW_PROCESS_GROUP
