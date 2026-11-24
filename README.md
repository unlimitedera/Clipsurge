# Cliptastic

Any video in, share-ready vertical shorts out. Runs locally on your PC.
Copyright (c) 2026 unlimitedera. All Rights Reserved (see LICENSE).

## Run
Double-click `start.bat` (opens http://127.0.0.1:8420), or:
`.venv\Scripts\python.exe -m cliptastic.server`

## Flow
Get video (yt-dlp) -> Transcribe (faster-whisper, GPU) -> Find moments (audio energy,
speech, keywords, optional local LLM) -> Smart crop (OpenCV face follow or blurred fit)
-> Word-by-word captions -> Loudness normalize -> MP4 1080x1920.

## Local AI (optional)
Start LM Studio's server (127.0.0.1:1234). Cliptastic uses it for titles, hashtags and
better scoring. Without it, scoring still works. Override with CLIPTASTIC_LLM.

## YouTube upload
1. Google Cloud console: create a project, enable "YouTube Data API v3".
2. Create OAuth client ID, type Desktop app, download the JSON.
3. Save it as `secrets/client_secret.json`. Click "Upload to YouTube" and sign in once.
Uploads default to private. Unverified Google projects can only post private videos
until the app passes Google's audit.

## Status
- Done: pipeline, dashboard, YouTube upload (untested without your credentials)
- Next: scheduler, TikTok and Instagram, MCP wrapper
