# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""SurgeAI facts and housekeeping: answers about the creator's own data come straight from the data (never from a small model's
arithmetic), things he cannot do get an honest answer with the closest alternative, and project / title / upload / schedule
requests and "find the loudest or funniest part" are handled here."""
import datetime as _dt, json, re as _re
from . import jobs, insights

def mm(s):
    s = int(max(0, s)); return f"{s // 60}:{s % 60:02d}"

def line(c):
    d = c["end"] - c["start"]
    return f"**#{c['id']}** \"{(c.get('title') or 'untitled')[:55]}\" ({mm(c['start'])} to {mm(c['end'])}, {int(d)} s, score {c.get('score') or 0}, {len(c.get('tags') or [])} tags, {c.get('status')})"

# ------------------------------------------------------------------ things he cannot do
CANT = [
 (r"\b(split|cut|chop)\b.{0,25}\b(in|into)\s+(half|two|2|parts|pieces|halves)|\bsplit\b.{0,20}\bclip", "I can't split a clip in two. Make two clips from times instead, for example **clip 0:10 to 0:25** and **clip 0:25 to 0:40**, then delete the old one."),
 (r"\b(merge|combine|join|stitch|concatenate)\b", "I can't join clips into one video. Clipsurge makes one clip per moment. To cover a longer moment, make one clip with a wider time range, for example **clip 12:30 to 13:20**."),
 (r"\b(gif|mp3|wav|convert|export (?:as|to|it))\b", "I can't convert clips to other formats. Clips are saved as MP4 files. Open the clip card to download the file."),
 (r"\b(music|volume|louder|quieter|softer|sound effects?|sfx|background (?:sound|audio)|audio level|bass|echo|denoise|noise|mute)\b", "I can't change a clip's audio. The only audio setting is the title narration volume, under Settings > Speech and video > Narration."),
 (r"\b(zoom|effects?|filters?|transitions?|stickers?|emojis?|overlays?|b-?roll|watermark|logo|slow[- ]?mo(?:tion)?|speed (?:it )?up|slow (?:it )?down|intro|outro|color grad\w*|shake|blur the|green ?screen)\b", "I can't add visual effects. I can change the crop (stack, game, fit, follow, speaker), the captions, narration, timing and title."),
 (r"\badd (?:a |an |the )?hook\b|\b(?:hook|intro) (?:to|at) the (?:start|beginning)\b", "I can't add a new hook. I can make the clip start at the strongest line: say **trim clip 3 to 0:35-0:50**, or ask me for the part where he says something with **clip the part where he says ...**."),
 (r"\b(remove|cut|delete|trim)\b.{0,12}\b(silence|silent parts?|pauses|dead air|filler words?|ums?)\b|\bjump ?cuts?\b", "I can't cut silences or filler words out of a clip. I can trim the clip's start and end, for example **trim clip 3 to 0:35-0:50**."),
 (r"\btranslate\b", "I can't translate captions. Captions follow the language that is spoken. You can set the spoken language in Settings > Speech and video."),
 (r"\b(thumbnails?|cover image|poster)\b", "I can't make thumbnails. Clipsurge picks a frame automatically for each clip."),
]
CANT = [(_re.compile(a, _re.I), b) for a, b in CANT]

# ------------------------------------------------------------------ facts from the data
def _clips(j): return j.get("clips") or []

def _ids_in(s):
    ids = []
    for m in _re.finditer(r"\bclips?\s*(?:number|no\.?|#)?\s*#?(\d{1,3})((?:\s*(?:,|and|&)\s*(?:clip\s*)?#?\d{1,3})*)", s, _re.I):
        for n in [m.group(1)] + _re.findall(r"\d{1,3}", m.group(2) or ""):
            if int(n) not in ids: ids.append(int(n))
    for n in _re.findall(r"#(\d{1,3})\b", s):
        if int(n) not in ids: ids.append(int(n))
    return ids

def problems(j, c):
    out = []; d = c["end"] - c["start"]; av = [x.get("score") or 0 for x in _clips(j)]
    if c.get("status") == "error": out.append("it failed to render. Say **re-render clip %d**" % c["id"])
    if not c.get("tags"): out.append("it has no tags. Say **for clip %d add tags**" % c["id"])
    if d > 60: out.append(f"it is {int(d)} s long. Shorts under 60 s usually do better")
    if d < 8: out.append(f"it is only {int(d)} s, which may feel too short")
    if not (c.get("title") or "").strip() or (c.get("title") or "").startswith("Custom clip"): out.append("it has no real title")
    if len(av) > 1 and (c.get("score") or 0) < sorted(av)[len(av) // 3] and (c.get("score") or 0) < 60: out.append(f"its score ({c.get('score') or 0}) is in the lower third of this video")
    if not (c.get("text") or "").strip(): out.append("I have no speech text for it, so my advice on it is limited")
    return out

def facts(j, s, last_id):
    low = s.lower().strip(" ?!."); cl = _clips(j)
    if not _re.match(r"^\W*(?:(?:ok(?:ay)?|so|hey|please|can you|could you|tell me|show me|give me|what|which|how|who|list|sort|compare|is|are|do|does|any|total|average)\b)", low): return None
    if _re.search(r"\b(how (do|can|to|would)|why)\b", low): return None
    ids = _ids_in(s)
    if _re.search(r"\bcompare\b", low) and len(ids) >= 2:
        by = {c["id"]: c for c in cl}; miss = [i for i in ids if i not in by]
        if miss: return f"There is no clip #{miss[0]}. The clips are: {', '.join('#' + str(c['id']) for c in cl)}."
        out = ["Side by side:", ""] + [f"- {line(by[i])}" for i in ids[:4]]
        a, b = by[ids[0]], by[ids[1]]
        out += ["", f"Clip #{a['id'] if (a.get('score') or 0) >= (b.get('score') or 0) else b['id']} has the higher score, and clip #{a['id'] if a['end'] - a['start'] <= b['end'] - b['start'] else b['id']} is the shorter one."]
        return "\n".join(out)
    m = _re.search(r"\b(?:what'?s|what is|whats|any problems?|problems? (?:with|in)|review|check|is)\b.{0,15}\bclip\s*#?(\d{1,3})\b", low) if _re.search(r"\b(wrong|problems?|issues?|review|check|good|bad|weak|improve)\b", low) else None
    if m or (_re.search(r"\b(wrong|problems?|issues?|improve|good|bad|weak)\b", low) and last_id and _re.search(r"\b(it|that|this)\b", low) and not ids):
        cid = int(m.group(1)) if m else last_id
        c = next((x for x in cl if x["id"] == cid), None)
        if not c: return f"There is no clip #{cid}. The clips are: {', '.join('#' + str(x['id']) for x in cl)}."
        pr = problems(j, c)
        return (f"Clip {line(c)}\n\nWhat I can see: " + ("\n- " + "\n- ".join(pr) if pr else "nothing wrong in the data. It has tags, a title, a good length and a decent score.") + "\n\n(I check the numbers and the text, not the picture.)")
    if not cl and _re.search(r"\bclips?\b", low): return "This video has no clips yet."
    if _re.search(r"\b(best|top|highest|strongest|worst|lowest|weakest)\b.{0,25}\b(clip|score)\b|\bwhich clip\b.{0,20}\b(best|highest|lowest|worst)\b", low):
        rev = not _re.search(r"worst|lowest|weakest", low)
        c = sorted(cl, key=lambda x: x.get("score") or 0, reverse=rev)[0]
        return f"The {'highest' if rev else 'lowest'} scoring clip is {line(c)}."
    if _re.search(r"\b(longest|shortest)\b", low):
        c = sorted(cl, key=lambda x: x["end"] - x["start"], reverse="longest" in low)[0]
        return f"The {'longest' if 'longest' in low else 'shortest'} clip is {line(c)}."
    if _re.search(r"\b(total|combined|all together|altogether|sum)\b.{0,25}\b(length|duration|time|long)\b|\bhow long are (?:all )?(?:my |the )?clips\b", low):
        t = sum(c["end"] - c["start"] for c in cl)
        return f"Your {len(cl)} clip{'s' if len(cl) != 1 else ''} add up to **{mm(t)}** ({int(t)} seconds)."
    if _re.search(r"\bhow many clips\b|\bnumber of clips\b", low):
        done = sum(1 for c in cl if c.get("status") == "done")
        return f"This video has **{len(cl)}** clip{'s' if len(cl) != 1 else ''}, {done} finished rendering."
    if _re.search(r"\baverage\b.{0,15}\bscore\b|\bmean score\b", low):
        sc = [c.get("score") or 0 for c in cl]; return f"The average clip score is **{round(sum(sc) / len(sc))}** across {len(sc)} clips."
    if _re.search(r"\b(no|without|missing|untagged)\b.{0,12}\btags?\b|\bwhich clips?\b.{0,20}\b(no tags|untagged)", low):
        nt = [c for c in cl if not c.get("tags")]
        return ("Clips without tags: " + ", ".join(f"#{c['id']}" for c in nt) + ". Say **add tags to all clips** to fill them.") if nt else "Every clip has tags."
    if _re.search(r"\bsort\b|\border\b.{0,15}\bby\b|\brank\b", low) or _re.search(r"\b(list|show)\b.{0,15}\b(all |my |the )?clips\b|\bwhat clips\b", low):
        key = "length" if _re.search(r"length|long|duration", low) else "time" if _re.search(r"time|start|order|position", low) else "score"
        f = {"score": lambda c: -(c.get("score") or 0), "length": lambda c: -(c["end"] - c["start"]), "time": lambda c: c["start"]}[key]
        return f"Your clips by {key}:\n\n" + "\n".join(f"{n}. {line(c)}" for n, c in enumerate(sorted(cl, key=f), 1))
    if _re.search(r"\bhow long is (?:the|this|my) (?:video|source|stream|recording)\b|\b(?:video|source) (?:length|duration)\b", low):
        d = float((j.get("info") or {}).get("duration") or 0)
        return f"The video \"{(j.get('title') or '')[:70]}\" is **{mm(d)}** long." if d else "I do not know the length of this video yet."
    if _re.search(r"\bhow many (?:views|likes|comments)\b|\b(?:views|likes)\b.{0,25}\b(?:upload|video|short|clip)", low) or _re.search(r"\bhow many uploads\b", low):
        return uploads_answer(low, ids)
    return None

def uploads_answer(low, ids):
    t = insights.tracked(); db = insights._load().get("videos", {})
    if _re.search(r"how many uploads", low): return f"You have **{len(t)}** upload{'s' if len(t) != 1 else ''} on record."
    rows = []
    for v, u in t.items():
        d = db.get(v) or {}
        if d.get("views") is not None: rows.append({"u": u, "views": d["views"], "likes": d.get("likes"), "comments": d.get("comments")})
    if not rows: return "I have no view numbers yet. Uploads show up here after they are posted and the numbers are fetched (open the Overview page to refresh)."
    if _re.search(r"\b(best|top|most)\b", low): r = max(rows, key=lambda x: x["views"])
    elif ids: r = next((x for x in rows if x["u"].get("cid") in ids), rows[0])
    else: r = max(rows, key=lambda x: x["u"].get("posted") or 0)
    which = "best" if _re.search(r"\b(best|top|most)\b", low) else "latest"
    return f"Your {which} upload \"{(r['u'].get('title') or '')[:60]}\" has **{r['views']:,} views**, {r['likes'] if r['likes'] is not None else '?'} likes and {r['comments'] if r['comments'] is not None else '?'} comments."

# ------------------------------------------------------------------ projects and video title
def _find_project(name):
    from . import projects
    n = _re.sub(r"[^\w ]", "", (name or "").lower()).strip()
    if not n: return None
    ps = projects.all_projects()
    return next((p for p in ps if _re.sub(r"[^\w ]", "", p["name"].lower()).strip() == n), None) or next((p for p in ps if n in p["name"].lower()), None)

def _tail(s, kw=r"(?:to|as|called|named|:)"):
    m = _re.search(r"\b" + kw + r"\s+[\"\u201c]?(.{2,80}?)[\"\u201d]?\s*$", s.strip(" ."), _re.I)
    return m.group(1).strip(" \"'") if m else None

def meta(scope, sid, j, s):
    from . import projects
    low = s.lower()
    if _re.search(r"\b(create|make|start|add|new)\b.{0,15}\bproject\b", low) and not _re.search(r"\bto (?:the |this |a |another )?project\b", low):
        name = _tail(s, r"(?:called|named|:|titled)") or _tail(s, r"project")
        if not name or len(name) < 2: return "What should the project be called? For example: **create a project called Gaming Highlights**."
        if _find_project(name) and _find_project(name)["name"].lower() == name.lower(): return f"A project called \"{name}\" already exists."
        pr = projects.create(name)
        return f"Created the project **{pr['name']}**. [[nav:#/p/{pr['id']}|Open project]]"
    pid = sid if scope == "project" else (j or {}).get("project")
    if _re.search(r"\b(rename|change|set|call)\b.{0,25}\bproject\b|\bproject\b.{0,15}\b(name|title)\b", low) and pid:
        name = _tail(s)
        if not name: return "What should the project be called? For example: **rename the project to Gaming Highlights**."
        old = projects.get(pid)["name"]; projects.update(pid, {"name": name})
        return f"Renamed the project from \"{old}\" to **{name}**."
    if j and _re.search(r"\b(rename|retitle|change|set|call)\b", low) and _re.search(r"\b(video|source)\b", low) and _re.search(r"\b(title|name|rename|retitle|call)\b", low) and not _re.search(r"\bclip\b|\b(crop|captions?|tags?|language|layout|length|narrat\w*)\b", low):
        name = _tail(s)
        if not name: return "What should the video be called? For example: **rename the video to Night stream highlights**."
        old = j.get("title") or ""; jobs.update(j["id"], lambda x: x.__setitem__("title", name[:120]))
        return f"Renamed the video from \"{old[:60]}\" to **{name[:120]}**. (This is the video's name in your project, not a clip.)"
    if j and _re.search(r"\bmove\b.{0,30}\b(video|this)\b.{0,15}\b(to|into)\b|\bmove (?:this|the) video\b", low):
        name = _tail(s, r"(?:to|into)"); name = _re.sub(r"^(?:the |my |a )?(?:project\s+)?", "", name or "", flags=_re.I).strip()
        pr = _find_project(name) if name else None
        if not pr: return "Which project? Say **move this video to project Gaming Highlights**. Your projects: " + ", ".join(p["name"] for p in projects.all_projects()[:8])
        if pr["id"] == j.get("project"): return f"This video is already in **{pr['name']}**."
        old = projects.get(j.get("project", "inbox")).get("name", "")
        jobs.update(j["id"], lambda x: x.__setitem__("project", pr["id"]))
        try:
            from . import library; library.sync_async()
        except Exception: pass
        return f"Moved this video from \"{old}\" to **{pr['name']}**. Say **move this video to project {old}** to move it back. [[nav:#/p/{pr['id']}|Open project]]"
    return None

# ------------------------------------------------------------------ upload and schedule
LEAD = r"^\W*(?:(?:ok(?:ay)?|so|now|please|pls|can you|could you|would you|and|then|also|just|go ahead and|i want you to|i want to|let'?s|hey)[\s,]+)*"
def _cid(j, s, last_id):
    ids = [i for i in _ids_in(s) if any(c["id"] == i for c in _clips(j))]
    if ids: return ids[0], None
    bad = _ids_in(s)
    if bad: return None, f"There is no clip #{bad[0]}. The clips are: {', '.join('#' + str(c['id']) for c in _clips(j))}."
    if _re.search(r"\b(it|that|this|the last|the new)\b", s, _re.I) and last_id and any(c["id"] == last_id for c in _clips(j)): return last_id, None
    return None, "Which clip? Tell me its number, for example **upload clip 3**."

def upload(j, s, last_id):
    if not _re.match(LEAD + r"(?:upload|post|publish|share|send)\b", s, _re.I) or _re.search(r"\b(when|what time|how)\b", s, _re.I): return None
    if _re.search(r"\b(all|every|each)\b.{0,12}\bclips\b", s, _re.I): return "I upload one clip at a time, so you can check the rules and risk notes for each. Say **upload clip 3**."
    cid, err = _cid(j, s, last_id)
    if err: return err
    c = next(x for x in _clips(j) if x["id"] == cid)
    if c.get("status") != "done": return f"Clip #{cid} has not finished rendering yet. Try again in a moment."
    plat = "tiktok" if _re.search(r"tik ?tok", s, _re.I) else "youtube"
    return f"I do not upload on my own, because each platform needs your confirmation of its rules. I opened the upload step for clip **#{cid}** (\"{(c.get('title') or '')[:50]}\") for you: [[upload:{j['id']}/{cid}/{plat}|Open {'YouTube' if plat == 'youtube' else 'TikTok'} upload]]"

WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
def parse_when(s, now=None):
    now = now or _dt.datetime.now(); low = _re.sub(r"\bclips?\s*(?:number|no\.?|#)?\s*#?\d+", " ", s.lower())
    m = _re.search(r"\bin\s+(\d+|an?|one|two|three|four|five|six|seven|ten)\s*(minutes?|mins?|hours?|hrs?|days?)\b", low)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10}[m.group(1)]
        u = m.group(2)[0]; return now + (_dt.timedelta(minutes=n) if u == "m" else _dt.timedelta(hours=n) if u == "h" else _dt.timedelta(days=n))
    day = None
    d = _re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    if d:
        try: day = _dt.date(int(d.group(1)), int(d.group(2)), int(d.group(3)))
        except ValueError: return None
        low = low.replace(d.group(0), " ")
    elif "tomorrow" in low: day = now.date() + _dt.timedelta(days=1)
    elif "today" in low or "tonight" in low: day = now.date()
    else:
        for i, w in enumerate(WD):
            if w in low:
                k = (i - now.weekday()) % 7 or 7; day = now.date() + _dt.timedelta(days=k); break
    if day is None: return None
    t = _re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b|\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b(\d{1,2}):(\d{2})\b", low)
    h, mi = (20, 0) if "tonight" in low else (18, 0)
    if t:
        g = t.groups()
        if g[0]: h, mi, ap = int(g[0]), int(g[1] or 0), g[2]
        elif g[3]: h, mi, ap = int(g[3]), int(g[4] or 0), g[5]
        else: h, mi, ap = int(g[6]), int(g[7]), None
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
    if h > 23 or mi > 59: return None
    return _dt.datetime.combine(day, _dt.time(h, mi))

def schedule(j, s, last_id, put):
    if not _re.match(LEAD + r"schedule\b", s, _re.I) and not _re.search(r"\bschedule\b.{0,20}\bclip\b", s, _re.I): return None
    cid, err = _cid(j, s, last_id)
    if err: return err
    when = parse_when(s)
    if not when: return "When? For example: **schedule clip 3 for tomorrow at 6pm**, **in 2 hours** or **on friday at 20:00**."
    if when <= _dt.datetime.now(): return f"{when:%A %d %b, %H:%M} is in the past. Pick a later time."
    if _re.search(r"tik ?tok", s, _re.I): return "Scheduled posting works for YouTube only. For TikTok, say **upload clip %d to tiktok** and post it yourself." % cid
    from . import youtube
    if not youtube.state().get("connected"): return "YouTube is not connected, so I can't schedule. [[settings:acct/yt|Connect YouTube]]"
    c = next(x for x in _clips(j) if x["id"] == cid)
    put(sched={"cid": cid, "ts": when.timestamp()})
    return (f"Schedule clip **#{cid}** (\"{(c.get('title') or '')[:50]}\") on YouTube for **{when:%A %d %b at %H:%M}**? It is uploaded automatically at that time as a **private** video, as long as Clipsurge is running. "
            "You stay responsible for what you post and for the platform rules. Say **yes** to schedule or **no** to cancel.")

def schedule_confirm(j, st, put, yes):
    sc = st.get("sched")
    if not sc: return None
    put(sched=None)
    if not yes: return "Okay, I did not schedule anything."
    from . import extras
    extras.sched_add(j["id"], sc["cid"], sc["ts"])
    return f"Scheduled clip #{sc['cid']} for {_dt.datetime.fromtimestamp(sc['ts']):%A %d %b at %H:%M}. Keep Clipsurge running until then. I can't list or cancel schedules yet." 

# ------------------------------------------------------------------ the loudest, funniest, most exciting part (from sound and words, not understanding)
FEEL = _re.compile(r"\b(loudest|funniest|most (?:exciting|intense|hype|epic|funny)|biggest (?:reaction|moment|scream)|laugh\w*|funny|hilarious|screams?|screaming|yells?|yelling|crowd|reaction|hype)\b", _re.I)
LAUGH = _re.compile(r"\b(ha ?ha+|haha+|lol|lmao|laugh\w*|giggl\w*|hehe+|kek)\b", _re.I)

def feel_hits(j, text, n=3):
    import numpy as np
    from . import analyze, assist, agent
    jd = jobs.JOBS / j["id"]
    try: tr = analyze.load_transcript(jd / "transcript.json")
    except Exception: return []
    words = tr.get("words") or []; segs = tr.get("segments") or []
    try: en = np.array(json.loads((jd / "energy.json").read_text("utf-8")), dtype=float)
    except Exception: return []
    if len(en) < 10: return []
    z = (en - en.mean()) / (en.std() + 1e-6); sc = z.copy()
    low = text.lower(); laugh_only = bool(_re.search(r"laugh|funn|hilar", low)); loud_only = "loudest" in low or _re.search(r"scream|yell", low)
    for w in words:
        i = int(w["s"])
        if i >= len(sc): continue
        t = w["w"]
        if LAUGH.search(t): sc[i] += 4 if laugh_only else 2
        elif not loud_only and analyze.HYPE.search(t): sc[i] += 1.5
    L = int(agent.pref_len() or 25); dur = float((j.get("info") or {}).get("duration") or len(en))
    win = np.convolve(sc, np.ones(8) / 8, mode="same")
    clips = [(c["start"], c["end"]) for c in _clips(j)]
    out = []
    for i in np.argsort(-win):
        t0 = float(i)
        if any(abs(t0 - o["at"]) < 25 for o in out): continue
        s0 = max(0.0, t0 - L * 0.4)
        for sg in segs:
            if sg["s"] <= s0 <= sg["e"]: s0 = sg["s"]; break
        e0 = min(dur, s0 + L)
        for sg in segs:
            if sg["e"] >= e0: e0 = min(dur, sg["e"]); break
        if any(min(e0, b) - max(s0, a) > 0.3 * (e0 - s0) for a, b in clips): continue
        txt = " ".join(x["text"] for x in segs if x["s"] >= s0 - .3 and x["e"] <= e0 + .3).strip()
        if laugh_only and not LAUGH.search(txt): continue
        out.append({"s": s0, "e": e0, "at": t0, "txt": txt, "score": float(win[i])})
        if len(out) >= n: break
    return out

def feel(j, sid, s, do_clip):
    from . import assist
    if not FEEL.search(s) or _re.search(r"\b(how (do|can|to)|why)\b", s, _re.I): return None
    want_clip = _re.match(LEAD + r"(?:clip|make|cut|grab|create)\b", s, _re.I) is not None
    find = _re.search(r"\b(find|where|when|show|list|which|locate|what)\b", s, _re.I)
    if not want_clip and not find: return None
    if _re.search(r"\bsays?|said|saying\b", s, _re.I) and not _re.search(r"loud|laugh|funn", s, _re.I): return None
    hits = feel_hits(j, s)
    if not hits and _re.search(r"laugh|funn|hilar", s, _re.I):
        return "I can't hear laughter. I only see it when the transcript has words like \"haha\" or \"lol\", and I found none that are not already clipped. Ask for **the loudest part** instead, which uses volume."
    if not hits: return "I could not find a clear moment like that that is not already clipped. I rank sounds by loudness, so a quiet video gives little to work with."
    note = "I rank moments by how loud they are and by words like \"haha\" or \"no way\". I can't hear humour, so check them before you post."
    assist.LAST[sid] = [{"s": h["s"], "e": h["e"], "txt": h["txt"]} for h in hits]
    if want_clip:
        h = hits[0]
        return do_clip(j, {"range": (h["s"], h["e"]), "note": ""}) + "\n\n" + note
    return "Best matches, not yet clipped:\n\n" + "\n".join(f"{i}. **{mm(h['at'])}**: \"{h['txt'][:130].strip()}\"" for i, h in enumerate(hits, 1)) + "\n\nSay **clip number 1** to make one. " + note

# ------------------------------------------------------------------ entry
def handle(j, sid, s, last_id):
    from . import assist
    st = assist.LAST.st(sid)
    put = lambda **kw: assist.LAST.put(sid, **kw)
    if st.get("sched"):
        r = schedule_confirm(j, st, put, bool(assist.YES.match(s)))
        if assist.YES.match(s) or assist.NO.match(s): return r
    if st.get("sched") and not (assist.YES.match(s) or assist.NO.match(s)): put(sched=None)
    r = meta("video", sid, j, s)
    if r: return r
    if _re.search(r"\b(delete|remove|erase|wipe|get rid of)\b.{0,12}\b(all|every|each|everything)\b", s, _re.I) and _re.search(r"\bclips?\b", s, _re.I):
        return "I do not delete clips in bulk, because it is easy to regret. Delete them one at a time with **delete clip 3** (I ask you to confirm), or use the delete button on a clip card."
    m = _re.match(LEAD + r"(?:open|show|play|view|go to|edit|see|watch)\b.{0,25}?\bclip\s*(?:number|no\.?|#)?\s*#?(\d{1,3})\b", s, _re.I)
    if m:
        cid = int(m.group(1))
        if not any(c["id"] == cid for c in _clips(j)): return f"There is no clip #{cid}. The clips are: {', '.join('#' + str(c['id']) for c in _clips(j))}."
        put(last=cid)
        return f"Here it is: [[nav:#/p/{j.get('project')}/v/{j['id']}?clip={cid}|Open clip #{cid}]]. You can edit its title, timing, crop and captions there, or ask me to do it here."
    asking = _re.match(r"^\W*(?:how|what|why|which|who|give me|write|suggest|tell me|explain|ideas?|any|should|is|are|does|do)\b", s, _re.I)
    for rx, msg in ([] if asking else CANT):
        if rx.search(s) and _re.search(r"\b(clip|video|it|this|that|the)\b", s, _re.I) and not _re.search(r"\b(what|which|why)\b.{0,15}\b(is|are)\b", s, _re.I): return msg
    for fn in (upload, schedule_wrap(put)):
        r = fn(j, s, last_id)
        if r: return r
    r = facts(j, s, last_id)
    if r: return r
    return feel(j, sid, s, assist.do_clip)

def schedule_wrap(put):
    return lambda j, s, last_id: schedule(j, s, last_id, put)
