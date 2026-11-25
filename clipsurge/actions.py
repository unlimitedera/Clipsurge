# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""SurgeAI actions: understands what the creator asks for in plain words and does it to clips of the open video.
Tags, titles, length, captions, crop, narration, bad language filter, re-render, info, delete. Anything it cannot place is
handed to the model, which may answer in words only."""
import re as _re
from . import jobs, insights

def mmss(s):
    s = int(max(0, s)); return f"{s // 60}:{s % 60:02d}"

LAYOUTS = {"stack": ["webcam", "stack", "face cam", "facecam", "webcam on top"], "game": ["gameplay only", "game only", "gameplay", "center", "centre"],
           "fit": ["whole screen", "full screen", "fit", "blur", "blurred", "letterbox"], "follow": ["follow face", "follow", "face"],
           "speaker": ["speaker", "cut to speaker", "whoever is speaking", "active speaker"], "auto": ["auto", "automatic", "default"]}
STYLES = {"pop": ["pop", "word highlight", "highlight"], "clean": ["clean", "plain", "simple"], "fire": ["fire", "flame", "hot"], "off": ["off", "none", "no captions", "hide", "remove", "disable", "without"]}
POS = {"top": ["top", "upper"], "middle": ["middle", "center", "centre", "mid"], "bottom": ["bottom", "lower", "low"]}

def _num_words(s):
    return {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}.get(s, None)

def _secs(x):
    m = _re.fullmatch(r"(\d+):(\d{2})", x)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else float(x)

def targets(j, s):
    """Clip ids the sentence is about. Returns (ids, error)."""
    ids = {c["id"] for c in j["clips"]}
    if _re.search(r"\b(all|every|each)\b.*\bclips?\b|\ball of (them|the clips)\b|\beverything\b", s, _re.I): return sorted(ids), None
    found = []
    for m in _re.finditer(r"\bclips?\b\s*(?:number|no\.?|id|#)?\s*#?(\d{1,3})((?:\s*(?:,|and|&)\s*#?\d{1,3})*)", s, _re.I):
        for n in [m.group(1)] + _re.findall(r"\d{1,3}", m.group(2) or ""):
            if int(n) in ids and int(n) not in found: found.append(int(n))
        for n in [m.group(1)] + _re.findall(r"\d{1,3}", m.group(2) or ""):
            if int(n) not in ids: return [], f"There is no clip #{n} in this video. The clips here are: {', '.join('#' + str(i) for i in sorted(ids)) or 'none'}."
    if found: return found, None
    return [], None

def _save(jid, cid, fn, render=False):
    def f(j):
        for c in j["clips"]:
            if c["id"] == cid:
                fn(c)
                if render and c.get("approved", True): c["status"] = "queued"
    jobs.update(jid, f)

def _rerender(jid, ids):
    if ids: jobs.rerender(jid, ids)

def _ctx_clip(j, cid): return next((c for c in j["clips"] if c["id"] == cid), None)

def _kw(s, table):
    for k, words in table.items():
        for w in words:
            if _re.search(r"\b" + _re.escape(w) + r"\b", s): return k
    return None

# ------------------------------------------------------------ tags
def _hashtags(text):
    out = []
    for m in _re.finditer(r"#([\w\u0600-\u06ff-]{2,30})", text): out.append(m.group(1))
    return out

def _explicit_tags(s):
    m = _re.search(r"\btags?\b\s*(?:like|:|=|called|named|of)?\s*(.+)$", s, _re.I)
    if not m: return []
    tail = _re.sub(r"\b(to|for|on|in)\b.*\bclips?\b.*$", "", m.group(1), flags=_re.I)
    h = _hashtags(tail)
    if h: return h
    if _re.search(r"\b(you think|that|which|can help|go viral|viral|best|good|trending|popular|relevant|fit|suitable|suggest|recommend)\b", tail, _re.I): return []
    return [w.strip().lstrip("#") for w in _re.split(r"[,;]|\band\b", tail) if 1 < len(w.strip()) < 30][:10]

def _llm_tags(j, c):
    """Ask the model for hashtags that describe THIS clip. Returns [] when the model is missing or refuses."""
    from . import llm
    try:
        p = llm.provider("rating"); mid = llm.model_id("rating")
        if not p or not mid: return []
        txt = ((c.get("text") or "") or "")[:700]
        sys_ = ("You write hashtags for short vertical videos. Give 8 hashtags that truly describe the clip: the game or topic, the kind of moment, the emotion and the format. "
                "Lowercase, no spaces, each starting with #, separated by spaces. Reply with only the hashtags. No duplicates, nothing misleading.")
        r = llm._chat(p, mid, [{"role": "system", "content": sys_}, {"role": "user", "content": f"Video: {j.get('title')}\nProject type: {(j.get('settings') or {}).get('mode')}\nClip title: {c.get('title')}\nClip text: {txt}"}], 120, 0.5)
        r = _re.sub(r"<think>.*?</think>", "", r, flags=_re.S)
        out = []
        for h in _hashtags(r):
            h = h.lower()
            if h not in out and len(h) > 2 and not h.isdigit(): out.append(h)
        return out[:8]
    except Exception: return []

_COMMON = set("this that with from have they their there about would could should which what when where while these those your you are was were been being into than then them some such only very just also more most much many even like over under after before again because really actually there here okay chat come going know think look want need make made take".split())

def _topic_words(j, c, have):
    """Last resort: the most meaningful words of the video title and project, as tags."""
    words = _re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", (j.get("title") or "")) 
    out = []
    for w in words:
        wl = w.lower()
        if wl in _COMMON or wl in insights.STOP or wl in [h.lower() for h in have] or wl in out: continue
        out.append(wl)
    return out[:4]

def do_tags(j, s, ids):
    jid = j["id"]; low = s.lower(); out = []
    rem = _re.search(r"\b(remove|delete|clear|drop|take (?:off|out)|get rid of)\b", low)
    show = _re.search(r"\b(what|which|show|list|see)\b.*\btags?\b|\btags? (are|does|do)\b", low) and not _re.search(r"\b(add|set|put|give|generate)\b", low)
    for cid in ids:
        c = _ctx_clip(j, cid); have = list(c.get("tags") or [])
        if show: out.append(f"Clip **#{cid}** tags: {' '.join(have) or 'none yet'}"); continue
        if rem:
            ex = _explicit_tags(s)
            keep = [] if (not ex or _re.search(r"\b(all|every)\b", low)) else [t for t in have if t.lstrip("#").lower() not in {e.lower() for e in ex}]
            _save(jid, cid, lambda cc, k=keep: cc.__setitem__("tags", k)); out.append(f"Clip **#{cid}**: tags now {' '.join(keep) or 'none'}."); continue
        ex = _explicit_tags(s); src = "you gave me"
        if not ex:
            sug = insights.suggest(jid, cid, wait=True); ex = [x["tag"] for x in sug["tags"]]
            names = {"yours": "your best videos", "trending": "trending videos on this topic", "search": "what people search for", "clip": "the clip itself"}
            used = [names[x] for x in dict.fromkeys(y["src"] for y in sug["tags"]) if x in names]; src = ("from " + ", ".join(used)) if used else "my own ideas"
            if len(ex) < 5:
                got = _llm_tags(j, c)
                if got: ex = ex + [g for g in got if g.lower() not in [e.lower() for e in ex]]; src = (src + " and my model") if src.startswith("from") else "my model, based on what is said in the clip"
            if len(ex) < 3:
                ex += _topic_words(j, c, ex)
        new = []
        for e in ex:
            tag = "#" + _re.sub(r"[^\w\u0600-\u06ff]", "", e.replace(" ", ""))
            if len(tag) > 2 and tag.lower() not in [h.lower() for h in have + new]: new.append(tag)
        new = new[:8]; total = (have + new)[:15]
        _save(jid, cid, lambda cc, t_=total: cc.__setitem__("tags", t_))
        out.append(f"Clip **#{cid}**: added {' '.join(new) or 'nothing new'} ({src}). All tags: {' '.join(total)}")
    return "\n".join(out) + ("" if show else "\n\nThey are saved on the clip and used when you upload it. Only keep ones that really describe the video: misleading tags break platform rules.")

# ------------------------------------------------------------ everything else
def do_title(j, s, ids):
    from . import llm
    lines = []
    for cid in ids:
        c = _ctx_clip(j, cid); old = c.get("title") or ""
        txt = (c.get("text") or "")[:600]
        new = None
        try:
            p = llm.provider("rating"); mid = llm.model_id("rating")
            if p and mid:
                r = llm._chat(p, mid, [{"role": "system", "content": "Write ONE catchy short-video title, at most 8 words, in the same language as the text. Reply with only the title."},
                                       {"role": "user", "content": f"Clip text: {txt}\nCurrent title: {old}"}], 40, 0.7)
                r = _re.sub(r"<think>.*?</think>", "", r, flags=_re.S).strip().split("\n")[0].strip(" \"'*")
                if 3 <= len(r) <= 95 and not _re.match(r"(i'?m sorry|sorry|i can)", r, _re.I): new = r
        except Exception: pass
        if not new: lines.append(f"Clip **#{cid}**: I could not come up with a better title. Tell me one: **rename clip {cid} to ...**"); continue
        _save(jid_of(j), cid, lambda cc, n=new: cc.__setitem__("title", n)); lines.append(f"Clip **#{cid}**: new title \"{new}\" (was \"{old[:50]}\").")
    return "\n".join(lines)

def jid_of(j): return j["id"]

def do_length(j, s, ids):
    jid = j["id"]; dur = float((j.get("info") or {}).get("duration") or 0); out = []; todo = []
    low = _re.sub(r"\bclips?\s*(?:number|no\.?|id|#)?\s*#?\d{1,3}(?:\s*(?:,|and|&)\s*#?\d{1,3})*", " ", s.lower())    # the clip number is not a time
    rng = _re.search(r"(\d{1,3}:\d{2}|\d+(?:\.\d+)?)\s*(?:-|to|until|till)\s*(\d{1,3}:\d{2}|\d+(?:\.\d+)?)", low)
    by = _re.search(r"\bby\s+(\d+(?:\.\d+)?|" + "|".join(["one","two","three","four","five","six","seven","eight","nine","ten","fifteen","twenty","thirty"]) + r")\s*(?:seconds?|secs?|s)\b", low)
    st = _re.search(r"\b(?:start(?:s|ing)?|begin(?:s|ning)?)\s*(?:at|from|to)?\s*(\d{1,3}:\d{2}|\d+(?:\.\d+)?)", low)
    en = _re.search(r"\b(?:end(?:s|ing)?|stop(?:s)?)\s*(?:at|on|to)?\s*(\d{1,3}:\d{2}|\d+(?:\.\d+)?)", low)
    for cid in ids:
        c = _ctx_clip(j, cid); a, b = c["start"], c["end"]
        if rng: a, b = _secs(rng.group(1)), _secs(rng.group(2))
        elif by:
            k = _num_words(by.group(1)) or float(by.group(1))
            if _re.search(r"\b(longer|extend|lengthen|add|more)\b", low): b += k
            elif _re.search(r"\b(shorter|shorten|trim|cut|less|reduce)\b", low): b -= k
            if _re.search(r"\b(at the start|at the beginning|earlier|before|from the start)\b", low): a, b = c["start"] - k, c["end"] if _re.search(r"\b(longer|extend|lengthen)\b", low) else c["end"]
        else:
            if st: a = _secs(st.group(1))
            if en: b = _secs(en.group(1))
        if dur: b = min(b, dur)
        a = max(0.0, a)
        if b - a < 3: out.append(f"Clip **#{cid}**: that would make it shorter than 3 seconds."); continue
        if b - a > 180: out.append(f"Clip **#{cid}**: that is longer than 3 minutes, which is too long for a short."); continue
        _save(jid, cid, lambda cc, a_=a, b_=b: cc.update(start=round(a_, 2), end=round(b_, 2)), render=True); todo.append(cid)
        out.append(f"Clip **#{cid}**: now {mmss(a)} to {mmss(b)} ({int(b - a)} s).")
    _rerender(jid, todo)
    return "\n".join(out) + ("\n\nRe-rendering it now." if todo else "")

def do_captions(j, s, ids):
    jid = j["id"]; low = s.lower(); todo = []; out = []
    style = _kw(low, STYLES); pos = _kw(low, POS) if _re.search(r"\b(at|to|on|in)\s+the\s+(top|middle|bottom)|\b(top|middle|bottom)\b", low) else None
    size = _re.search(r"\b(?:size|font)\b\D{0,12}(\d{2,3})\b", low); big = _re.search(r"\b(bigger|larger|increase)\b", low); small = _re.search(r"\b(smaller|decrease)\b", low)
    per = _re.search(r"\b(\d)\s*words?\b", low); upper = "lowercase" in low or "no caps" in low or "not all caps" in low
    if style == "off" and not _re.search(r"\b(off|none|no captions|hide|remove|disable|without)\b", low): style = None
    for cid in ids:
        c = _ctx_clip(j, cid); ch = []
        def f(cc):
            e = cc.setdefault("edit", {}); cp = e.setdefault("captions", {})
            if style: cp["style"] = style; ch.append(f"style **{style}**")
            if pos: cp["pos"] = pos; ch.append(f"position **{pos}**")
            if size: cp["size"] = int(size.group(1)); ch.append(f"size {size.group(1)}")
            elif big: cp["size"] = min(160, int(cp.get("size") or 84) + 14); ch.append(f"size {cp['size']}")
            elif small: cp["size"] = max(40, int(cp.get("size") or 84) - 14); ch.append(f"size {cp['size']}")
            if per: cp["per"] = max(1, min(6, int(per.group(1)))); ch.append(f"{cp['per']} words per line")
            if upper: cp["upper"] = False; ch.append("normal case")
        _save(jid, cid, f, render=True)
        if not ch: out.append(f"Clip **#{cid}**: tell me what to change, for example **captions to fire**, **captions at the top**, **bigger captions** or **captions off**."); continue
        todo.append(cid); out.append(f"Clip **#{cid}**: captions set to {', '.join(ch)}.")
    _rerender(jid, todo)
    return "\n".join(out) + ("\n\nRe-rendering now." if todo else "")

def do_crop(j, s, ids):
    jid = j["id"]; layout = _kw(s.lower(), LAYOUTS); out = []; todo = []
    if not layout: return "Which crop? Say **stack** (webcam on top), **game** (gameplay only), **fit** (whole screen with blur), **follow** (follow the face), **speaker** (cut to who talks) or **auto**."
    for cid in ids:
        _save(jid, cid, lambda cc: cc.setdefault("edit", {}).__setitem__("layout", layout), render=True); todo.append(cid); out.append(f"Clip **#{cid}**: crop set to **{layout}**.")
    _rerender(jid, todo); return "\n".join(out) + "\n\nRe-rendering now."

def do_flag(j, s, ids, key, on, label):
    jid = j["id"]; todo = []; out = []
    for cid in ids:
        def f(cc):
            e = cc.setdefault("edit", {})
            if key == "narration": e.setdefault("narration", {})["on"] = on
            else: e["censor"] = "on" if on else "off"
        _save(jid, cid, f, render=True); todo.append(cid); out.append(f"Clip **#{cid}**: {label} {'on' if on else 'off'}.")
    _rerender(jid, todo); return "\n".join(out) + "\n\nRe-rendering now."

def do_rerender(j, ids): _rerender(j["id"], ids); [_save(j["id"], i, lambda c: c.__setitem__("status", "queued")) for i in ids]; return "Re-rendering " + ", ".join(f"#{i}" for i in ids) + "."

def do_info(j, ids):
    out = []
    for cid in ids:
        c = _ctx_clip(j, cid); e = c.get("edit") or {}
        out.append(f"Clip **#{cid}** \"{(c.get('title') or '')[:70]}\": {mmss(c['start'])} to {mmss(c['end'])} ({int(c['end'] - c['start'])} s), score {c.get('score')}, status {c.get('status')}, tags {' '.join(c.get('tags') or []) or 'none'}, crop {e.get('layout') or c.get('layout_used') or 'auto'}, captions {(e.get('captions') or {}).get('style') or 'project default'}" + (f", uploaded {c['youtube']}" if c.get("youtube") else ""))
    return "\n".join(out)

HELP = ("Just tell me in plain words. I can do these, on this video:\n\n"
        "- **Find clips:** *which moments did I miss?*, then *clip number 3*, *clip 1 and 4*, *clip all*. Or by words: *clip the part where he says ...*. Or by time: *clip 12:30 to 13:00*.\n"
        "- **Tags:** *for clip 5 add tags that can help it go viral*, *add tags #gaming #funny to clip 5*, *what are the tags of clip 5*, *remove all tags from clip 5*.\n"
        "- **Titles:** *rename clip 5 to My title*, *give clip 5 a better title*.\n"
        "- **Length:** *make clip 5 shorter by 5 seconds*, *make clip 5 longer by 10 seconds*, *trim clip 5 to 0:30-0:50*, *clip 5 starts at 0:12*.\n"
        "- **Captions:** *captions of clip 5 to fire*, *captions at the top*, *bigger captions*, *captions off*.\n"
        "- **Crop:** *set the crop of clip 5 to whole screen* (stack, game, fit, follow, speaker, auto).\n"
        "- **Other:** *turn on narration for clip 5*, *hide the bad language in clip 5*, *re-render clip 5*, *what is clip 5*, *delete clip 5*.\n\n"
        "Say *it* or *that clip* for the clip I just worked on, or *all clips* for every clip. For ideas, tags and score advice just ask me normally.")
HOW = _re.compile(r"\b(how (do|can|to|would|does)|why|explain|tell me how)\b", _re.I)

def handle(j, text, last_id):
    """Returns a reply when the text is a request about existing clips, else None."""
    s = (text or "").strip(); low = s.lower()
    if _re.search(r"\b(what can you do|what do you do|your (commands|abilities|skills)|^help\b|how do i (use|talk to) you|what.{0,20}(ask|tell) you)\b", low) or \
       (HOW.search(s) and _re.search(r"\b(tags?|rename|caption|crop|trim|shorter|longer|delete|title|narrat|layout|clip)\b", low) and not _re.search(r"\bhow (do|can|would|does) (i|we) (get|make) (more|my|good)", low)):
        return HELP
    if not s or HOW.search(s) and not _re.search(r"\bfor clip\b", low): return None
    pron = _re.search(r"\b(it|that|this|them)\b|\bthe (last|new|latest) (clip|one)\b", low)
    verbs = {"tags": r"\b(tags?|hashtags?)\b", "length": r"\b(longer|shorter|extend|lengthen|shorten|trim|cut (?:it|the)|start(?:s|ing)? at|end(?:s|ing)? at|make it (?:\d+|longer|shorter))\b",
             "captions": r"\b(captions?|subtitles?)\b", "crop": r"\b(crop|layout|framing|webcam on top|gameplay only|whole screen|follow (?:the )?face|cut to speaker)\b",
             "title": r"\b(better|new|improve|improved|viral|catchier|different)\b.*\b(title|name)\b|\b(title|name)\b.*\b(better|improve|catchier|viral)\b",
             "narr": r"\b(narrat\w*|voice ?over|read(?:s)? the title)\b", "cens": r"\b(bad language|curse|swear|profanity|censor)\b", "render": r"\b(re-?render|render again|redo|regenerate|re-?make)\b",
             "info": r"\b(info|details|status|show me clip|tell me about clip|what is clip|how long is)\b"}
    hit = [k for k, rx in verbs.items() if _re.search(rx, low)]
    if not hit: return None
    ids, err = targets(j, s)
    if err: return err
    if not ids:
        if pron and last_id and _ctx_clip(j, last_id): ids = [last_id]
        elif len(j["clips"]) == 1: ids = [j["clips"][0]["id"]]
        else:
            return "Which clip? Tell me its number, for example **for clip 19 add tags**. The clips here are: " + ", ".join(f"#{c['id']}" for c in j["clips"]) + "."
    # priority: the thing the sentence is mainly asking for
    k = hit[0] if len(hit) == 1 else next((x for x in ("tags", "title", "captions", "crop", "length", "narr", "cens", "render", "info") if x in hit), hit[0])
    if k == "tags": return do_tags(j, s, ids)
    if k == "title": return do_title(j, s, ids)
    if k == "captions": return do_captions(j, s, ids)
    if k == "crop": return do_crop(j, s, ids)
    if k == "length": return do_length(j, s, ids)
    if k == "narr": return do_flag(j, s, ids, "narration", not _re.search(r"\b(off|no|without|disable|remove|stop)\b", low), "title narration")
    if k == "cens": return do_flag(j, s, ids, "censor", not _re.search(r"\b(off|no|without|disable|remove|stop|show)\b", low), "bad language filter")
    if k == "render": return do_rerender(j, ids)
    return do_info(j, ids)
