# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""TikTok upload through the official Content Posting API (Direct Post) with your own TikTok developer app.
Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
Until TikTok audits your app, every post is private (SELF_ONLY) and only private accounts can post. See platforms.py."""
import hashlib, http.server, json, secrets, threading, time, urllib.parse, webbrowser
from pathlib import Path
import httpx
from .youtube import SECRETS

CLIENT = SECRETS / "tiktok_client.json"
TOKEN = SECRETS / "tiktok_token.json"
API = "https://open.tiktokapis.com"
AUTH = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "user.info.basic,video.publish"
REDIRECT_HELP = "http://127.0.0.1:*/callback/"

def _client():
    try: return json.loads(CLIENT.read_text("utf-8"))
    except Exception: return None

def state():
    c = _client(); t = None
    try: t = json.loads(TOKEN.read_text("utf-8"))
    except Exception: pass
    return {"client_file": bool(c and c.get("client_key") and c.get("client_secret")), "connected": bool(t and t.get("refresh_token")),
            "scope": (t or {}).get("scope", ""), "can_publish": "video.publish" in (t or {}).get("scope", ""),
            "redirect": REDIRECT_HELP, "refresh_expires": (t or {}).get("refresh_expires_at")}

def save_client(client_key, client_secret):
    ck, cs = (client_key or "").strip(), (client_secret or "").strip()
    if not ck or not cs: raise ValueError("Paste both the Client key and the Client secret.")
    SECRETS.mkdir(exist_ok=True); CLIENT.write_text(json.dumps({"client_key": ck, "client_secret": cs}), "utf-8")

def disconnect(forget_client=False):
    TOKEN.unlink(missing_ok=True)
    if forget_client: CLIENT.unlink(missing_ok=True)

def _save_token(d):
    now = time.time()
    d = dict(d); d["expires_at"] = now + int(d.get("expires_in", 86400)) - 120
    d["refresh_expires_at"] = now + int(d.get("refresh_expires_in", 31536000))
    SECRETS.mkdir(exist_ok=True); TOKEN.write_text(json.dumps(d), "utf-8")
    return d

def _token_call(data):
    r = httpx.post(API + "/v2/oauth/token/", data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"}, timeout=30)
    j = r.json()
    if r.status_code != 200 or j.get("error"): raise RuntimeError(f"TikTok sign in failed: {j.get('error_description') or j.get('error') or r.status_code}")
    return j

def connect():
    """Opens the TikTok sign in page once. Uses PKCE and a local loopback address; passwords never touch this app."""
    c = _client()
    if not c: raise FileNotFoundError("Add your TikTok client key and secret first.")
    verifier = secrets.token_urlsafe(48)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()          # TikTok wants lowercase hex SHA-256, not base64url
    csrf = secrets.token_hex(16); got = {}
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if not self.path.startswith("/callback"): self.send_response(404); self.end_headers(); return
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(b"<h3>Signed in. You can close this tab and go back to Clipsurge.</h3>")
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
    redirect = f"http://127.0.0.1:{port}/callback/"
    url = AUTH + "?" + urllib.parse.urlencode({"client_key": c["client_key"], "scope": SCOPES, "response_type": "code", "redirect_uri": redirect,
                                                "state": csrf, "code_challenge": challenge, "code_challenge_method": "S256"})
    srv.timeout = 1; t0 = time.time(); webbrowser.open(url)
    while not got and time.time() - t0 < 240: srv.handle_request()
    srv.server_close()
    if not got: raise TimeoutError("Sign in timed out. Try Connect again.")
    if got.get("error"): raise RuntimeError(got.get("error_description") or got["error"])
    if got.get("state") != csrf: raise RuntimeError("Sign in was rejected (state did not match). Try again.")
    j = _token_call({"client_key": c["client_key"], "client_secret": c["client_secret"], "code": urllib.parse.unquote(got["code"]),
                     "grant_type": "authorization_code", "redirect_uri": redirect, "code_verifier": verifier})
    _save_token(j)

def _access():
    c = _client()
    try: t = json.loads(TOKEN.read_text("utf-8"))
    except Exception: raise RuntimeError("TikTok is not connected. Sign in under Settings > Accounts.")
    if not c: raise RuntimeError("TikTok client key is missing. Add it under Settings > Accounts.")
    if time.time() >= t.get("expires_at", 0):
        t = _save_token(_token_call({"client_key": c["client_key"], "client_secret": c["client_secret"], "grant_type": "refresh_token", "refresh_token": t["refresh_token"]}))
    return t["access_token"]

def _post(path, body, tok):
    r = httpx.post(API + path, json=body, headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8"}, timeout=60)
    j = r.json(); err = j.get("error") or {}
    if err.get("code") not in (None, "ok"): raise RuntimeError(f"TikTok: {err.get('code')}: {err.get('message') or ''}".strip())
    return j.get("data") or {}

def creator_info():
    return _post("/v2/post/publish/creator_info/query/", {}, _access())

PRIV = {"private": "SELF_ONLY", "unlisted": "MUTUAL_FOLLOW_FRIENDS", "public": "PUBLIC_TO_EVERYONE"}

def upload(path, caption, privacy="private", prog=None):
    """Direct Post. Returns a link to the account (TikTok gives no link for private posts). Raises with TikTok's own error text."""
    path = Path(path); size = path.stat().st_size; tok = _access()
    info = creator_info(); opts = info.get("privacy_level_options") or ["SELF_ONLY"]
    want = PRIV.get(privacy, "SELF_ONLY")
    level = want if want in opts else ("SELF_ONLY" if "SELF_ONLY" in opts else opts[0])
    MB = 1024 * 1024
    if size <= 64 * MB: chunk, n = size, 1
    else: chunk = 10 * MB; n = size // chunk                      # the last chunk takes the remainder (up to 128 MB)
    init = _post("/v2/post/publish/video/init/", {
        "post_info": {"title": (caption or "")[:2200], "privacy_level": level, "disable_duet": False, "disable_comment": False,
                      "disable_stitch": False, "video_cover_timestamp_ms": 1000},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": n}}, tok)
    pid, url = init["publish_id"], init["upload_url"]
    with open(path, "rb") as f:
        for i in range(n):
            start = i * chunk; end = size - 1 if i == n - 1 else start + chunk - 1
            f.seek(start); data = f.read(end - start + 1)
            r = httpx.put(url, content=data, timeout=600, headers={"Content-Type": "video/mp4", "Content-Length": str(len(data)),
                                                                   "Content-Range": f"bytes {start}-{end}/{size}"})
            if r.status_code not in (200, 201, 206): raise RuntimeError(f"TikTok upload failed ({r.status_code}): {r.text[:160]}")
            if prog: prog(0.9 * (i + 1) / n)
    for _ in range(100):                                          # wait for TikTok to process it (up to ~5 minutes)
        time.sleep(3)
        d = _post("/v2/post/publish/status/fetch/", {"publish_id": pid}, tok); s = d.get("status")
        if s == "PUBLISH_COMPLETE":
            ids = d.get("publicaly_available_post_id") or d.get("publicly_available_post_id") or []
            if prog: prog(1.0)
            return f"https://www.tiktok.com/video/{ids[0]}" if ids else "https://www.tiktok.com/"
        if s == "FAILED": raise RuntimeError("TikTok could not publish it: " + str(d.get("fail_reason") or "unknown reason"))
        if prog: prog(min(0.97, 0.9 + 0.001 * _))
    raise RuntimeError("TikTok is still processing the video. Check your TikTok app in a few minutes.")
