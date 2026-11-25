# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Chat with your AI model about a project or a video. Builds a compact, honest briefing from what Clipsurge knows
(goals, clips, scores, transcript, your upload results) so the model can suggest ideas, titles, tags and improvements."""
import json, re, time
from . import jobs, projects, insights, settings

def _clip_line(c, full=False):
    t = _clean((c.get("text") or "").replace("\n", " "))
    s = f"#{c['id']} \"{_clean((c.get('title') or '')[:80])}\" score {c.get('score')} {int(c.get('end', 0) - c.get('start', 0))}s"
    if c.get("idea"): s += f" (matches: {c['idea'][:50]})"
    if c.get("tags"): s += " tags " + " ".join(c["tags"][:6])
    return s + (f"\n   says: {t[:500 if full else 160]}" if t else "")

def _perf_block(ids=None):
    try: a = insights.analyse()
    except Exception: return ""
    out = []
    if a.get("measured"):
        out.append(f"Upload results so far ({a['measured']} clips with numbers, signal: {a.get('confidence')}):")
        for r in sorted([v for v in a["videos"] if v.get("views") is not None], key=lambda r: -(r.get("perf") or 0))[:6]:
            out.append(f"- \"{(r.get('title') or '')[:60]}\" {r['views']} views, {r['likes']} likes, {r['comments']} comments, {r['feat'].get('length','')}")
        for i in a["insights"][:5]: out.append("Pattern: " + i["text"] + f" ({i['diff']:+d} points, {i['n']} clips)")
        if a["reco"]: out.append("Their best clips: " + json.dumps(a["reco"]))
    return "\n".join(out)

def _trend_block(topic):
    try:
        t = insights.trending(topic, wait=False)
        tags = [x["tag"] for x in t.get("tags", [])[:15]]
        rel = t.get("related", [])[:6]
        return (f"Trending tags on this topic (used by 2+ channels): {', '.join(tags)}\n" if tags else "") + (f"People also search: {', '.join(rel)}\n" if rel else "")
    except Exception: return ""

def _clean(text):
    """Curse words become [expletive] in what the model reads (stars would be copied around and break formatting)."""
    from . import censor
    ex = censor._extra()
    return " ".join("[expletive]" if censor.is_curse(w, ex) else w for w in (text or "").split(" "))

def _mmss(s):
    s = int(max(0, s)); return f"{s // 60}:{s % 60:02d}"

def _missed(j):
    """(clips, picked candidates, segments) for a video, or None without a transcript."""
    import numpy as np
    from . import analyze
    jd = jobs.JOBS / j["id"]
    try: tr = analyze.load_transcript(jd / "transcript.json")
    except Exception: return None
    segs = tr.get("segments") or []
    if not segs: return None
    try: en = np.array(json.loads((jd / "energy.json").read_text("utf-8")), dtype=float)
    except Exception: en = np.zeros(int(segs[-1]["e"]) + 2)
    z = (en - en.mean()) / (en.std() + 1e-6) if len(en) > 1 else en
    st = j.get("settings") or {}
    L = max(15, min(45, int(((st.get("minlen") or 20) + (st.get("maxlen") or 55)) / 2)))
    clips = [(c.get("start", 0), c.get("end", 0)) for c in (j.get("clips") or [])]
    cands = []
    for sg in segs:
        s = sg["s"]; e = min(s + L, segs[-1]["e"])
        if e - s < 8: continue
        txt = " ".join(x["text"] for x in segs if x["s"] >= s - 0.01 and x["e"] <= e + 0.5).strip()
        if len(txt.split()) < 6: continue
        zz = z[int(s):int(e) + 1] if len(z) else []
        pk = float(max(zz)) if len(zz) else 0.0; mn = float(np.mean(zz)) if len(zz) else 0.0
        kw = min(1.0, len(analyze.HYPE.findall(txt)) / 3); q = 0.4 if "?" in txt[:80] or analyze.HOOK.search(txt[:60]) else 0.0
        over = max((max(0, min(e, b) - max(s, a)) / (e - s) for a, b in clips), default=0)
        if over > 0.3: continue
        cands.append({"s": s, "e": e, "txt": txt, "pk": pk, "mn": mn, "score": pk * 0.45 + mn * 0.3 + kw * 1.2 + q})
    picked = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if all(c["e"] <= p["s"] - 4 or c["s"] >= p["e"] + 4 for p in picked): picked.append(c)
        if len(picked) >= 8: break
    return clips, sorted(picked, key=lambda c: -c["score"]), segs

from .config import DATA
_STATE = DATA / "chat_state.json"

class _Mem(dict):
    """Per video memory that survives restarts: the list SurgeAI last showed, the clip he last touched, a pending delete, and what he did."""
    def _all(self):
        try: return json.loads(_STATE.read_text("utf-8"))
        except Exception: return {}
    def get(self, jid, default=None): return self._all().get(jid, {}).get("list", default)
    def __getitem__(self, jid): return self._all().get(jid, {}).get("list")
    def __setitem__(self, jid, lst): self.put(jid, list=lst)
    def put(self, jid, **kw):
        d = self._all(); d.setdefault(jid, {}).update(kw)
        try: _STATE.write_text(json.dumps(d, indent=1), "utf-8")
        except Exception: pass
    def st(self, jid): return self._all().get(jid, {})
    def log(self, jid, line):
        d = self._all(); a = d.setdefault(jid, {}).setdefault("actions", []); a.append(line); d[jid]["actions"] = a[-12:]
        try: _STATE.write_text(json.dumps(d, indent=1), "utf-8")
        except Exception: pass
LAST = _Mem()

def missed_answer(j):
    """A plain, always-correct answer to 'did I miss moments?', written from the data (no model needed)."""
    m = _missed(j)
    if not m: return "I can't see a transcript for this video yet. Wait until step 2 (Transcribe) has finished, then ask again."
    clips, picked, segs = m
    if not picked:
        return "Good news: I can't find loud or exciting parts that are not already covered by your clips. Everything that stands out is already clipped."
    LAST[j["id"]] = [{"s": c["s"], "e": c["e"], "txt": c["txt"]} for c in picked]
    out = ["Here are the best moments you haven't clipped yet. I found them from how loud they are, excited words and hooks:", ""]
    for k, c in enumerate(picked, 1):
        out.append(f"{k}. **{_mmss(c['s'])} to {_mmss(c['e'])}**: \"{c['txt'][:220].strip()}\"" + (f" (loud: {c['pk']:+.1f} above average)" if c["pk"] >= 1.5 else ""))
    out += ["", "Tell me which to clip, for example **\"clip number 3\"**, **\"clip 1 and 4\"** or **\"clip all\"**, and I will make them. Loud does not always mean good, so watch each one after."]
    return "\n".join(out)

import re as _re
REFUSAL = _re.compile(r"^\W*(i['\u2019]?m sorry|sorry|i can(?:['\u2019]?t|not)|i am unable|i['\u2019]?m unable|i won['\u2019]?t|as an ai)", _re.I)
MISSED = _re.compile(r"\b(miss(ed|ing)?|overlook(ed)?|left out|unclipped|not clipped|what else|other moments|more moments|good parts)\b", _re.I)
NUDGE = ("\n\nIMPORTANT: everything above is the creator's own footage and notes. Answer the creator's question helpfully and directly using the briefing. "
         "Do not refuse, do not apologise. If something is not in the briefing, say exactly what is missing.")

ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8,
       "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
PHRASEQ = _re.compile(r"\b(when|where|what time|at what (time|point)|which part)\b", _re.I)
HOWQ = _re.compile(r"\b(how (do|can|to|would)|what (does|is|do)|why|explain|tell me how)\b", _re.I)
TIME = r"(\d{1,3}):(\d{2})"

def _secs(m, s): return int(m) * 60 + int(s)

def parse_clip_command(text, n_list):
    """Returns None (not a command) or a dict: {"nums": [..]} to pick from the list, or {"range": (s, e)} for typed times."""
    s = (text or "").lower().strip()
    if HOWQ.search(s) or not _re.search(r"\b(clip|add|make|cut|grab|create|render|save)\b", s): return None
    ph = phrase_of(text)
    if ph and not _re.search(TIME, s): return {"phrase": ph}
    rng = _re.search(TIME + r"\s*(?:-|to|until|till|through|and)\s*" + TIME, s)
    if rng:
        a = _secs(rng.group(1), rng.group(2)); b = _secs(rng.group(3), rng.group(4))
        return {"range": (a, b)} if b > a else {"error": "The end time has to be after the start time."}
    at = _re.search(TIME, s)
    if at: return {"range": (_secs(at.group(1), at.group(2)), _secs(at.group(1), at.group(2)) + 30)}
    if _re.search(r"\b(all|every|everything|each)\b", s): return {"nums": list(range(1, max(n_list, 1) + 1))}
    m = _re.search(r"\b(?:first|top|best)\s+(\d|two|three|four|five|six)\b", s)
    if m:
        k = ORD.get(m.group(1)) or int(m.group(1)); return {"nums": list(range(1, k + 1))}
    nums = []
    for tok in _re.findall(r"\b(\d{1,2}|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|1st|2nd|3rd|4th|5th|6th|7th|8th|nine|ten)\b", s):
        v = ORD.get(tok) or int(tok)
        if v not in nums: nums.append(v)
    if not nums:
        if _re.search(r"\b(that|this|the)\s+(one|moment)\b", s) and n_list == 1: nums = [1]
        else: return None
    return {"nums": nums}

SAYS = _re.compile(r"(?:where|when|that|which|the (?:part|bit|moment|scene|line)|part where|bit where)\s+(?:(?:\w+\s+){0,3})?(?:says?|said|saying|mentions?|mentioned|talks? about|talked about|yells?|yelled|screams?|screamed|goes|asks?|asked|reads?)\b[:,]?\s+(.+)$", _re.I)
ABOUT = _re.compile(r"\bthe\s+(?:part|bit|moment|scene|section)\s+(?:about|with|on|where it'?s about)\s+(.+)$", _re.I)
QUOTED = _re.compile(r"[\"\u201c\u2018']([^\"\u201d\u2019']{4,160})[\"\u201d\u2019']")
STOPQ = set("the a an and or of to in on at is it that this for with as be are was were i you he she we they my your me him her his them so just like um uh oh yeah okay ok then than but if".split())
def phrase_of(text):
    s = (text or "").strip().rstrip("?.! ")
    m = QUOTED.search(s) or SAYS.search(s) or ABOUT.search(s)
    return m.group(1).strip(" \"'\u201c\u201d") if m else None

def find_phrase(j, phrase, limit=3):
    """Where in the video is this said? Fuzzy: speech to text often spells words a little differently."""
    import difflib
    from . import analyze
    try: tr = analyze.load_transcript(jobs.JOBS / j["id"] / "transcript.json")
    except Exception: return []
    ws = [w for w in (tr.get("words") or []) if _re.sub(r"\W", "", w["w"])]
    if not ws: return []
    norm = lambda x: _re.sub(r"[^\w']", "", x.lower())
    toks = [norm(w["w"]) for w in ws]
    q = [x for x in (norm(w) for w in phrase.split()) if x]
    key = [x for x in q if x not in STOPQ] or q
    if not key: return []
    def match(a, b): return a == b or (len(a) > 3 and len(b) > 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)
    N = len(toks); INF = 10 ** 9
    nxt = []
    for qt in key:
        arr = [INF] * (N + 1); last = INF
        for i in range(N - 1, -1, -1):
            if match(qt, toks[i]): last = i
            arr[i] = last
        nxt.append(arr)
    W = int(len(q) * 1.7) + 3; hits = []
    for i in range(N):
        got = [k for k in range(len(key)) if nxt[k][i] < i + W]
        cov = len(got) / len(key)
        if cov >= (1.0 if len(key) <= 2 else 0.7):
            first = min(nxt[k][i] for k in got); hits.append((cov, -(abs(first - i)), first))
    best = []
    for cov, _, first in sorted(hits, key=lambda h: (-h[0], -h[1])):
        tm = ws[first]["s"]
        if all(abs(tm - b["at"]) > 20 for b in best): best.append({"cov": cov, "at": tm})
        if len(best) >= limit: break
    st = j.get("settings") or {}
    L = max(15, min(45, int(((st.get("minlen") or 20) + (st.get("maxlen") or 55)) / 2)))
    dur = float((j.get("info") or {}).get("duration") or 0)
    segs = tr.get("segments") or []
    out = []
    for b in best:
        s0 = max(0.0, b["at"] - 3)
        for sg in segs:                                   # start where a sentence starts
            if sg["s"] <= b["at"] - 1 and sg["e"] >= s0 - 1: s0 = min(s0, sg["s"]) if b["at"] - sg["s"] < 8 else s0; break
        e0 = s0 + L
        for sg in segs:
            if sg["e"] >= e0: e0 = sg["e"]; break
        if dur: e0 = min(e0, dur)
        txt = " ".join(x["text"] for x in segs if x["s"] >= s0 - .3 and x["e"] <= e0 + .3).strip()
        head = next((sg["text"].strip() for sg in segs if sg["s"] - 0.5 <= b["at"] <= sg["e"] + 0.5), "")
        out.append({"s": s0, "e": e0, "at": b["at"], "cov": b["cov"], "txt": txt, "head": head})
    return out

def _auto_title(txt):
    from . import censor
    sents = [x.strip(" -\"'") for x in _re.split(r"(?<=[.!?])\s+", (txt or "").strip()) if x.strip(" -\"'")]
    first = next((x for x in sents if len(x.split()) >= 4), sents[0] if sents else "New clip")
    words = first.split()
    if len(words) > 9: first = " ".join(words[:9]).rstrip(",;:") + "..."
    return censor.mask_text(first)[:70]

def _clean_show(x): return x

RENAME_ID = _re.compile(r"\b(?:rename|re-?title|retitle|call|title|name|change the (?:title|name) of|set the (?:title|name) of)\b.*?\bclip\s*(?:number|no\.?|id)?\s*#?(\d{1,3})\b\s*(?:to|as|into|:|-|=)?\s*(.+)$", _re.I)
RENAME_IT = _re.compile(r"\b(?:rename|re-?title|retitle|call|name)\b.*?\b(?:it|that(?: clip| one)?|this(?: clip| one)?|the last (?:clip|one)|the new (?:clip|one))\b.*?\b(?:to|as|into)\b\s*(.+)$", _re.I)
DELETE_ID = _re.compile(r"\b(?:delete|remove|get rid of|trash|scrap)\b.*?\bclip\s*(?:number|no\.?|id)?\s*#?(\d{1,3})\b", _re.I)
DELETE_IT = _re.compile(r"\b(?:delete|remove|get rid of|undo|trash|scrap)\b.*?\b(?:it|that(?: clip| one)?|this(?: clip| one)?|the last (?:clip|one)|the new (?:clip|one))\b", _re.I)
YES = _re.compile(r"^\W*(yes|yeah|yep|yup|sure|ok|okay|do it|confirm|go ahead|delete it|please do)\W*$", _re.I)
NO = _re.compile(r"^\W*(no|nope|nah|cancel|stop|never ?mind|don'?t|keep it)\W*$", _re.I)

def _clean_title(x):
    x = (x or "").strip().strip("\"'\u201c\u201d\u2018\u2019`").strip()
    x = _re.sub(r"\s+", " ", x).rstrip(".")
    return x[:95]

def _clip_of(jid, cid):
    try: j = jobs.load(jid)
    except Exception: return None, None
    return j, next((c for c in j["clips"] if c["id"] == cid), None)

def existing_command(j, text):
    """Rename or delete a clip that already exists, by id ('clip 19') or by pronoun ('it', 'that clip'). Returns a reply or None."""
    jid = j["id"]; st = LAST.st(jid); s = (text or "").strip()
    pend = st.get("pending")
    if pend:
        if YES.match(s):
            LAST.put(jid, pending=None)
            return _delete_clip(jid, pend["cid"])
        if NO.match(s):
            LAST.put(jid, pending=None); return f"Okay, I kept clip #{pend['cid']}."
    if HOWQ.search(s): return None
    ref = _re.search(r"\b(?:talking about|meant|mean|i said|i meant|we (?:created|made|added)|you (?:created|made|added)|already|existing|that)\b.*?\bclip\s*(?:number|no\.?|id)?\s*#?(\d{1,3})\b", s, _re.I)
    if ref and not RENAME_ID.search(s) and not DELETE_ID.search(s):
        _, c = _clip_of(jid, int(ref.group(1)))
        if c:
            LAST.put(jid, last=c["id"])
            return f"Got it, clip **#{c['id']}** (\"{(c.get('title') or '')[:60]}\", {_mmss(c['start'])} to {_mmss(c['end'])}). What should I do with it? You can say **rename it to ...** or **delete it**."
    m = RENAME_ID.search(s)
    if m and not _re.search(r"\b(which|what)\b.*\?$", s):
        return _rename_clip(jid, int(m.group(1)), m.group(2))
    m = RENAME_IT.search(s)
    if m:
        cid = st.get("last")
        if not cid: return "Which clip? Tell me the number, for example **rename clip 19 to My new title**."
        return _rename_clip(jid, cid, m.group(1))
    m = DELETE_ID.search(s)
    cid = int(m.group(1)) if m else (st.get("last") if DELETE_IT.search(s) else None)
    if DELETE_IT.search(s) and not m and not cid: return "Which clip? Tell me the number, for example **delete clip 19**."
    if cid is not None:
        _, c = _clip_of(jid, cid)
        if not c: return f"There is no clip #{cid} in this video. The clips here are: {', '.join('#' + str(x['id']) for x in jobs.load(jid)['clips']) or 'none'}."
        LAST.put(jid, pending={"cid": cid})
        return f"Delete clip **#{cid}** (\"{(c.get('title') or '')[:60]}\", {_mmss(c['start'])} to {_mmss(c['end'])})? This removes its file too. Say **yes** to confirm or **no** to keep it."
    return None

def _rename_clip(jid, cid, new):
    new = _clean_title(new)
    if not new: return "What should the new title be? For example: **rename clip 19 to My new title**."
    j, c = _clip_of(jid, cid)
    if not c: return f"There is no clip #{cid} in this video. The clips here are: {', '.join('#' + str(x['id']) for x in j['clips']) or 'none'}."
    old = c.get("title") or ""
    def f(jj):
        for x in jj["clips"]:
            if x["id"] == cid: x["title"] = new
    jobs.update(jid, f); LAST.put(jid, last=cid); LAST.log(jid, f"renamed clip #{cid} from \"{old[:40]}\" to \"{new[:40]}\"")
    return f"Done. Clip **#{cid}** is now called \"{new}\" (it was \"{old[:60]}\"). The new title is used for narration, uploads and the clip list; the video itself is not re-rendered."

def _delete_clip(jid, cid):
    try:
        from . import server
        _, c = _clip_of(jid, cid); title = (c or {}).get("title") or ""
        server.delete_clip(jid, cid)
    except Exception as e:
        return f"I could not delete it: {getattr(e, 'detail', None) or e}"
    LAST.log(jid, f"deleted clip #{cid} (\"{title[:40]}\")"); st = LAST.st(jid)
    if st.get("last") == cid: LAST.put(jid, last=None)
    return f"Deleted clip #{cid} (\"{title[:60]}\")."

def do_clip(j, cmd):
    """Make the clips the user asked for. Returns the reply text."""
    jid = j["id"]
    if j.get("state") in ("running", "queued"): return "This video is still being processed. Ask me again when it has finished."
    if "error" in cmd: return cmd["error"]
    dur = float((j.get("info") or {}).get("duration") or 0)
    todo = []; note = ""
    if "phrase" in cmd:
        hits = find_phrase(j, cmd["phrase"])
        if not hits: return f"I could not find \"{cmd['phrase'][:80]}\" in the transcript. Speech to text can spell words differently, so try a few different words from that sentence, or give me times like **clip 12:30 to 13:00**."
        if len(hits) > 1 and hits[1]["cov"] >= hits[0]["cov"] - 0.01:
            LAST[jid] = [{"s": h["s"], "e": h["e"], "txt": h["txt"]} for h in hits]
            out = [f"I found that in {len(hits)} places. Which one do you want?", ""]
            for k, h in enumerate(hits, 1): out.append(f"{k}. **{_mmss(h['at'])}**: \"{_clean_show(h['txt'])[:150]}\"")
            out += ["", "Say **clip number 1**, **clip number 2**, and so on."]
            return "\n".join(out)
        h = hits[0]; todo.append((h["s"], h["e"], h["txt"], h["head"]))
        note = f"Found it at **{_mmss(h['at'])}**: \"{h['txt'][:120].strip()}\". "
    elif "range" in cmd:
        a, b = cmd["range"]
        if dur and a >= dur: return f"This video is only {_mmss(dur)} long, so {_mmss(a)} is past the end."
        b = min(b, dur or b, a + 90)
        if b - a < 3: return "That is too short for a clip. Give me at least a few seconds."
        m = _missed(j); txt = " ".join(x["text"] for x in m[2] if x["s"] >= a - .5 and x["e"] <= b + .5).strip() if m else ""
        todo.append((a, b, txt))
    else:
        lst = LAST.get(jid)
        if cmd.get("nums") and not lst:
            c = _clip_of(jid, cmd["nums"][0])[1]
            if c: return f"Clip **#{c['id']}** already exists (\"{(c.get('title') or '')[:60]}\"). Say **rename clip {c['id']} to ...** or **delete clip {c['id']}**, or ask me **which moments did I miss** for new ones."
        if not lst:
            m = _missed(j)
            if not m or not m[1]: return "I have no list of moments to pick from yet. Ask me **which moments did I miss** first, or give me times like **clip 28:01 to 28:38**."
            lst = LAST[jid] = [{"s": c["s"], "e": c["e"], "txt": c["txt"]} for c in m[1]]
            note = "(I used my current list of unclipped moments.) "
        bad = [n for n in cmd["nums"] if n < 1 or n > len(lst)]
        if bad and _clip_of(jid, bad[0])[1]:
            c = _clip_of(jid, bad[0])[1]
            return (f"Clip **#{bad[0]}** already exists (\"{(c.get('title') or '')[:60]}\"). My list of missed moments has {len(lst)} item{'s' if len(lst) != 1 else ''}. "
                    f"If you want to change clip #{bad[0]}, say **rename clip {bad[0]} to ...** or **delete clip {bad[0]}**.")
        if bad: return f"My list only has {len(lst)} moment{'s' if len(lst) != 1 else ''}, so number {bad[0]} does not exist. Ask me **which moments did I miss** to see it again."
        for n in cmd["nums"]: todo.append((lst[n - 1]["s"], lst[n - 1]["e"], lst[n - 1]["txt"]))
    ids = []
    def f(jj):
        i = max([c["id"] for c in jj["clips"]] + [0])
        for a, b, txt, *tt in todo:
            i += 1; ids.append(i)
            jj["clips"].append({"id": i, "start": round(a, 2), "end": round(b, 2), "score": 0, "title": _auto_title(tt[0] if tt and tt[0] else txt) if txt else "Custom clip",
                                "tags": [], "text": txt, "approved": True, "status": "queued", "idea": "added by SurgeAI"})
    jobs.update(jid, f)
    jobs.rerender(jid, ids)
    LAST.put(jid, last=ids[-1])
    for cid_, (a_, b_, *_x) in zip(ids, todo): LAST.log(jid, f"added clip #{cid_} ({_mmss(a_)} to {_mmss(b_)})")
    lines = [f"{note}Done! I added {'this clip' if len(ids) == 1 else str(len(ids)) + ' clips'} and started rendering:", ""]
    for cid, (a, b, txt, *tt) in zip(ids, todo):
        lines.append(f"- **clip #{cid}**: {_mmss(a)} to {_mmss(b)}, \"{_auto_title(tt[0] if tt and tt[0] else txt) if txt else 'Custom clip'}\"")
    lines += ["", "They show up in the clip list on this page in a moment, with your project's crop and captions. Open one to edit the title, timing or crop. Delete it from its card if you change your mind."]
    return "\n".join(lines)

def answer(scope, sid, focus, messages):
    """Generator of the reply text. Retries once when a small model refuses, and answers 'did I miss moments?' from the data."""
    from . import llm
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    j = None
    if scope == "video":
        try: j = jobs.load(sid)
        except Exception: j = None
    if j is not None:
        try: j = jobs.load(sid)
        except Exception: pass
        try: er = existing_command(j, last)
        except Exception as e: er = f"I could not do that ({type(e).__name__}: {str(e)[:100]})."
        if er: yield er; return
    if j is not None and PHRASEQ.search(last) and not _re.search(r"\b(clip|make|cut|add|grab)\b", last, _re.I):
        ph = phrase_of(last)
        if ph:
            hits = find_phrase(j, ph)
            if not hits: yield f"I could not find \"{ph[:80]}\" in the transcript."
            else:
                LAST[sid] = [{"s": h["s"], "e": h["e"], "txt": h["txt"]} for h in hits]
                yield ("He says it at " if len(hits) == 1 else "I found it in several places:\n") + "\n".join(f"- **{_mmss(h['at'])}**: \"{h['txt'][:140].strip()}\"" for h in hits) + "\n\nWant me to make a clip? Say **clip number 1**."
            return
    if j is not None:
        cmd = parse_clip_command(last, len(LAST.get(sid) or []) or 8)
        if cmd:
            try: yield do_clip(j, cmd)
            except Exception as e: yield f"I could not make the clip ({type(e).__name__}: {str(e)[:120]})."
            return
    sysmsg = build(scope, sid, focus)
    def run(extra=""):
        return llm.stream_chat([{"role": "system", "content": sysmsg + extra}] + messages, role="rating")
    if j is not None and MISSED.search(last):
        yield missed_answer(j); return        # facts from the data: a model only copies the list, and small ones refuse or invent
    buf = ""; it = run()
    for piece in it:
        buf += piece
        if len(buf) >= 90 or buf.rstrip().endswith((".", "!", "?", "\n")): break
    if REFUSAL.match(buf.strip()) and len(buf) < 200:           # a small model refusing for no reason: ask again, firmly
        retry = "".join(run(NUDGE))
        if REFUSAL.match(retry.strip()) and len(retry) < 200:
            yield ("My model keeps declining this question. Try asking it a different way, or connect a larger model under Settings > AI and agents."
                   + (' For missed moments, ask: "which moments did I miss".' if scope == "video" else ""))
        else: yield retry
        return
    if buf: yield buf
    for piece in it: yield piece

def _transcript_and_missed(j):
    """Timestamped transcript (when it fits), the parts already clipped, and the best moments NOT clipped yet.
    Curse words are masked here: the briefing does not need them, and small models often refuse text that has them."""
    M = _clean
    m = _missed(j); out = []
    if not m: return ""
    clips, picked, segs = m
    out.append("ALREADY CLIPPED: " + (", ".join(f"{_mmss(a)}-{_mmss(b)}" for a, b in sorted(clips)) or "nothing yet"))
    if picked:
        out.append("MOMENTS NOT CLIPPED YET (best candidates found by loudness, excited words and hooks; loudness is in standard deviations above this video's average):")
        for k, c in enumerate(sorted(picked, key=lambda c: -c["score"]), 1):
            out.append(f"{k}. {_mmss(c['s'])}-{_mmss(c['e'])} loudness peak {c['pk']:+.1f}, average {c['mn']:+.1f}: \"{M(c['txt'][:260])}\"")
    else:
        out.append("No unclipped moments stand out: the loud and exciting parts are already covered by clips.")
    lines = [f"[{_mmss(sg['s'])}] {M(sg['text'].strip())}" for sg in segs]
    full = "\n".join(lines)
    if len(full) <= 5500: out.append("FULL TRANSCRIPT WITH TIMES:\n" + full)
    else:
        step = max(1, len(lines) // 40)
        out.append(f"TRANSCRIPT OUTLINE (every {step}th line of {len(lines)}):\n" + "\n".join(l[:110] for l in lines[::step]))
    return "\n".join(out)

def _video_ctx(j, focus=None):
    st = j.get("settings") or {}; br = j.get("brief") or {}
    s = [f"VIDEO: \"{j.get('title')}\"  source: {str(j.get('source'))[:80]}  length: {int((j.get('info') or {}).get('duration', 0) / 60)} min  type: {st.get('mode')}  language: {st.get('language')}",
         f"Creator goals: looks for {br.get('ideas') or 'nothing set'}; skips {br.get('avoid') or 'nothing set'}. Notes: {(br.get('prompt') or '')[:600]}",
         f"Settings: {st.get('count')} clips of {st.get('minlen')}-{st.get('maxlen')}s, crop {st.get('layout')}, captions {st.get('captions')}"]
    clips = j.get("clips") or []
    s.append(f"CLIPS ({len(clips)}), best first:")
    for c in sorted(clips, key=lambda c: -(c.get("score") or 0)):
        s.append(_clip_line(c, full=(focus is not None and str(c["id"]) == str(focus))))
    st = LAST.st(j["id"])
    if st.get("actions"): s.append("WHAT SURGEAI ALREADY DID IN THIS CHAT (oldest first): " + "; ".join(st["actions"]))
    try: s.append(_transcript_and_missed(j))
    except Exception as e: s.append(f"(Could not read the transcript: {type(e).__name__})")
    return "\n".join(s)

SYSTEM = ("You are SurgeAI, the friendly assistant inside Clipsurge, a tool that turns long videos into short vertical clips. You help the creator with ideas for clips, "
          "titles, hooks, hashtags and tags, and with how to raise clip scores and results. Use ONLY the briefing below for facts about their videos "
          "and numbers; never invent views, scores or trends. Scores (0 to 100) come from loudness, speech, keywords, the creator's goals and an AI rating: "
          "to raise a score, a clip needs a strong first line, a clear payoff, emotion, fitting the creator's goals and a length near their best clips. "
          "Be concrete and short: bullet points, ready to copy titles and #hashtags. Only suggest tags that really describe the video: misleading tags are spam and break "
          "platform rules. You cannot promise a video will go viral, so say so if asked. The briefing contains the real transcript with times, the loudness of each moment and a list of moments not clipped yet: use it to answer questions about missed moments, give times (m:ss) and quote the words. Never say you lack access to the video or stream: you have the data in the briefing. If the data is thin, say what is missing. "
          "You can also DO things for the creator on a video page: clip a moment from your list (\"clip number 3\"), clip by what is said (\"clip the part where he says ...\"), clip by times, rename a clip (\"rename clip 5 to ...\") and delete a clip (\"delete clip 5\", with confirmation). If asked whether you can, say yes and show the exact words to use. Never say you cannot edit or clip videos. "
          "Reply in the language the user writes in.")

def build(scope, sid, focus=None):
    if scope == "video":
        j = jobs.load(sid); pr = projects.get(j.get("project", "inbox"))
        ctx = f"PROJECT: {pr.get('name')} - {pr.get('description') or ''}\n" + _video_ctx(j, focus)
        topic = insights._topic(j.get("title") or "")
    elif scope == "general":
        ps = projects.all_projects(); js = jobs.list_jobs()
        ctx = [f"The creator has {len(ps)} project(s) and {len(js)} video(s). They are asking from outside any one project, so help with the whole channel, planning, ideas, tags and how to use Clipsurge.", "PROJECTS:"]
        allc = []
        for p in ps[:15]:
            pj = [x for x in js if x.get("project") == p["id"]]; cs = [c for x in pj for c in (x.get("clips") or [])]; sc = [c.get("score") or 0 for c in cs]
            ctx.append(f"- {p.get('name')}: {len(pj)} videos, {len(cs)} clips, avg score {round(sum(sc)/len(sc)) if sc else '-'}; looks for {(p.get('brief') or {}).get('ideas') or 'nothing set'}")
            allc += [(x, c) for x in pj for c in (x.get("clips") or [])]
        ctx.append("TOP CLIPS ACROSS ALL PROJECTS:")
        for x, c in sorted(allc, key=lambda t: -(t[1].get("score") or 0))[:8]: ctx.append(_clip_line(c) + f"   [from \"{(x.get('title') or '')[:40]}\"]")
        ctx = "\n".join(ctx); topic = insights._topic((ps[0].get("name") if ps else "") or "")
    else:
        pr = projects.get(sid); br = pr.get("brief") or {}; df = pr.get("defaults") or {}
        js = [x for x in jobs.list_jobs() if x.get("project") == sid]
        ctx = [f"PROJECT: {pr.get('name')} - {pr.get('description') or ''}",
               f"Creator goals: looks for {br.get('ideas') or 'nothing set'}; skips {br.get('avoid') or 'nothing set'}. Notes: {(br.get('prompt') or '')[:800]}",
               f"Defaults: {df}", f"VIDEOS ({len(js)}):"]
        allc = []
        for x in js[:25]:
            cs = x.get("clips") or []; sc = [c.get("score") or 0 for c in cs]
            ctx.append(f"- \"{(x.get('title') or '')[:70]}\" {x.get('state')}, {len(cs)} clips, avg score {round(sum(sc)/len(sc)) if sc else '-'}")
            allc += [(x, c) for c in cs]
        ctx.append("TOP CLIPS:")
        for x, c in sorted(allc, key=lambda t: -(t[1].get("score") or 0))[:8]: ctx.append(_clip_line(c) + f"   [from \"{(x.get('title') or '')[:40]}\"]")
        low = sorted([t for t in allc if (t[1].get('score') or 0) > 0], key=lambda t: (t[1].get('score') or 0))[:4]
        if low:
            ctx.append("LOWEST SCORING CLIPS:")
            for x, c in low: ctx.append(_clip_line(c))
        ctx = "\n".join(ctx); topic = insights._topic((js[0].get("title") if js else "") or pr.get("name") or "")
    extra = _perf_block()
    if settings.get().get("youtube", {}).get("learn", True) is not None:
        tb = _trend_block(topic)
    else: tb = ""
    return SYSTEM + "\n\n--- BRIEFING ---\n" + ctx[:12500] + ("\n\n" + extra if extra else "") + ("\n\n" + tb if tb else "")
