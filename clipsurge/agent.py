# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""SurgeAI agent layer: undo, chained requests, preference memory, project-wide actions, proactive tips and an optional
model planner. Everything here works with any model, including tiny ones: the rules do the work and a model plan is
always shown to the creator for confirmation before anything changes."""
import copy, json, re as _re, statistics
from . import jobs
from .config import DATA

FIELDS = ("title", "tags", "start", "end", "edit", "approved", "text", "idea", "score")

# ------------------------------------------------------------------ undo
def snap(j): return [{k: copy.deepcopy(c.get(k)) for k in ("id",) + FIELDS} for c in j["clips"]]
def _sig(x): return json.dumps(x, sort_keys=True, default=str)

def push_undo(jid, label, before):
    from . import assist
    st = assist.LAST.st(jid).get("undo") or []
    assist.LAST.put(jid, undo=(st + [{"label": label, "clips": before}])[-8:])

def tracked(j, label, fn):
    before = snap(j); r = fn()
    try: after = snap(jobs.load(j["id"]))
    except Exception: return r
    if _sig(before) != _sig(after): push_undo(j["id"], label, before)
    return r

def undo(jid):
    from . import assist, server
    st = assist.LAST.st(jid); stack = list(st.get("undo") or [])
    if not stack: return "There is nothing to undo on this video."
    j = jobs.load(jid)
    if j.get("state") in ("running", "queued"): return "This video is still being processed. Ask me to undo when it has finished."
    top = stack.pop(); notes = []; rer = []
    old = {c["id"]: c for c in top["clips"]}
    for c in j["clips"]:
        if c["id"] not in old:
            try: server.delete_clip(jid, c["id"]); notes.append(f"removed clip #{c['id']}")
            except Exception as e: notes.append(f"could not remove clip #{c['id']} ({getattr(e, 'detail', e)})")
    def f(jj):
        have = {c["id"]: c for c in jj["clips"]}
        for cid, o in old.items():
            if cid in have:
                c = have[cid]; changed = any(c.get(k) != o.get(k) for k in ("start", "end", "edit"))
                for k, v in o.items():
                    if k == "id": continue
                    if v is None: c.pop(k, None)
                    else: c[k] = copy.deepcopy(v)
                if changed: c["status"] = "queued"; rer.append(cid)
            else:
                nc = {k: copy.deepcopy(v) for k, v in o.items() if v is not None}
                nc.update(status="queued"); jj["clips"].append(nc); rer.append(cid); notes.append(f"brought back clip #{cid}")
        jj["clips"].sort(key=lambda c: c["id"])
    jobs.update(jid, f)
    assist.LAST.put(jid, undo=stack, last=None)
    if rer: jobs.rerender(jid, rer)
    assist.LAST.log(jid, f"undid: {top['label']}")
    msg = f"Undone: {top['label']}."
    if notes: msg += " (" + ", ".join(notes) + ")"
    if rer: msg += " Re-rendering " + ", ".join(f"#{i}" for i in rer) + " to match."
    left = len(stack)
    return msg + (f" I can undo {left} more step{'s' if left != 1 else ''}." if left else "")

UNDO = _re.compile(r"^\W*(?:please\s+|can you\s+|could you\s+)?(?:undo|revert|roll ?back|take (?:that|it|this) back|go back|put it back)\b", _re.I)

# ------------------------------------------------------------------ preferences (kept on this computer)
PF = DATA / "surgeai_prefs.json"
def _pl():
    try: return json.loads(PF.read_text("utf-8"))
    except Exception: return {"notes": [], "c": {}}
def _ps(d):
    try: PF.write_text(json.dumps(d, indent=1), "utf-8")
    except Exception: pass

def learn(kind, val):
    if val in (None, ""): return
    d = _pl(); c = d.setdefault("c", {})
    if kind == "len": c["len"] = ((c.get("len") or []) + [round(float(val))])[-30:]
    else:
        m = c.setdefault(kind, {}); m[str(val)] = m.get(str(val), 0) + 1
    _ps(d)

def top(kind, minn=3):
    c = (_pl().get("c") or {}).get(kind) or {}
    if not c or not isinstance(c, dict): return None
    k, v = max(c.items(), key=lambda x: x[1]); return k if v >= minn else None

def pref_len():
    L = (_pl().get("c") or {}).get("len") or []
    return float(statistics.median(L)) if len(L) >= 3 else None

NAMES = {"layout": {"stack": "webcam + gameplay", "game": "gameplay only", "fit": "whole screen with blur", "follow": "follow face", "speaker": "cut to speaker", "auto": "auto"}}

def prefs_summary():
    d = _pl(); out = []
    lay = top("layout"); cap = top("captions"); ln = pref_len()
    if lay: out.append(f"you usually pick the **{NAMES['layout'].get(lay, lay)}** crop")
    if cap: out.append(f"you usually use **{cap}** captions")
    if ln: out.append(f"your clips are usually about **{int(ln)} seconds**")
    return out, (d.get("notes") or [])

def prefs_text():
    out, notes = prefs_summary()
    if not out and not notes: return ""
    return "\n\nWHAT YOU KNOW ABOUT THIS CREATOR (from past chats; respect it): " + "; ".join(_re.sub(r"\*\*", "", x) for x in out) + ("; their own notes: " + " | ".join(notes) if notes else "")

REMEMBER = _re.compile(r"^\W*(?:please\s+)?remember\b(?:\s+that)?\s+(.{3,200})$", _re.I)
FORGET = _re.compile(r"\bforget\b.*\b(everything|my preferences|what you (?:know|remember)|all of it|me)\b", _re.I)
RECALL = _re.compile(r"\b(what (?:do|did) you (?:remember|know) about me|what have you learned|my preferences|what do you remember)\b", _re.I)

def memory_command(text):
    s = text.strip()
    m = REMEMBER.match(s)
    if m:
        d = _pl(); n = d.setdefault("notes", []); note = m.group(1).strip(" .")
        if note.lower() not in [x.lower() for x in n]: n.append(note)
        d["notes"] = n[-20:]; _ps(d)
        return f"Got it, I will remember: \"{note}\". Ask **what do you remember about me** to see everything, or **forget my preferences** to clear it."
    if FORGET.search(s):
        _ps({"notes": [], "c": {}}); return "Done. I forgot your notes and what I learned about your usual choices."
    if RECALL.search(s):
        out, notes = prefs_summary()
        if not out and not notes: return "Nothing yet. I learn your usual crop, captions and clip length as you ask me to change clips, and you can tell me things with **remember that ...**."
        return "\n".join(["Here is what I remember (it is saved only on this computer):", ""] + [f"- {x}" for x in out] + [f"- you told me: \"{n}\"" for n in notes])
    return None

# ------------------------------------------------------------------ chained requests
VERBS = r"(?:rename|add|set|make|trim|shorten|lengthen|delete|give|turn|hide|re-?render|clip(?=\s+(?:\d{1,3}:\d{2}|the part|the moment|number\s+\d|all\b|every\b))|undo|put|change|remove|captions?|crop)"
SPLIT = _re.compile(r"\s*(?:,?\s+and\s+(?=clip\s*#?\d{1,3}\s+(?:to|as)\b)|,?\s+and\s+then\s+|,?\s+then\s+|;\s*|,?\s+and\s+also\s+|,?\s+and\s+(?=" + VERBS + r"\b)|,\s+(?=" + VERBS + r"\b))", _re.I)

def split_commands(t):
    parts = [x.strip(" .") for x in SPLIT.split(t or "") if x and x.strip(" .")]
    for n in range(1, len(parts)):                    # "rename clip 3 to X and clip 4 to Y": the second part inherits the verb
        if _re.match(r"clip\s*#?\d{1,3}\s+(?:to|as)\b", parts[n], _re.I) and _re.match(r"(?:rename|call|title|retitle)\b", parts[n - 1], _re.I):
            parts[n] = "rename " + parts[n]
    return parts

def _one(j, sid, text):
    from . import assist
    try: j = jobs.load(sid)
    except Exception: pass
    try: return assist.video_command(j, sid, text)
    except Exception as e: return f"I could not do that ({type(e).__name__}: {str(e)[:100]})."

def run_chain(j, sid, parts):
    out = []
    for n, pt in enumerate(parts, 1):
        r = _one(j, sid, pt)
        if r is None:
            out.append(f"**Step {n}** (\"{pt[:60]}\"): I did not understand this one, so I stopped here.")
            break
        out.append(f"**Step {n}:** " + r.split("\n\n")[0] if len(parts) > 1 else r)
    return "\n\n".join(out)

# ------------------------------------------------------------------ model planner (optional, always confirmed)
OPS = {"rename", "tags_add", "tags_remove", "trim", "captions", "crop", "narration", "make_clip", "rerender"}
LAYWORD = {"stack": "stack", "game": "gameplay only", "fit": "whole screen", "follow": "follow face", "speaker": "speaker", "auto": "auto"}

def _ts(x):
    x = str(x).strip()
    if _re.fullmatch(r"\d{1,3}:\d{2}", x): return x
    if _re.fullmatch(r"\d+(\.\d+)?", x): v = int(float(x)); return f"{v // 60}:{v % 60:02d}"
    return None

def plan(j, text):
    """Ask the connected model to turn the request into steps. Returns a list of plain sentences, or None."""
    from . import llm
    try:
        pv = llm.provider("rating"); mid = llm.model_id("rating")
        if not pv or not mid: return None
        ids = {c["id"] for c in j["clips"]}
        clips = "; ".join(f"#{c['id']} \"{(c.get('title') or '')[:40]}\" {int(c['start'])}-{int(c['end'])}s" for c in j["clips"])[:900]
        sys_ = ("Turn the creator's request into a JSON list of steps. Reply with ONLY the JSON list, nothing else. Steps: "
                '{"do":"rename","clip":N,"title":"..."} {"do":"tags_add","clip":N,"tags":["a","b"]} {"do":"tags_remove","clip":N,"tags":["a"]} '
                '{"do":"trim","clip":N,"start":"m:ss","end":"m:ss"} {"do":"captions","clip":N,"style":"pop|clean|fire|off"} '
                '{"do":"crop","clip":N,"layout":"stack|game|fit|follow|speaker|auto"} {"do":"narration","clip":N,"on":true} '
                '{"do":"make_clip","start":"m:ss","end":"m:ss"} {"do":"rerender","clip":N}. If the request does not fit these, reply []. Clips: ' + clips)
        r = llm._chat(pv, mid, [{"role": "system", "content": sys_}, {"role": "user", "content": text[:400]}], 350, 0.1)
        r = _re.sub(r"<think>.*?</think>", "", r, flags=_re.S)
        m = _re.search(r"\[.*\]", r, _re.S)
        steps = json.loads(m.group(0)) if m else []
    except Exception: return None
    out = []
    for s in steps[:6] if isinstance(steps, list) else []:
        if not isinstance(s, dict) or s.get("do") not in OPS: return None
        d = s["do"]; n = s.get("clip")
        if d != "make_clip":
            try: n = int(n)
            except Exception: return None
            if n not in ids: return None
        if d == "rename":
            t = str(s.get("title", "")).strip()[:90]
            if len(t) < 2: return None
            out.append(f"rename clip {n} to {t}")
        elif d in ("tags_add", "tags_remove"):
            tg = ["#" + _re.sub(r"[^\w]", "", str(x)) for x in (s.get("tags") or [])[:10] if _re.sub(r"[^\w]", "", str(x))]
            if not tg: return None
            out.append(f"add tags {' '.join(tg)} to clip {n}" if d == "tags_add" else f"remove the tag {' '.join(tg)} from clip {n}")
        elif d == "trim":
            x, y = _ts(s.get("start")), _ts(s.get("end"))
            if not x or not y: return None
            out.append(f"trim clip {n} to {x}-{y}")
        elif d == "captions":
            st = str(s.get("style", "")).lower()
            if st not in ("pop", "clean", "fire", "off"): return None
            out.append(f"captions of clip {n} to {st}")
        elif d == "crop":
            lw = LAYWORD.get(str(s.get("layout", "")).lower())
            if not lw: return None
            out.append(f"set the crop of clip {n} to {lw}")
        elif d == "narration": out.append(f"turn {'on' if s.get('on', True) else 'off'} narration for clip {n}")
        elif d == "make_clip":
            x, y = _ts(s.get("start")), _ts(s.get("end"))
            if not x or not y: return None
            out.append(f"clip {x} to {y}")
        elif d == "rerender": out.append(f"re-render clip {n}")
    return out or None

LOOKS_ACTION = _re.compile(r"\b(clip\s*#?\d|rename|trim|shorten|lengthen|caption|crop|narrat|tags?\b|re-?render|make (?:it|clip))", _re.I)

# ------------------------------------------------------------------ entry points
def handle_video(j, sid, text):
    """Reply text when the message is something to DO on this video, else None (the model answers)."""
    from . import assist
    s = (text or "").strip(); st = assist.LAST.st(sid)
    pl = st.get("plan")
    if pl:
        assist.LAST.put(sid, plan=None)
        if assist.YES.match(s):
            r = tracked(j, "model plan", lambda: run_chain(j, sid, pl))
            assist.LAST.log(sid, "did plan: " + "; ".join(pl)[:80]); return r
        if assist.NO.match(s): return "Okay, I did nothing."
    mc = memory_command(s)
    if mc: return mc
    if UNDO.match(s): return undo(sid)
    if (assist.YES.match(s) or assist.NO.match(s)) and not st.get("pending") and not st.get("sched"):
        return "I am not waiting for an answer right now. Tell me what to do, for example **rename clip 3 to ...**, or ask **what can you do?**"
    from . import chatfacts
    try:
        rf = chatfacts.handle(j, sid, s, st.get("last"))
    except Exception as e: rf = f"I could not do that ({type(e).__name__}: {str(e)[:100]})."
    if rf: return rf
    parts = split_commands(s)
    if len(parts) > 1 and _re.search(r"\b(clip|rename|tag|trim|caption|crop|narrat|title|delete|render)", parts[0], _re.I) and not assist.HOWQ.search(s):
        return tracked(j, "several steps", lambda: run_chain(j, sid, parts))
    pend = st.get("pending")
    label = f"delete clip {pend['cid']}" if pend and assist.YES.match(s) else s[:50]
    r = tracked(j, label, lambda: _one(j, sid, s))
    if r is not None: return r
    if LOOKS_ACTION.search(s) and not assist.HOWQ.search(s) and not _re.search(r"\?\s*$", s):
        pp = plan(j, s)
        if pp:
            assist.LAST.put(sid, plan=pp)
            return "I understood this as:\n\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(pp, 1)) + "\n\nSay **yes** and I will do it, or **no** to cancel."
    return None

def _jobs_of(pid):
    return [x["id"] for x in jobs.list_jobs() if x.get("project") == pid and x.get("state") == "done" and x.get("clips")]

PROJ_ALL = _re.compile(r"\b(every|all|each)\b.{0,30}\b(clips?|videos?)\b|\beverything\b", _re.I)

def handle_project(pid, text):
    from . import assist, actions
    s = (text or "").strip(); low = s.lower()
    mc = memory_command(s)
    if mc: return mc
    if UNDO.match(s):
        b = assist.LAST.st(pid).get("batch") or []
        if not b: return "There is no project-wide change to undo."
        res = [undo(x) for x in b]; assist.LAST.put(pid, batch=[])
        return f"Undid the last project-wide change on {len(b)} video{'s' if len(b) != 1 else ''}.\n\n" + res[0]
    mc2 = __import__("clipsurge.chatfacts", fromlist=["x"]).meta("project", pid, None, s)
    if mc2: return mc2
    if not PROJ_ALL.search(s) or assist.HOWQ.search(s): return None
    mc2 = __import__("clipsurge.chatfacts", fromlist=["x"]).meta("project", pid, None, s)
    if mc2: return mc2
    if _re.search(r"\b(delete|remove (?:the )?clips?|get rid|rename)\b", low):
        return "I do not delete or rename in bulk, because it is easy to regret. Open a video and ask me there, or name the clip you mean."
    ids = _jobs_of(pid)
    if not ids: return "This project has no finished videos with clips yet."
    done_clips = 0; vids = 0; first = None; changed = []
    for jid in ids:
        j = jobs.load(jid); before = snap(j)
        r = actions.handle(j, s, None)
        if r is None:
            if first is None: return None
            continue
        if first is None: first = r
        done_clips += len(_re.findall(r"(?m)^Clip \*\*#", r)); vids += 1
        try:
            if _sig(before) != _sig(snap(jobs.load(jid))): push_undo(jid, "project-wide: " + s[:40].strip(" ,."), before); changed.append(jid)
        except Exception: pass
    assist.LAST.put(pid, batch=changed)
    sample = first.split("\n\n")[0].split("\n")[0] if first else ""
    return f"Done across the project: {done_clips} clip{'s' if done_clips != 1 else ''} in {vids} video{'s' if vids != 1 else ''}.\n\nExample: {sample}\n\nSay **undo** if you want it back."

# ------------------------------------------------------------------ proactive tips
def tips(scope, sid):
    from . import assist
    out = []
    try:
        if scope == "video":
            j = jobs.load(sid)
            if j.get("state") in ("running", "queued") or not j.get("clips"): return []
            cl = j["clips"]
            bad = [c for c in cl if c.get("status") == "error"]
            if bad: out.append({"t": f"Clip #{bad[0]['id']} failed to render", "q": f"re-render clip {bad[0]['id']}"})
            nt = [c for c in cl if not c.get("tags")]
            if nt: out.append({"t": f"{len(nt)} clip{'s have' if len(nt) != 1 else ' has'} no tags", "q": f"for clip {nt[0]['id']} add tags that can help it go viral" if len(nt) == 1 else "add tags to all clips"})
            lg = [c for c in cl if c["end"] - c["start"] > 60]
            if lg:
                c = lg[0]; ex = int(c["end"] - c["start"] - 45)
                out.append({"t": f"Clip #{c['id']} is {int(c['end'] - c['start'])} s long. Shorts under 60 s usually do better", "q": f"make clip {c['id']} shorter by {ex} seconds"})
            gen = [c for c in cl if not (c.get("title") or "").strip() or (c.get("title") or "").startswith("Custom clip")]
            if gen: out.append({"t": f"Clip #{gen[0]['id']} has no real title", "q": f"give clip {gen[0]['id']} a better title"})
            try:
                m = assist._missed(j)
                if m and m[1]: out.append({"t": f"{len(m[1])} strong moments are not clipped yet", "q": "Which moments did I miss?"})
            except Exception: pass
        elif scope == "project":
            nt = 0
            for jid in _jobs_of(sid): nt += sum(1 for c in jobs.load(jid)["clips"] if not c.get("tags"))
            if nt: out.append({"t": f"{nt} clip{'s' if nt != 1 else ''} in this project have no tags", "q": "add tags to all clips in this project"})
    except Exception: return out[:4]
    return out[:4]
