# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Chat with your AI model about a project or a video. Builds a compact, honest briefing from what Clipsurge knows
(goals, clips, scores, transcript, your upload results) so the model can suggest ideas, titles, tags and improvements."""
import json, re, time
from . import jobs, projects, insights, settings

def _clip_line(c, full=False):
    t = (c.get("text") or "").replace("\n", " ")
    s = f"#{c['id']} \"{(c.get('title') or '')[:80]}\" score {c.get('score')} {int(c.get('end', 0) - c.get('start', 0))}s"
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

def _video_ctx(j, focus=None):
    st = j.get("settings") or {}; br = j.get("brief") or {}
    s = [f"VIDEO: \"{j.get('title')}\"  source: {str(j.get('source'))[:80]}  length: {int((j.get('info') or {}).get('duration', 0) / 60)} min  type: {st.get('mode')}  language: {st.get('language')}",
         f"Creator goals: looks for {br.get('ideas') or 'nothing set'}; skips {br.get('avoid') or 'nothing set'}. Notes: {(br.get('prompt') or '')[:600]}",
         f"Settings: {st.get('count')} clips of {st.get('minlen')}-{st.get('maxlen')}s, crop {st.get('layout')}, captions {st.get('captions')}"]
    clips = j.get("clips") or []
    s.append(f"CLIPS ({len(clips)}), best first:")
    for c in sorted(clips, key=lambda c: -(c.get("score") or 0)):
        s.append(_clip_line(c, full=(focus is not None and str(c["id"]) == str(focus))))
    try:
        tr = json.loads((jobs.JOBS / j["id"] / "transcript.json").read_text("utf-8")) if hasattr(jobs, "JOBS") else None
    except Exception: tr = None
    if tr and not focus:
        txt = " ".join(w["w"] for w in tr["words"][:260])
        s.append("TRANSCRIPT START: " + txt)
    return "\n".join(s)

SYSTEM = ("You are SurgeAI, the friendly assistant inside Clipsurge, a tool that turns long videos into short vertical clips. You help the creator with ideas for clips, "
          "titles, hooks, hashtags and tags, and with how to raise clip scores and results. Use ONLY the briefing below for facts about their videos "
          "and numbers; never invent views, scores or trends. Scores (0 to 100) come from loudness, speech, keywords, the creator's goals and an AI rating: "
          "to raise a score, a clip needs a strong first line, a clear payoff, emotion, fitting the creator's goals and a length near their best clips. "
          "Be concrete and short: bullet points, ready to copy titles and #hashtags. Only suggest tags that really describe the video: misleading tags are spam and break "
          "platform rules. You cannot promise a video will go viral, so say so if asked. If the data is thin, say what is missing. "
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
    return SYSTEM + "\n\n--- BRIEFING ---\n" + ctx[:9000] + ("\n\n" + extra if extra else "") + ("\n\n" + tb if tb else "")
