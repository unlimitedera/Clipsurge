# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Learns from your uploads. Reads views, likes and comments of the clips you posted, finds what the best ones have in
common (length, crop, title style, tags, posting time), looks up what is trending on the topic, and suggests tags.

Nothing here can promise a video will go viral. It looks for patterns in YOUR results and in public videos on the same
topic, and only suggests tags that fit the video."""
import json, math, re, threading, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from .config import DATA

DB = DATA / "insights.json"
_lock = threading.Lock()
_busy = {"stats": False, "trend": set()}
_db_cache = None
STOP = set("the a an and or of to in on at for with is it this that my your i you we they he she was were be been are am do did "
           "from by as so but if not no yes just very new video videos short shorts clip clips official full part live".split())

def _load():
    global _db_cache
    if _db_cache is None:
        try: _db_cache = json.loads(DB.read_text("utf-8"))
        except Exception: _db_cache = {}
        for k, d in (("videos", {}), ("trends", {}), ("fetched", 0)): _db_cache.setdefault(k, d)
    return _db_cache

def _save():
    with _lock:
        tmp = DB.with_suffix(".tmp"); tmp.write_text(json.dumps(_load(), indent=1), "utf-8")
        for _ in range(20):
            try: tmp.replace(DB); break
            except PermissionError: time.sleep(0.05)

def vid_of(url):
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None

# ---------------------------------------------------------------- what was uploaded

def tracked():
    """Every clip that was posted to YouTube, with what we know about how it was made."""
    from . import transfers, jobs
    out, seen = {}, set()
    try: ups = transfers.list_uploads()
    except Exception: ups = []
    try: js = {j["id"]: j for j in jobs.list_jobs()}
    except Exception: js = {}
    def meta_of(jid, cid):
        j = js.get(jid) or {}
        c = next((x for x in j.get("clips", []) if str(x["id"]) == str(cid)), None)
        if not c: return {}
        st = j.get("settings") or {}
        return {"dur": round(max(0, (c.get("end") or 0) - (c.get("start") or 0)), 1), "score": c.get("score"),
                "layout": c.get("layout_used") or (c.get("edit") or {}).get("layout") or st.get("layout"),
                "mode": st.get("mode"), "tags": c.get("tags") or [], "project": j.get("project"),
                "narration": bool(((c.get("edit") or {}).get("narration") or st.get("narration") or {}).get("enabled")),
                "captions": st.get("captions"), "source": j.get("title")}
    for u in ups:
        if u.get("state") != "done": continue
        v = vid_of(u.get("url"))
        if not v or v in seen: continue
        seen.add(v)
        m = dict(meta_of(u["jid"], u["cid"])); m.update({k: x for k, x in (u.get("meta") or {}).items() if x not in (None, "")})
        out[v] = {"id": v, "url": u["url"], "title": u.get("title"), "jid": u["jid"], "cid": u["cid"],
                  "posted": u.get("t1") or u.get("t0"), "meta": m, "tags": u.get("tags") or m.get("tags") or []}
    for jid, j in js.items():                                    # clips posted before uploads were logged here
        for c in j.get("clips", []):
            v = vid_of(c.get("youtube"))
            if v and v not in seen:
                seen.add(v)
                out[v] = {"id": v, "url": c["youtube"], "title": c.get("title"), "jid": jid, "cid": c["id"], "posted": None,
                          "meta": meta_of(jid, c["id"]), "tags": c.get("tags") or []}
    return out

# ---------------------------------------------------------------- statistics

def _ytdlp_stats(v):
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True, "socket_timeout": 12}) as y:
            i = y.extract_info("https://www.youtube.com/watch?v=" + v, download=False)
        d = i.get("upload_date")
        return {"views": int(i.get("view_count") or 0), "likes": int(i.get("like_count") or 0),
                "comments": int(i.get("comment_count") or 0), "privacy": "public",
                "published": f"{d[:4]}-{d[4:6]}-{d[6:8]}T12:00:00Z" if d else None}
    except Exception:
        return None

def refresh(force=False):
    """Fetch fresh numbers for every posted clip. Safe to call often: skips if checked in the last 20 minutes."""
    db = _load()
    if _busy["stats"] or (not force and time.time() - db.get("fetched", 0) < 1200): return
    _busy["stats"] = True
    def run():
        try:
            from . import youtube
            ids = list(tracked().keys()); got = {}; err = ""
            if ids and youtube.can_read():
                try: got = youtube.videos_stats(ids)
                except Exception as e: err = str(e)[:160]
            for v in ids:
                if v not in got:
                    s = _ytdlp_stats(v)                           # works for public and unlisted videos
                    got[v] = s if s else {"privacy": "unreadable"}
            now = time.time()
            for v, s in got.items():
                row = db["videos"].setdefault(v, {"history": []})
                if s.get("views") is not None:
                    row.update(s); row["history"] = (row.get("history", []) + [[int(now), s["views"]]])[-60:]
                else: row["privacy"] = s.get("privacy")
                row["fetched"] = now
            db["fetched"] = now; db["error"] = err
            _save()
        finally: _busy["stats"] = False
    threading.Thread(target=run, daemon=True).start()

# ---------------------------------------------------------------- learning

def _pct(vals):
    s = sorted(vals); n = len(s)
    return lambda x: 0.5 if n < 2 else sum(1 for y in s if y < x) / (n - 1) + 0.0
def _bucket_dur(d): return None if not d else "under 20 s" if d < 20 else "20 to 35 s" if d < 35 else "35 to 50 s" if d < 50 else "over 50 s"
def _bucket_score(s):
    try: s = float(s)
    except Exception: return None
    return "AI score 85+" if s >= 85 else "AI score 70 to 84" if s >= 70 else "AI score under 70"
def _bucket_hour(t):
    if not t: return None
    h = time.localtime(t).tm_hour
    return "posted in the morning" if 5 <= h < 12 else "posted in the afternoon" if h < 18 and h >= 12 else "posted in the evening" if 18 <= h < 24 else "posted at night"

def features(v):
    m = v.get("meta") or {}; t = (v.get("title") or "")
    w = re.findall(r"\w+", t)
    f = {"length": _bucket_dur(m.get("dur")), "crop": m["layout"] if m.get("layout") else None,
         "type": ("video type: " + m["mode"]) if m.get("mode") else None, "score": _bucket_score(m.get("score")),
         "time": _bucket_hour(v.get("posted")),
         "title_len": None if not w else ("short titles (1 to 4 words)" if len(w) <= 4 else "medium titles (5 to 7 words)" if len(w) <= 7 else "long titles (8+ words)"),
         "number": "numbers in the title" if re.search(r"\d", t) else "no numbers in the title",
         "question": "a question in the title" if "?" in t else None,
         "caps": "a word in CAPS in the title" if re.search(r"\b[A-Z]{3,}\b", t) else None,
         "narr": "narration on" if m.get("narration") else "narration off",
         "tags": "5+ tags" if len(v.get("tags") or []) >= 5 else "few tags"}
    return {k: x for k, x in f.items() if x}

def board():
    """Joined list of posted clips with their numbers and a performance score from 0 to 100."""
    db = _load(); tr = tracked(); rows = []
    for v, t in tr.items():
        s = db["videos"].get(v, {})
        r = {**t, "views": s.get("views"), "likes": s.get("likes"), "comments": s.get("comments"),
             "privacy": s.get("privacy"), "published": s.get("published"), "fetched": s.get("fetched")}
        pub = None
        try: pub = time.mktime(time.strptime(s["published"][:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        except Exception: pub = t.get("posted")
        r["age_days"] = max((time.time() - pub) / 86400, 0.02) if pub else None
        if r["views"] is not None and r["age_days"]:
            r["per_day"] = r["views"] / max(r["age_days"], 1)
            r["engagement"] = (r["likes"] + 2 * r["comments"]) / max(r["views"], 1) * 100
        rows.append(r)
    ok = [r for r in rows if r.get("per_day") is not None]
    if len(ok) >= 2:
        a, b = _pct([r["per_day"] for r in ok]), _pct([r["engagement"] for r in ok])
        for r in ok: r["perf"] = round(100 * (0.65 * a(r["per_day"]) + 0.35 * b(r["engagement"])))
    for r in rows: r["feat"] = features(r)
    return rows

TEXT = {"length": "Clips of {v}", "crop": "Clips using the {v} crop", "type": "Clips from {v}", "score": "Clips with {v}",
        "time": "Clips {v}", "title_len": "Clips with {v}", "number": "Clips with {v}", "question": "Clips with {v}",
        "caps": "Clips with {v}", "narr": "Clips with {v}", "tags": "Clips with {v}"}

def analyse():
    rows = board(); ok = [r for r in rows if r.get("perf") is not None]
    out = {"videos": rows, "count": len(rows), "measured": len(ok), "insights": [], "reco": {}, "best": None,
           "totals": {"views": sum(r.get("views") or 0 for r in rows), "likes": sum(r.get("likes") or 0 for r in rows),
                      "comments": sum(r.get("comments") or 0 for r in rows)}}
    rated = [r for r in rows if r.get("views") is not None]
    out["totals"]["engagement"] = round((out["totals"]["likes"] + 2 * out["totals"]["comments"]) / max(out["totals"]["views"], 1) * 100, 2) if rated else None
    out["unreadable"] = sum(1 for r in rows if r.get("views") is None)
    if rated: out["best"] = max(rated, key=lambda r: (r.get("perf") if r.get("perf") is not None else -1, r["views"]))
    n = len(ok)
    out["confidence"] = "none" if n < 3 else "early" if n < 8 else "fair" if n < 20 else "good"
    if n >= 4:
        avg = sum(r["perf"] for r in ok) / n; groups = defaultdict(list)
        for r in ok:
            for k, val in r["feat"].items(): groups[(k, val)].append(r["perf"])
        found = []
        for (k, val), ps in groups.items():
            if len(ps) < 2 or len(ps) > n - 1: continue          # needs a group and a comparison group
            d = sum(ps) / len(ps) - avg
            if abs(d) >= 8: found.append((abs(d) * math.sqrt(len(ps)), k, val, d, len(ps)))
        for _, k, val, d, c in sorted(found, reverse=True)[:6]:
            out["insights"].append({"text": TEXT[k].format(v=val) + (" do better" if d > 0 else " do worse"), "diff": round(d), "n": c, "good": d > 0})
    top = sorted(ok, key=lambda r: -r["perf"])[:max(1, n // 3)] if ok else []
    if top:
        durs = [r["meta"]["dur"] for r in top if (r.get("meta") or {}).get("dur")]
        if durs: out["reco"]["length"] = [int(min(durs)), int(math.ceil(max(durs)))]
        for key, name in (("layout", "crop"), ("mode", "type")):
            c = Counter((r.get("meta") or {}).get(key) for r in top if (r.get("meta") or {}).get(key))
            if c: out["reco"][name] = c.most_common(1)[0][0]
        tc = Counter()
        for r in top:
            for t in r.get("tags") or []: tc[t.lstrip("#").lower()] += 1 + r["perf"] / 100
        out["reco"]["tags"] = [t for t, _ in tc.most_common(8)]
    return out

def _mine():
    """Tags that showed up on the best clips (used to suggest tags and to guide titles)."""
    try:
        a = analyse(); return a
    except Exception:
        return {"reco": {}, "videos": [], "confidence": "none"}

def llm_hint(mode=None):
    """A short note for the moment-rating prompt: what worked for this creator. Empty until there is enough data."""
    from . import settings
    if not settings.get().get("youtube", {}).get("learn", True): return ""
    a = _mine()
    if a.get("confidence") == "none": return ""
    best = sorted([r for r in a["videos"] if r.get("perf") is not None], key=lambda r: -r["perf"])[:3]
    if not best: return ""
    s = "What has worked for this creator so far (their best performing shorts). Prefer moments that resemble them and write titles in a similar style:\n"
    s += "".join(f"- \"{(r['title'] or '')[:80]}\" ({r['views']} views, {r['feat'].get('length', '')})\n" for r in best)
    if a["reco"].get("length"): s += f"Best clip length so far: {a['reco']['length'][0]} to {a['reco']['length'][1]} seconds.\n"
    return s

# ---------------------------------------------------------------- trending tags

def _topic(text):
    t = re.sub(r"[\[\(].*?[\]\)]|[^\w\s]", " ", text or "")
    w = [x for x in t.split() if x.lower() not in STOP]
    return " ".join(w[:6]).strip()

def _norm(tag):
    t = tag.strip().lstrip("#").lower()
    t = re.sub(r"\s+", " ", t)
    return t if 2 <= len(t) <= 30 and not t.isdigit() else ""

def trending(topic, force=False, wait=True):
    """Public tags and hashtags used by popular short videos on the topic (cached for 12 hours)."""
    key = _topic(topic).lower()
    if not key: return {"tags": [], "related": [], "pending": False}
    db = _load(); hit = db["trends"].get(key)
    if hit and not force and time.time() - hit["t"] < 43200: return {**hit, "pending": False}
    if key not in _busy["trend"]:
        _busy["trend"].add(key)
        threading.Thread(target=_fetch_trend, args=(key,), daemon=True).start()
    if not wait: return {**(hit or {"tags": [], "related": []}), "pending": True}
    for _ in range(90):
        time.sleep(0.5)
        if key not in _busy["trend"]: break
    return {**(_load()["trends"].get(key) or {"tags": [], "related": []}), "pending": key in _busy["trend"]}

def _fetch_trend(key):
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True, "socket_timeout": 10, "no_warnings": True}) as y:
            es = y.extract_info(f"ytsearch30:{key} shorts", download=False).get("entries") or []
        shorts = [e for e in es if e.get("id") and (e.get("duration") or 999) <= 180]
        pool, per = [], Counter()
        for e in sorted(shorts or es, key=lambda e: -(e.get("view_count") or 0)):     # at most 2 per channel: one channel's branding is not a trend
            ch = e.get("channel_id") or e.get("channel") or e["id"]
            if per[ch] < 2 and len(pool) < 10: pool.append(e); per[ch] += 1
        chans = {re.sub(r"\W", "", (e.get("channel") or "").lower()) for e in pool}
        def full(e):
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "socket_timeout": 10, "no_warnings": True}) as y:
                    return y.extract_info("https://www.youtube.com/watch?v=" + e["id"], download=False)
            except Exception: return None
        with ThreadPoolExecutor(6) as ex: infos = [i for i in ex.map(full, pool) if i]
        cnt, views, chs = Counter(), Counter(), defaultdict(set)
        kw = set(re.findall(r"\w+", key))
        for i in infos:
            mine = set()
            for t in i.get("tags") or []: mine.add(_norm(t))
            for h in re.findall(r"#([\w-]{2,30})", (i.get("title") or "") + " " + (i.get("description") or "")[:600]): mine.add(_norm(h))
            for t in mine:
                if t and re.sub(r"\W", "", t) not in chans and t not in STOP:
                    chs[t].add(i.get("channel_id") or i.get("uploader_id") or i.get("id")); views[t] += i.get("view_count") or 0
        for t, s in chs.items(): cnt[t] = len(s)
        keep = [{"tag": t, "count": c, "views": views[t]} for t, c in cnt.most_common(60) if c >= 2]         # used by 2+ different channels
        keep += [{"tag": t, "count": c, "views": views[t]} for t, c in cnt.most_common(60) if c == 1 and kw & set(re.findall(r"\w+", t))][:10]
        related = []
        try:
            u = "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=" + urllib.parse.quote(key)
            related = [x for x in json.loads(urllib.request.urlopen(u, timeout=8).read().decode("utf-8", "replace"))[1] if x][:6]
        except Exception: pass
        _load()["trends"][key] = {"t": time.time(), "tags": keep[:25], "related": related,
                                   "sources": [{"title": i.get("title"), "views": i.get("view_count"), "url": i.get("webpage_url")} for i in infos[:5]]}
        _save()
    except Exception as e:
        _load()["trends"][key] = {"t": time.time() - 40000, "tags": [], "related": [], "error": str(e)[:120]}
    finally: _busy["trend"].discard(key)

# ---------------------------------------------------------------- tags for one clip

def suggest(jid, cid, wait=True):
    from . import jobs
    j = jobs.load(jid); c = next((x for x in j["clips"] if str(x["id"]) == str(cid)), {})
    mine = _mine().get("reco", {}).get("tags", [])
    topic = _topic(j.get("title") or "") or _topic(c.get("title") or "")
    tr = trending(topic, wait=wait)
    words = set(re.findall(r"\w+", ((c.get("title") or "") + " " + (j.get("title") or "") + " " + (c.get("text") or "")).lower()))
    items, seen = [], set()
    def add(tag, src, w):
        t = _norm(tag)
        if t and t not in seen: seen.add(t); items.append({"tag": t, "src": src, "w": w})
    for t in c.get("tags") or []: add(t, "clip", 100)
    for t in mine: add(t, "yours", 90)
    for x in tr.get("tags", []):
        rel = any(p in words for p in re.findall(r"\w+", x["tag"]))
        if x["count"] >= 3 or rel: add(x["tag"], "trending", 40 + 10 * x["count"] + (20 if rel else 0))
    for p in tr.get("related", [])[:3]: add(p, "search", 30)
    items.sort(key=lambda i: -i["w"])
    out, used = [], 0
    for i in items:
        if len(out) >= 12 or used + len(i["tag"]) + 3 > 450: continue
        out.append(i); used += len(i["tag"]) + 3
    return {"tags": out, "pending": bool(tr.get("pending")), "topic": topic, "hashtags": ["#" + re.sub(r"\W", "", i["tag"]) for i in out[:3] if re.sub(r"\W", "", i["tag"])]}
