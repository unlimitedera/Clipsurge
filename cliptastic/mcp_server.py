# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""MCP server: lets an agent (Hermes, Claude, etc.) drive Cliptastic.
Run:  .venv\\Scripts\\python.exe -m cliptastic.mcp_server   (Cliptastic web app must be running)"""
import os
import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("CLIPTASTIC_URL", "http://127.0.0.1:8420")
mcp = FastMCP("cliptastic")

def _call(method, path, **kw):
    r = httpx.request(method, BASE + path, timeout=60, **kw)
    r.raise_for_status()
    return r.json()

def _brief(j):
    return {"id": j["id"], "title": j.get("title"), "state": j["state"], "stage": j.get("stage"),
            "progress_in_stage": round(j.get("sp", 0), 2), "note": j.get("note"), "error": j.get("error"),
            "clips": [{"id": c["id"], "score": c["score"], "start": c["start"], "end": c["end"],
                       "title": c["title"], "status": c["status"], "file": c.get("file")} for c in j["clips"]]}

@mcp.tool()
def create_job(source: str, mode: str = "auto", count: int = 5, layout: str = "auto") -> dict:
    """Start clipping a video. source = URL or local file path. mode: auto|gaming|podcast|tutorial.
    layout: auto|stack|game|fit|follow. Returns the job; poll with get_job."""
    return _brief(_call("POST", "/api/jobs", data={"url": source, "mode": mode, "count": count, "layout": layout}))

@mcp.tool()
def list_jobs() -> list:
    """List jobs (id, title, state)."""
    return _call("GET", "/api/jobs")

@mcp.tool()
def get_job(job_id: str) -> dict:
    """Job status with per-step progress and the clips found (score, time range, title, file)."""
    return _brief(_call("GET", f"/api/jobs/{job_id}"))

@mcp.tool()
def search_moments(job_id: str, query: str) -> list:
    """Find moments in a finished job's transcript by describing what you want."""
    return _call("GET", f"/api/jobs/{job_id}/search", params={"q": query})

@mcp.tool()
def add_clip(job_id: str, start: float, end: float, title: str = "Custom clip") -> dict:
    """Add and render a custom clip (seconds in the source video)."""
    return _call("POST", f"/api/jobs/{job_id}/clips", json={"start": start, "end": end, "title": title})

@mcp.tool()
def render_pending(job_id: str) -> dict:
    """Render clips that have not rendered yet or failed."""
    return _call("POST", f"/api/jobs/{job_id}/render")

@mcp.tool()
def upload_to_youtube(job_id: str, clip_id: int, privacy: str = "private") -> dict:
    """Upload a rendered clip to YouTube (needs the one-time Google sign-in done in the app)."""
    return _call("POST", f"/api/jobs/{job_id}/clips/{clip_id}/upload", params={"privacy": privacy})

if __name__ == "__main__":
    mcp.run()
