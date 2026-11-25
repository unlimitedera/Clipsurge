# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Internet lookups for SurgeAI: trending tags, what people search, top videos on a topic, web search, and reading a page the user pastes.
Only public data, read only, short timeouts. Nothing from the user's account or files is sent except the search words."""
import json, re, urllib.parse, urllib.request, html as _html, time
from . import insights

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
_cache = {}

def _get(url, timeout=10, limit=400000):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
    return r.read(limit).decode("utf-8", "replace")

def enabled():
    try:
        from . import settings
        return bool(settings.get().get("surgeai", {}).get("web", False))
    except Exception: return True

def suggestions(q):
    try:
        u = "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=" + urllib.parse.quote(q)
        return [x for x in json.loads(_get(u, 8))[1] if x][:8]
    except Exception: return []

def search(q, n=5):
    """General web search through Bing's plain page, with Google News as a second source."""
    import base64
    out = []
    try:
        h = _get("https://www.bing.com/search?q=" + urllib.parse.quote_plus(q) + "&setlang=en&cc=US&mkt=en-US", 12)
        cl = lambda x: _html.unescape(re.sub(r"<.*?>", "", x)).strip()
        for b in h.split('<li class="b_algo"')[1:n + 3]:
            m = re.search(r'<h2[^>]*><a[^>]*href="([^"]+)"', b); u = _html.unescape(m.group(1)) if m else ""
            if "bing.com/ck/" in u:
                mm = re.search(r"[?&]u=a1([^&]+)", u)
                try: u = base64.urlsafe_b64decode(mm.group(1) + "=" * (-len(mm.group(1)) % 4)).decode() if mm else ""
                except Exception: u = ""
            ti = re.search(r"<h2.*?</h2>", b, re.S); sn = re.search(r"<p[^>]*>(.*?)</p>", b, re.S)
            if u.startswith("http") and ti: out.append({"title": cl(ti.group(0)), "url": u, "snippet": cl(sn.group(1))[:240] if sn else ""})
            if len(out) >= n: break
    except Exception: pass
    if len(out) < 3:
        try:
            x = _get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en", 10)
            for m in re.finditer(r"<item><title>(.*?)</title><link>(.*?)</link>", x):
                out.append({"title": _html.unescape(m.group(1)), "url": m.group(2), "snippet": "news"})
                if len(out) >= n: break
        except Exception: pass
    return out

def page_text(url, n=3500):
    try:
        h = _get(url, 12)
        h = re.sub(r"(?is)<(script|style|noscript|svg|head).*?</\1>", " ", h)
        t = _html.unescape(re.sub(r"<[^>]+>", " ", h)); t = re.sub(r"\s+", " ", t).strip()
        return t[:n]
    except Exception as e: return ""

def top_videos(topic, n=6):
    """Most viewed recent public videos on a topic: title, channel, views, length."""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True, "socket_timeout": 10, "no_warnings": True}) as y:
            es = y.extract_info(f"ytsearch15:{topic} shorts", download=False).get("entries") or []
        es = sorted([e for e in es if e.get("id")], key=lambda e: -(e.get("view_count") or 0))[:n]
        return [{"title": e.get("title"), "channel": e.get("channel"), "views": e.get("view_count"), "len": e.get("duration"), "url": "https://youtu.be/" + e["id"]} for e in es]
    except Exception: return []

def lookup(topic):
    """Everything useful for one topic, cached 30 minutes."""
    key = insights._topic(topic).lower() or topic.lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 1800: return hit[1]
    tr = insights.trending(key, wait=True)
    d = {"topic": key, "tags": [x["tag"] for x in tr.get("tags", [])][:15], "related": tr.get("related") or suggestions(key), "top": top_videos(key)}
    _cache[key] = (time.time(), d); return d

def _fmt(n):
    n = n or 0
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}K" if n >= 1e3 else str(n)

def context(question, topic, video_title=""):
    """Text for the model's briefing + a list of sources for the reader. Empty when nothing was found."""
    q = question or ""; parts = []; src = []
    urls = re.findall(r"https?://[^\s)>\]]+", q)
    for u in urls[:2]:
        t = page_text(u)
        if t: parts.append(f"PAGE {u}: {t}"); src.append(u)
    want_web = re.search(r"\b(search|google|look up|lookup|find out|latest|news|today|this week|right now|current|online|internet|web)\b", q, re.I)
    if want_web and not urls:
        sq = re.sub(r"(?i)\b(can you|could you|please|search( the)?( web| internet)?( for)?|google|look up|online)\b", " ", q).strip(" ?.")[:120] or topic
        rs = search(sq)
        if rs:
            parts.append("WEB SEARCH RESULTS: " + " | ".join(f"{r['title']}: {r['snippet']}" for r in rs)); src += [r["url"] for r in rs[:4]]
    d = lookup(topic or video_title or q[:60])
    if d["tags"] or d["top"] or d["related"]:
        parts.append(f"LIVE YOUTUBE DATA for '{d['topic']}': trending tags used by 2+ channels: {' '.join('#' + t.replace(' ', '') for t in d['tags']) or 'none found'}. "
                     f"What people search: {'; '.join(d['related']) or 'n/a'}. "
                     "Most viewed short videos on it: " + " | ".join(f"{(v['title'] or '')[:70]} ({_fmt(v['views'])} views, {v['channel']})" for v in d["top"]))
        src += [v["url"] for v in d["top"][:3]]
    return "\n".join(parts), src

NEEDS_MSG = ("I need internet access for that, and it is turned off. It is off by default: when it is on, I look up trending tags, what people search for, popular videos on your topic and web pages "
             "you paste. Only the search words leave your computer.\n\n[[settings:ai/web|Turn on internet access]]")

def trend_answer(topic):
    d = lookup(topic)
    if not (d["tags"] or d["related"] or d["top"]): return "I could not reach YouTube just now, or nothing came back for that topic. Check your connection and try again."
    o = [f"Here is what I found online for **{d['topic']}**:", ""]
    if d["tags"]: o += ["**Tags used by several popular channels:**", " ".join("#" + x.replace(" ", "") for x in d["tags"][:12]), ""]
    if d["related"]: o += ["**What people search for:**"] + [f"- {x}" for x in d["related"][:6]] + [""]
    if d["top"]: o += ["**Most viewed short videos on it:**"] + [f"- [{(v['title'] or '')[:70]}]({v['url']}) ({_fmt(v['views'])} views, {v['channel']})" for v in d["top"][:5]] + [""]
    o.append("Only use tags that really describe your video. Say **for clip N add tags** and I will pick fitting ones.")
    return "\n".join(o)

def search_answer(q):
    sq = re.sub(r"(?i)\b(can you|could you|please|search( the)?( web| internet)?( for)?|google|look up|online)\b", " ", q).strip(" ?.")[:120] or q
    rs = [r for r in search(sq, 6) if "whatsapp" not in r["url"]][:5]
    vs = top_videos(sq, 4)
    if not rs and not vs: return "I could not get search results just now. Try again in a moment."
    o = [f"Results for **{sq}**:", ""]
    if rs: o += ["**Web:**"] + [f"- [{r['title'][:80]}]({r['url']}){': ' + r['snippet'] if r['snippet'] and r['snippet'] != 'news' else ''}" for r in rs] + [""]
    if vs: o += ["**Most viewed videos on YouTube:**"] + [f"- [{(v['title'] or '')[:70]}]({v['url']}) ({_fmt(v['views'])} views, {v['channel']})" for v in vs] + [""]
    o.append("Web search results can be off-topic, so check the links before relying on them.")
    return "\n".join(o)
