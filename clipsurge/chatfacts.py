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
    if not _re.match(r"^\W*(?:(?:ok(?:ay)?|so|hey|please|can you|could you|tell me|show me|give me|what|which|how|who|list|sort|compare|is|are|do|does|any|total|average|summari[sz]e|describe|explain)\b)", low): return None
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
    r = transcript_facts(j, s)
    if r: return r
    r = facts(j, s, last_id)
    if r: return r
    return feel(j, sid, s, assist.do_clip)

def schedule_wrap(put):
    return lambda j, s, last_id: schedule(j, s, last_id, put)


# ------------------------------------------------------------------ typos, digits, "the longest clip", "the clip about X"
ARABIC_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
ARABIC_DIGITS.update({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")})
def digits(s): return (s or "").translate(ARABIC_DIGITS)

CMD_WORDS = ["rename", "retitle", "delete", "remove", "shorten", "lengthen", "captions", "caption", "narration", "schedule", "upload", "render", "rerender", "compare", "summarize"]
def _osa(a, b):
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1): d[i][0] = i
    for k in range(len(b) + 1): d[0][k] = k
    for i in range(1, len(a) + 1):
        for k in range(1, len(b) + 1):
            c = 0 if a[i - 1] == b[k - 1] else 1
            d[i][k] = min(d[i - 1][k] + 1, d[i][k - 1] + 1, d[i - 1][k - 1] + c)
            if i > 1 and k > 1 and a[i - 1] == b[k - 2] and a[i - 2] == b[k - 1]: d[i][k] = min(d[i][k], d[i - 2][k - 2] + 1)
    return d[len(a)][len(b)]

def fix_typos(s):
    """Fix misspelled command words, only in the first three words (the command), never in titles."""
    parts = s.split(" ")
    for i in range(min(3, len(parts))):
        w = _re.sub(r"[^a-z]", "", parts[i].lower())
        if len(w) < 5 or w in CMD_WORDS: continue
        best = min(CMD_WORDS, key=lambda c: _osa(w, c))
        if _osa(w, best) <= (1 if len(w) == 5 else 2) and abs(len(w) - len(best)) <= 2: parts[i] = _re.sub(r"[A-Za-z]+", best, parts[i], count=1)
    return " ".join(parts)

ORD = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "sixth": 5, "seventh": 6, "eighth": 7}
_ASKWHICH = _re.compile(r"^\W*(?:which|what)\b.{0,25}\b(best|longest|shortest|worst|highest|lowest|first|last|top|weakest|strongest)\b", _re.I)
_WORDS = set("the a an and or of to in on at is it that this for with as be are was were i you he she we they my your me him her his them so just like um uh oh yeah okay ok then than but if about where says say said saying clip".split())

