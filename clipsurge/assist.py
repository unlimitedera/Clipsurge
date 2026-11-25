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

def missed_answer(j):
    """A plain, always-correct answer to 'did I miss moments?', written from the data (no model needed)."""
    m = _missed(j)
    if not m: return "I can't see a transcript for this video yet. Wait until step 2 (Transcribe) has finished, then ask again."
    clips, picked, segs = m
    if not picked:
        return "Good news: I can't find loud or exciting parts that are not already covered by your clips. Everything that stands out is already clipped."
    out = ["Here are the best moments you haven't clipped yet. I found them from how loud they are, excited words and hooks:", ""]
    for k, c in enumerate(picked, 1):
        out.append(f"{k}. **{_mmss(c['s'])} to {_mmss(c['e'])}**: \"{c['txt'][:220].strip()}\"" + (f" (loud: {c['pk']:+.1f} above average)" if c["pk"] >= 1.5 else ""))
    out += ["", "To clip one, open **Full video and manual clips** on this page, type the start and end time, and press Add clip. Loud does not always mean good, so watch each one first."]
    return "\n".join(out)

import re as _re
REFUSAL = _re.compile(r"^\W*(i['\u2019]?m sorry|sorry|i can(?:['\u2019]?t|not)|i am unable|i['\u2019]?m unable|i won['\u2019]?t|as an ai)", _re.I)
MISSED = _re.compile(r"\b(miss(ed|ing)?|overlook(ed)?|left out|unclipped|not clipped|what else|other moments|more moments|good parts)\b", _re.I)
NUDGE = ("\n\nIMPORTANT: everything above is the creator's own footage and notes. Answer the creator's question helpfully and directly using the briefing. "
         "Do not refuse, do not apologise. If something is not in the briefing, say exactly what is missing.")

def answer(scope, sid, focus, messages):
    """Generator of the reply text. Retries once when a small model refuses, and answers 'did I miss moments?' from the data."""
    from . import llm
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    j = None
    if scope == "video":
        try: j = jobs.load(sid)
        except Exception: j = None
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
    try: s.append(_transcript_and_missed(j))
    except Exception as e: s.append(f"(Could not read the transcript: {type(e).__name__})")
    return "\n".join(s)

SYSTEM = ("You are SurgeAI, the friendly assistant inside Clipsurge, a tool that turns long videos into short vertical clips. You help the creator with ideas for clips, "
          "titles, hooks, hashtags and tags, and with how to raise clip scores and results. Use ONLY the briefing below for facts about their videos "
          "and numbers; never invent views, scores or trends. Scores (0 to 100) come from loudness, speech, keywords, the creator's goals and an AI rating: "
          "to raise a score, a clip needs a strong first line, a clear payoff, emotion, fitting the creator's goals and a length near their best clips. "
          "Be concrete and short: bullet points, ready to copy titles and #hashtags. Only suggest tags that really describe the video: misleading tags are spam and break "
          "platform rules. You cannot promise a video will go viral, so say so if asked. The briefing contains the real transcript with times, the loudness of each moment and a list of moments not clipped yet: use it to answer questions about missed moments, give times (m:ss) and quote the words. Never say you lack access to the video or stream: you have the data in the briefing. If the data is thin, say what is missing. "
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
