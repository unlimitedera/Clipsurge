# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Rules and risk notes for every platform Clipsurge talks to, and a simple upload counter that warns before a burst of posts.

This is general guidance, not legal advice. Platforms change their rules: the links are the source of truth.
Nothing here is a limit published by a platform unless it says so. The warning thresholds are Clipsurge's own cautious defaults."""
import json, time, threading
from .config import DATA

ACK = DATA / "acknowledged.json"
_lock = threading.Lock()
RULES_VERSION = 1            # bump when the text changes in a way people should read again

PLATFORMS = {
 "youtube": {
  "name": "YouTube", "roles": ["upload", "source"],
  "summary": "Clips you upload go through the official YouTube Data API with your own Google project.",
  "rules": [
   "You must own the content or have permission to post it. Clipping someone else's video without permission can lead to copyright strikes, removed videos and, after repeated strikes, a terminated channel.",
   "Copyright claims can come from music, game audio, movie or TV footage and other people's streams, even in a short clip. 'Fair use' is a legal argument, not a setting: YouTube does not decide it for you, and it does not stop a claim.",
   "YouTube's spam, deceptive practices and scams policy covers repetitive or mass-produced uploads and misleading titles, tags and descriptions. Only use tags that describe the video.",
   "Channels that post lots of near-identical or mass-produced clips can be judged as 'inauthentic' content, which affects monetization and can lead to removal. Make each clip meaningfully different and add your own value.",
   "Downloading videos from YouTube is not allowed by YouTube's Terms of Service except through features YouTube provides. Clipsurge's link download is meant for your own videos or videos you have permission to use.",
   "Using the API means you also agree to the YouTube API Services Terms of Service and Developer Policies, and your Google project is subject to its quota.",
  ],
  "limits": [
   "Default API quota: 100 video uploads per day for each Google project (Google's current published default; it can change).",
   "YouTube does not publish how many automated uploads trigger spam checks. Treat any burst of uploads as a risk.",
   "Uploads from a new or unverified API project are not forced private, but your channel may have its own daily upload limit.",
  ],
  "warn_at": 6, "high_at": 15,
  "links": [
   ["Terms of Service", "https://www.youtube.com/t/terms"],
   ["Community Guidelines", "https://www.youtube.com/howyoutubeworks/policies/community-guidelines/"],
   ["Spam, deceptive practices and scams", "https://support.google.com/youtube/answer/2801973"],
   ["Copyright on YouTube", "https://support.google.com/youtube/answer/2797466"],
   ["Fair use on YouTube", "https://support.google.com/youtube/answer/9783148"],
   ["Monetization policies (inauthentic content)", "https://support.google.com/youtube/answer/1311392"],
   ["API Services Terms of Service", "https://developers.google.com/youtube/terms/api-services-terms-of-service"],
   ["API quota costs", "https://developers.google.com/youtube/v3/determine_quota_cost"]],
 },
 "tiktok": {
  "name": "TikTok", "roles": ["upload", "source"],
  "summary": "Clips are posted with TikTok's official Content Posting API using your own TikTok developer app.",
  "rules": [
   "You must own the content or have permission to post it, including the music and sounds in it. Posts can be removed and accounts restricted or banned after copyright reports.",
   "Posts made through the API must follow TikTok's Community Guidelines and the Content Sharing Guidelines: the person posting must know what is sent and choose the caption and privacy. Do not hide that content is made or edited by an automated tool where TikTok asks for a label.",
   "Do not post spam: repeated identical clips, misleading captions or hashtags unrelated to the video. TikTok can limit reach or ban accounts for this.",
   "Until TikTok audits your app, everything posted through the API is private (visible only to you), only accounts set to private can post, and at most 5 users per day can post through one app. Posts can be made public by you later inside TikTok.",
   "Using the API means you also agree to the TikTok Developer Terms of Service.",
  ],
  "limits": [
   "About 15 posts per day per TikTok account through the API, shared by every app that posts for that account (TikTok's published figure; it varies by account).",
   "6 upload requests per minute per login. Too many posts returns the error 'spam_risk_too_many_posts'.",
   "Videos: MP4, WebM or MOV, up to 4 GB, 360 to 4096 px a side, 23 to 60 fps, up to 10 minutes (your own account limit applies). Captions up to 2,200 characters.",
  ],
  "warn_at": 5, "high_at": 12,
  "links": [
   ["Terms of Service", "https://www.tiktok.com/legal/page/global/terms-of-service/en"],
   ["Community Guidelines", "https://www.tiktok.com/community-guidelines"],
   ["Copyright policy", "https://www.tiktok.com/legal/page/global/copyright-policy/en"],
   ["Developer Terms of Service", "https://www.tiktok.com/legal/tik-tok-developer-terms-of-service"],
   ["Content Sharing Guidelines (limits and audit)", "https://developers.tiktok.com/doc/content-sharing-guidelines"],
   ["TikTok for Developers", "https://developers.tiktok.com/"]],
 },
 "twitch": {
  "name": "Twitch and other streaming sites", "roles": ["source"],
  "summary": "Where you download videos from. Clipsurge uses yt-dlp, which supports many sites.",
  "rules": [
   "A site's Terms of Service usually forbid downloading its videos except with the site's own tools. You are responsible for following them.",
   "A streamer or channel owns what they broadcast. Ask for permission, or check whether they allow clips and reuploads. Many streamers allow clips with credit and some do not.",
   "Game audio, music and other people's content in a stream can lead to copyright claims on your clip even if the streamer allows clipping.",
   "A DMCA notice or Content ID claim can remove a clip or strike your channel, no matter how short the clip is.",
  ],
  "limits": [],
  "warn_at": 0, "high_at": 0,
  "links": [
   ["Twitch Terms of Service", "https://www.twitch.tv/p/legal/terms-of-service/"],
   ["Twitch DMCA guidelines", "https://www.twitch.tv/p/legal/dmca-guidelines/"],
   ["US Copyright Office: DMCA", "https://www.copyright.gov/dmca/"],
   ["US Copyright Office: fair use", "https://www.copyright.gov/fair-use/"]],
 },
}

