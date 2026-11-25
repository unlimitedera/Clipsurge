# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""YouTube Shorts upload via the official Data API (OAuth, your own Google project).
Put your OAuth client file at secrets/client_secret.json (Desktop app type)."""
from pathlib import Path
from .config import ROOT

import os
SECRETS = (Path(os.environ["CLIPSURGE_DATA"]) / "secrets") if os.environ.get("CLIPSURGE_DATA") else (ROOT / "secrets")
CLIENT = SECRETS / "client_secret.json"
TOKEN = SECRETS / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

DEFAULT = Path(__file__).resolve().parent / "default_client.json"   # optional: a client shipped with the app

def _client_path():
    return CLIENT if CLIENT.exists() else (DEFAULT if DEFAULT.exists() else None)

def state():
    return {"client_file": _client_path() is not None, "connected": TOKEN.exists(),
            "bundled": (not CLIENT.exists()) and DEFAULT.exists()}

def save_client(text=None, client_id=None, client_secret=None):
    """Store the Google OAuth client from the downloaded JSON, or from a pasted client id + secret."""
    import json
    if text and text.strip():
        try: data = json.loads(text)
        except Exception: raise ValueError("That is not a JSON file. Use the file Google lets you download for the OAuth client.")
        kind = "installed" if "installed" in data else ("web" if "web" in data else None)
        if not kind or not data[kind].get("client_id") or not data[kind].get("client_secret"):
            raise ValueError("This file has no client id or secret. Make sure you created an OAuth client of type Desktop app.")
        if kind == "web":
            raise ValueError("This client is the Web type. Create a new OAuth client and choose Desktop app.")
    else:
        cid, sec = (client_id or "").strip(), (client_secret or "").strip()
        if not cid or not sec: raise ValueError("Paste both the client id and the client secret.")
        if not cid.endswith(".apps.googleusercontent.com"): raise ValueError("The client id should end with .apps.googleusercontent.com")
        data = {"installed": {"client_id": cid, "client_secret": sec, "project_id": "clipsurge",
                              "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                              "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                              "redirect_uris": ["http://localhost"]}}
    SECRETS.mkdir(exist_ok=True)
    CLIENT.write_text(json.dumps(data, indent=1), "utf-8")
    TOKEN.unlink(missing_ok=True)       # a new client needs a new sign-in

def disconnect(forget_client=False):
    TOKEN.unlink(missing_ok=True)
    if forget_client: CLIENT.unlink(missing_ok=True)

def _creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request()); TOKEN.write_text(c.to_json())
    return c

def connect():
    """Opens the browser once so the user can sign in. Passwords never touch this app."""
    cp = _client_path()
    if cp is None:
        raise FileNotFoundError("Add your Google client first (step 2).")
    from google_auth_oauthlib.flow import InstalledAppFlow
    c = InstalledAppFlow.from_client_secrets_file(str(cp), SCOPES).run_local_server(
        port=0, timeout_seconds=240, authorization_prompt_message="", success_message="Signed in. You can close this tab and go back to Clipsurge.")
    SECRETS.mkdir(exist_ok=True); TOKEN.write_text(c.to_json())

def upload(path, title, description="", tags=None, privacy="private", prog=None):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    yt = build("youtube", "v3", credentials=_creds())
    body = {"snippet": {"title": (title or "Clip")[:95] + " #Shorts",
                        "description": description, "tags": [t.lstrip("#") for t in (tags or [])],
                        "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), resumable=True, chunksize=1024 * 1024))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st and prog: prog(st.progress())
    return f"https://youtube.com/shorts/{resp['id']}"
