# Clipsurge

Any video in, share-ready vertical shorts out. Runs locally on your PC.
Copyright (c) 2026 unlimitedera. All Rights Reserved (see LICENSE).

## Run
Double-click `start.bat` (opens http://127.0.0.1:8420), or:
`.venv\Scripts\python.exe -m clipsurge.server`

## Flow
Get video (yt-dlp) -> Transcribe (faster-whisper, GPU) -> Find moments (audio energy,
speech, keywords, optional local LLM) -> Smart crop (OpenCV face follow or blurred fit)
-> Word-by-word captions -> Loudness normalize -> MP4 1080x1920.

## Local AI (optional)
Start LM Studio's server (127.0.0.1:1234). Clipsurge uses it for titles, hashtags and
better scoring. Without it, scoring still works. Override with CLIPSURGE_LLM.

## YouTube upload
1. Google Cloud console: create a project, enable "YouTube Data API v3".
2. Create OAuth client ID, type Desktop app, download the JSON.
3. Save it as `secrets/client_secret.json`. Click "Upload to YouTube" and sign in once.
Uploads default to private. Unverified Google projects can only post private videos
until the app passes Google's audit.

## Status
- Done: pipeline, dashboard with per-step progress, webcam+gameplay layout, YouTube upload (untested without your credentials)
- Next: scheduler, TikTok and Instagram, MCP wrapper

## Repo map (what is really used)
Used in code: yt-dlp (download, chat replay), OpenCV (faces, webcam detection, crop),
faster-whisper (word timestamps, stands in for whisper-timestamped), ffmpeg-normalize
(-14 LUFS), OpenTimelineIO (.otio + EDL export), RapidOCR (on-screen text, stands in
for PaddleOCR), ASS captions (open in Aegisub), NVENC/ffmpeg encode (stands in for
Shutter Encoder), obs-websocket (record from OBS).
Ideas reimplemented, no code copied (AGPL/unlicensed): gaming-clip (webcam stack),
Stream-clipper (chat spikes), Chopify (scoring), StoryToolkitAI (transcript search).
Not included yet (heavy ML, optional later): BoxMOT, SAM 2, SpeechBrain, Moment-DETR,
Ultimate Vocal Remover, Decord. GUI apps (OpenCut, Aegisub, VideoCaptioner) are
export targets, not dependencies.

## Settings tab
Connect any OpenAI-compatible model or agent (LM Studio, Ollama, llama.cpp, OpenRouter, OpenAI,
or an agent API), choose which one rates moments and which one handles search, set defaults,
toggle features, pick the speech model, encoder, loudness and caption size, and enter OBS and
YouTube options. API keys are stored in data/settings.json (not committed) and shown masked.

## Agent control (MCP)
`python -m clipsurge.mcp_server` exposes create_job, list_jobs, get_job, search_moments,
add_clip, render_pending, upload_to_youtube. The Settings tab shows the config to paste into
an agent's MCP settings. Requires `mcp<2`.

## Projects, goals, editor
- Projects tab: each project has goals ("what to look for", "skip these"), defaults, and many videos.
  Videos come from links, files picked on this PC, uploads, or OBS recordings. Goals boost matching
  moments (word overlap, plus the AI when connected) and label clips with the matched idea.
- Clip editor (Edit on any clip): timing (loudness map, drag handles, word-accurate cuts), crop
  (auto, webcam+gameplay, gameplay, whole screen, follow face, manual box with optional pan),
  captions (style, position, size, color, words per line, fix wording), sound (volume, noise
  reduction, voice effects, bass/treble, music with ducking, mute), look (speed, fades, colour).