def _load():
    try: return json.loads(ACK.read_text("utf-8"))
    except Exception: return {}

def acknowledged(platform):
    a = _load().get(platform) or {}
    return a.get("v") == RULES_VERSION

def acknowledge(platform):
    if platform not in PLATFORMS: raise KeyError(platform)
    with _lock:
        d = _load(); d[platform] = {"v": RULES_VERSION, "t": int(time.time())}
        ACK.write_text(json.dumps(d, indent=1), "utf-8")

def recent(platform, hours=24):
    """Posts to this platform in the last N hours (including ones in progress)."""
    from . import transfers
    cut = time.time() - hours * 3600
    return sum(1 for u in transfers.list_uploads()
               if (u.get("platform") or "youtube") == platform and u.get("state") in ("queued", "uploading", "done") and (u.get("t0") or 0) >= cut)

def risk(platform):
    """What to tell the user before posting: level none | notice | warn | high, plus plain messages."""
    P = PLATFORMS.get(platform)
    if not P or "upload" not in P["roles"]: return {"level": "none", "count": 0, "messages": []}
    n = recent(platform); name = P["name"]; msgs = []; level = "none"
    if not acknowledged(platform):
        level = "notice"; msgs.append(f"First time posting to {name}: read the rules below and confirm once.")
    if n >= P["high_at"]:
        level = "high"
        msgs.append(f"You posted {n} clips to {name} in the last 24 hours. That is a lot. "
                    + ("TikTok allows about 15 per account per day through the API and rejects more. " if platform == "tiktok" else
                       "YouTube does not publish what it treats as automated or spam behavior, but bursts like this are the kind of pattern that can trigger spam review, limits or removed videos. ")
                    + "Wait, and post fewer, more distinct clips. If you continue, you do so at your own risk.")
    elif n >= P["warn_at"]:
        level = "warn" if level != "high" else level
        msgs.append(f"You posted {n} clips to {name} in the last 24 hours. "
                    + ("YouTube does not publish limits for automated posting. " if platform == "youtube" else "TikTok limits API posts per account per day. ")
                    + "Many similar clips in a short time can look automated and may lead to limits or removals. Space them out. If you continue, you do so at your own risk.")
    return {"level": level, "count": n, "messages": msgs, "needs_ack": not acknowledged(platform),
            "warn_at": P["warn_at"], "high_at": P["high_at"]}

def public():
    out = {}
    for k, P in PLATFORMS.items():
        out[k] = {**P, "acknowledged": acknowledged(k), "risk": risk(k) if "upload" in P["roles"] else None}
    return {"version": RULES_VERSION, "platforms": out}

def to_markdown():
    md = ["# Platform rules, copyright and risk", "",
          "Clipsurge posts to and downloads from other platforms. Each one has its own rules. This page summarises them, shows the limits Clipsurge knows about, and says when it warns you.", "",
          "> This is general guidance, not legal advice. Platforms change their rules without notice: the links are the source of truth. You are responsible for what you download, clip and post.", "",
          "## The short version", "",
          "- Only clip content you own or have permission to use. Copyright claims and strikes happen even for a few seconds of someone else's video or music.",
          "- Posting many similar clips quickly can look automated. No platform publishes the exact number that triggers a review, so Clipsurge warns early and lets you decide. **If you continue after a warning, you do so at your own risk.**",
          "- Use tags and captions that describe the video. Misleading tags count as spam.",
          "- Your account, your Google project and your TikTok app are yours. Their rules and limits apply to you, not to Clipsurge.", ""]
    for k, P in PLATFORMS.items():
        md += [f"## {P['name']}", "", P["summary"], "", "**Rules to know**", ""] + [f"- {r}" for r in P["rules"]] + [""]
        if P["limits"]: md += ["**Limits**", ""] + [f"- {r}" for r in P["limits"]] + [""]
        if "upload" in P["roles"]:
            md += [f"**When Clipsurge warns you**: after {P['warn_at']} posts to {P['name']} in 24 hours it shows a warning and asks you to confirm. After {P['high_at']} it warns strongly. These two numbers are Clipsurge's own cautious defaults, not limits set by {P['name']}.", ""]
        md += ["**Official pages**", ""] + [f"- [{t}]({u})" for t, u in P["links"]] + [""]
    md += ["## How the warnings work", "",
           "- The first time you post to a platform, Clipsurge shows its rules and asks you to confirm once. It asks again if this page changes in an important way.",
           "- Before every post it counts your posts to that platform in the last 24 hours. At the warning level you must tick *I understand and proceed at my own risk*.",
           "- The counts only include posts made through Clipsurge. Posts you made elsewhere are not counted.",
           "- Warnings are not a guarantee: staying below them does not make a post safe, and going above them does not mean a ban.", ""]
    return "\n".join(md)
