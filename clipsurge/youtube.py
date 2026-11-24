# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""YouTube Shorts upload via the official Data API (OAuth, your own Google project).
Put your OAuth client file at secrets/client_secret.json (Desktop app type)."""
from pathlib import Path
from .config import ROOT

SECRETS = ROOT / "secrets"
CLIENT = SECRETS / "client_secret.json"
TOKEN = SECRETS / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def state():
    return {"client_file": CLIENT.exists(), "connected": TOKEN.exists()}

def _creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request()); TOKEN.write_text(c.to_json())
    return c

def connect():
    """Opens the browser once so the user can sign in. Passwords never touch this app."""
    if not CLIENT.exists():
        raise FileNotFoundError(f"Put your Google OAuth client file at {CLIENT}")
    from google_auth_oauthlib.flow import InstalledAppFlow
    c = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES).run_local_server(port=0)
    SECRETS.mkdir(exist_ok=True); TOKEN.write_text(c.to_json())

def upload(path, title, description="", tags=None, privacy="private"):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    yt = build("youtube", "v3", credentials=_creds())
    body = {"snippet": {"title": (title or "Clip")[:95] + " #Shorts",
                        "description": description, "tags": [t.lstrip("#") for t in (tags or [])],
                        "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}"