def resolve_refs(j, s):
    """'the longest clip' -> 'clip 5'. Returns (text, notes, error)."""
    cl = sorted(_clips(j), key=lambda c: c["id"])
    if not cl or _ASKWHICH.match(s): return s, [], None
    notes = []; err = []
    def pick(key):
        if key in ("longest",): return max(cl, key=lambda c: c["end"] - c["start"])
        if key in ("shortest",): return min(cl, key=lambda c: c["end"] - c["start"])
        if key in ("worst", "lowest", "weakest"): return min(cl, key=lambda c: c.get("score") or 0)
        return max(cl, key=lambda c: c.get("score") or 0)
    def sub_ord(m):
        i = ORD[m.group(1).lower()]
        if i >= len(cl): err.append(f"There is no {m.group(1).lower()} clip. This video has {len(cl)} clip{'s' if len(cl) != 1 else ''}."); return m.group(0)
        notes.append(f"the {m.group(1).lower()} clip is #{cl[i]['id']}"); return f"clip {cl[i]['id']}"
    s2 = _re.sub(r"\b(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth)\s+clip\b", sub_ord, s, flags=_re.I)
    def sub_last(m):
        c = max(cl, key=lambda c: c["id"]); notes.append(f"the {m.group(1).lower()} clip is #{c['id']}"); return f"clip {c['id']}"
    s2 = _re.sub(r"\b(?:the\s+)?(last|latest|newest|final|most recent)\s+clip\b", sub_last, s2, flags=_re.I)
    def sub_sup(m):
        c = pick(m.group(1).lower().split("-")[0].split(" ")[0]); notes.append(f"the {m.group(1).lower()} clip is #{c['id']}"); return f"clip {c['id']}"
    s2 = _re.sub(r"\b(?:the\s+)?(longest|shortest|best|top|highest(?:[- ]scor\w+)?|strongest|worst|lowest(?:[- ]scor\w+)?|weakest)(?:\s+scoring)?\s+clip\b", sub_sup, s2, flags=_re.I)
    def sub_with(m):
        c = pick(m.group(1).lower()); notes.append(f"the clip with the {m.group(1).lower()} score is #{c['id']}"); return f"clip {c['id']}"
    s2 = _re.sub(r"\bthe\s+clip\s+with\s+the\s+(best|highest|worst|lowest|top)\s+score\b", sub_with, s2, flags=_re.I)
    def sub_about(m):
        ph = m.group(1).strip(" \"'"); toks = [w for w in _re.findall(r"[a-z0-9']+", ph.lower()) if w not in _WORDS]
        if not toks: err.append("Tell me a few words from the clip, or its number."); return m.group(0)
        sc = []
        for c in cl:
            hay = ((c.get("text") or "") + " " + (c.get("title") or "")).lower()
            sc.append((sum(1 for w in toks if w in hay), c))
        sc.sort(key=lambda x: -x[0])
        need = max(1, (len(toks) + 1) // 2)
        if sc[0][0] < need or (len(sc) > 1 and sc[1][0] == sc[0][0]):
            err.append(f"I could not tell which clip you mean by \"{ph[:60]}\". Use its number instead, for example **rename clip 4 to ...**."); return m.group(0)
        notes.append(f"the clip about \"{ph[:40]}\" is #{sc[0][1]['id']}"); return f"clip {sc[0][1]['id']}"
    s2 = _re.sub(r"\bthe\s+clip\s+(?:about|where\s+(?:\w+\s+)?(?:says?|said|talks? about|mentions?)|that\s+(?:says?|mentions?|talks? about))\s+(.+?)(?=\s+(?:to|and|then|please)\b|[,.?!]|$)", sub_about, s2, flags=_re.I)
    return s2, notes, (err[0] if err else None)

# ------------------------------------------------------------------ what was said, swearing, what a clip is about (from the transcript)
def _tr(j):
    from . import analyze
    try: return analyze.load_transcript(jobs.JOBS / j["id"] / "transcript.json")
    except Exception: return None

def transcript_facts(j, s):
    low = s.lower().strip(" ?!.")
    m = _re.search(r"\b(?:say|said|saying|says|is said|was said)\b.{0,14}\b(?:at|around|near|in)\s+(\d{1,3}:\d{2})\b", low) or _re.search(r"\bwhat'?s\s+(?:said|happening|going on)\s+(?:at|around|near)\s+(\d{1,3}:\d{2})", low)
    if m:
        a, b = m.group(1).split(":"); t0 = int(a) * 60 + int(b); tr = _tr(j)
        if not tr: return "I have no transcript for this video."
        segs = [x for x in tr.get("segments", []) if x["e"] >= t0 - 4 and x["s"] <= t0 + 12]
        if not segs: return f"Nothing is said around {m.group(1)}."
        return f"Around **{m.group(1)}**:\n\n" + "\n".join(f"- {mm(x['s'])}: \"{x['text'].strip()[:200]}\"" for x in segs[:6])
    if _re.search(r"\b(swear\w*|curs\w*|profan\w*|bad language|bad words?|expletives?|cuss\w*)\b", low) and _re.match(r"^\W*(?:is|are|does|do|did|any|how (?:much|many)|are there|is there|check|find|count)\b", low):
        from . import censor
        tr = _tr(j)
        if not tr: return "I have no transcript for this video."
        hits = [w for w in tr.get("words", []) if censor.is_curse(w["w"])]
        if not hits: return "I found **no** curse words in the transcript."
        times = ", ".join(mm(w["s"]) for w in hits[:8])
        return f"I found **{len(hits)}** curse word{'s' if len(hits) != 1 else ''} in the transcript, for example at {times}{'...' if len(hits) > 8 else ''}. Turn on **Hide curse words** under Settings > Clipping > Bad language to star them out of captions. [[settings:clip/censor|Open that setting]]"
    m = _re.search(r"\b(?:what(?:'s| is| does)?|summari[sz]e|describe|explain|read)\b.{0,25}?\bclip\s*#?(\d{1,3})\b", low)
    if m and _re.search(r"\b(about|summari[sz]e|describe|say|says|in|read|explain|is)\b", low) and not _re.search(r"\b(wrong|problem|issue|score|long|length|tags?)\b", low):
        c = next((x for x in _clips(j) if x["id"] == int(m.group(1))), None)
        if not c: return f"There is no clip #{m.group(1)}. The clips are: {', '.join('#' + str(x['id']) for x in _clips(j))}."
        txt = (c.get("text") or "").strip()
        return f"Clip {line(c)}\n\nWhat is said in it:\n\n> {txt[:500] or 'I have no speech text for this clip.'}"
    return None

# ------------------------------------------------------------------ projects and the whole library (data, not guesses)
HELP_PROJECT = ("In a project I can do this:\n\n- **Change every clip at once:** *add tags #gaming to every clip in this project*, *captions fire for all clips*, *set the crop to game for all clips*, *re-render all clips*. *Undo* takes the whole batch back.\n"
    "- **Facts:** *list my videos*, *which video has the most clips*, *show the best clips in this project*, *how many clips do I have*, *what is the average score*.\n"
    "- **Housekeeping:** *rename the project to ...*, *create a project called ...*, *open settings*.\n- **Memory:** *remember that ...*, *what do you remember about me*.\n\nFor edits on single clips (rename, trim, delete) open the video and ask me there. For ideas and advice just ask normally.")
HELP_GENERAL = ("Outside a project I can do this:\n\n- **Facts:** *list my projects*, *list my videos*, *which video has the best clips*, *how many projects do I have*, *show my best clips*.\n"
    "- **Housekeeping:** *create a project called ...*, *open project Gaming*, *open settings*, *open overview*, *open transfers*.\n- **Memory:** *remember that ...*, *what do you remember about me*.\n\nTo change clips, open a project (bulk changes) or a video (everything else) and ask me there. For ideas, tags and advice just ask normally.")

def _vids(pid=None):
    return [x for x in jobs.list_jobs() if pid is None or x.get("project") == pid]

def _avg(cs):
    sc = [c.get("score") or 0 for c in cs]; return round(sum(sc) / len(sc)) if sc else 0

def scope_facts(scope, pid, s):
    from . import projects
    low = s.lower().strip(" ?!."); inproj = scope == "project"
    if _re.search(r"\b(what can you do|what do you do|help|your (?:commands|abilities))\b", low): return HELP_PROJECT if inproj else HELP_GENERAL
    m = _re.match(LEAD + r"open\s+(?:the\s+)?(settings|overview|transfers|projects|home)\b", low)
    if m:
        t = m.group(1); h = {"settings": "#/settings", "overview": "#/overview", "transfers": "#/transfers", "projects": "#/projects", "home": "#/projects"}[t]
        return f"[[nav:{h}|Open {t}]]"
    m = _re.match(LEAD + r"open\s+(?:the\s+)?(?:project\s+)?(.+?)(?:\s+project)?$", low)
    if m and not _re.match(r"(settings|overview|transfers|projects|home|clip|video)", m.group(1)):
        pr = _find_project(m.group(1))
        if pr: return f"[[nav:#/p/{pr['id']}|Open {pr['name']}]]"
    if _re.search(r"\b(delete|remove)\b.{0,12}\bproject\b", low): return "I do not delete projects, because that removes all its videos. Use the delete button on the project card. [[nav:#/projects|Open projects]]"
    if _re.search(r"\b(projects?)\b", low) and _re.match(r"^\W*(?:what|which|list|show|how many|do i|my|tell)\b", low) and not _re.search(r"\b(this project|in this project)\b", low):
        ps = projects.all_projects(); vs = _vids()
        if _re.search(r"how many", low): return f"You have **{len(ps)}** project{'s' if len(ps) != 1 else ''} and {len(vs)} video{'s' if len(vs) != 1 else ''}."
        return "Your projects:\n\n" + "\n".join(f"- **{p['name']}**: {len([v for v in vs if v.get('project') == p['id']])} video(s), {sum(len(v.get('clips') or []) for v in vs if v.get('project') == p['id'])} clips" for p in ps) if ps else "You have no projects yet. Say **create a project called ...**."
    vs = _vids(pid if inproj else None)
    if not vs and _re.match(r"^\W*(?:what|which|list|show|how many)\b", low) and _re.search(r"\b(videos?|clips?)\b", low): return "There are no videos here yet."
    allc = [(v, c) for v in vs for c in (v.get("clips") or [])]
    if _re.search(r"\b(list|show|what)\b.{0,15}\b(videos|my videos|all videos)\b|^\W*(?:list|show)\b.{0,10}\bvideos\b", low):
        return "Videos:\n\n" + "\n".join(f"- **{v.get('title')}**{'' if inproj else ' (' + (projects.get(v.get('project') or 'inbox') or {}).get('name', '') + ')'}: {len(v.get('clips') or [])} clips, average score {_avg(v.get('clips') or [])}, {v.get('state')}" for v in vs)
    if _re.search(r"\bhow many\b.{0,10}\bvideos\b", low): return f"There {'is' if len(vs) == 1 else 'are'} **{len(vs)}** video{'s' if len(vs) != 1 else ''}{' in this project' if inproj else ''}."
    if _re.search(r"\bhow many\b.{0,10}\bclips\b", low): return f"There {'is' if len(allc) == 1 else 'are'} **{len(allc)}** clip{'s' if len(allc) != 1 else ''}{' in this project' if inproj else ''}."
    if _re.search(r"\baverage\b.{0,12}\bscore\b", low): return f"The average clip score is **{_avg([c for _, c in allc])}** across {len(allc)} clips."
    if _re.search(r"\b(most clips)\b", low) and vs:
        v = max(vs, key=lambda v: len(v.get("clips") or [])); return f"**{v.get('title')}** has the most clips: {len(v.get('clips') or [])}."
    if _re.search(r"\bwhich video\b.{0,25}\b(best|highest|top)\b", low) and vs:
        v = max(vs, key=lambda v: _avg(v.get("clips") or [])); return f"**{v.get('title')}** has the highest average clip score: {_avg(v.get('clips') or [])}."
    if _re.search(r"\b(best|top|highest|strongest|worst|lowest|weakest)\b.{0,15}\bclips?\b", low) and allc:
        rev = not _re.search(r"worst|lowest|weakest", low)
        top = sorted(allc, key=lambda x: x[1].get("score") or 0, reverse=rev)[:5]
        return ("The best clips" if rev else "The weakest clips") + (" in this project" if inproj else "") + ":\n\n" + "\n".join(f"{i}. **#{c['id']}** \"{(c.get('title') or '')[:50]}\" (score {c.get('score') or 0}) from {v.get('title')}" for i, (v, c) in enumerate(top, 1))
    if not inproj and _re.match(LEAD + r"(?:turn|set|add|rename|trim|delete|remove|change|make|re-?render|apply)\b", low) and _re.search(r"\b(clips?|narration|captions?|tags?|crop|everything)\b", low):
        return "I change clips from a project or a video chat, because I need to know which clips you mean. Open a project and ask there (for example *add tags #gaming to every clip in this project*), or open a video for single clips. [[nav:#/projects|Open projects]]"
    return None
