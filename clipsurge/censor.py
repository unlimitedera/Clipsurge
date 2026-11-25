# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Hides curse words: captions show F*** and the title narration only says the first part of the word."""
import math, re
from . import settings

# Word stems (matched at the start of a word, with common endings) and whole words. Matching is on whole words only,
# so ordinary words that merely contain letters of a curse are left alone.
STEMS = ("fuck", "motherfuck", "shit", "bullshit", "bitch", "asshole", "dumbass", "jackass", "dipshit", "douche", "bastard",
         "cunt", "dick", "pussy", "whore", "slut", "faggot", "nigger", "nigga", "retard", "goddamn", "damn", "piss", "wank",
         "mierda", "puta", "joder", "pendejo", "gilipollas", "cabron", "merde", "putain", "connard", "salope",
         "arschloch", "wichser", "fotze", "siktir", "orospu")
WHOLE = {"ass", "asses", "arse", "cock", "cocks", "fag", "fags", "tits", "twat", "prick", "crap", "coño", "carajo", "puto",
         "amk", "piç", "kurwa", "scheiße", "scheisse", "scheiß", "scheiss", "fick", "ficken", "hure", "enculé", "enculer",
         "كس", "كسمك", "كسم", "كسك", "شرموطة", "شرموط", "شرموطه", "منيوك", "منيك", "زبي", "عرص", "متناك", "خول", "قحبة", "قحبه"}
_END = r"(?:s|es|ed|ing|in|er|ers|y|ty|ies|ey|head|heads|face|hole|holes|it|a)?"
_RX = re.compile(r"^(?:" + "|".join(re.escape(s) for s in STEMS) + r")" + _END + "$", re.I)

def _core(tok):
    m = re.match(r"^(\W*)(.*?)(\W*)$", tok, re.S)
    return m.group(1), m.group(2), m.group(3)

def _extra():
    return {w.strip().lower() for w in re.split(r"[,\n;]", settings.get().get("censor", {}).get("words", "")) if w.strip()}

def is_curse(tok, extra=None):
    _, c, _ = _core(tok)
    c = c.lower().replace("*", "")
    if len(c) < 2: return False
    c = re.sub(r"(.)\1{2,}", r"\1", c)                  # "fuuuuck" -> "fuck"
    if c in WHOLE or c in (extra if extra is not None else _extra()): return True
    return bool(_RX.match(c))

def mask(tok):
    """fuck -> f***   Fuck! -> F***!"""
    a, c, b = _core(tok)
    return tok if len(c) < 2 else a + c[0] + "*" * (len(c) - 1) + b

def mask_word(tok, extra=None):
    return mask(tok) if is_curse(tok, extra) else tok

def mask_text(text):
    ex = _extra()
    return " ".join(mask_word(t, ex) for t in (text or "").split(" "))

def spoken(tok):
    """What the narrator says for a curse: only the first part, then a pause. fuck -> fu...   shit -> sh..."""
    a, c, b = _core(tok)
    if c.lower().startswith("motherfuck"): k = 6                 # "mother..."
    else: k = 1 if len(c) <= 3 else 2 if len(c) <= 8 else 3
    return a + c[:min(k, len(c) - 1)] + "..." + b

def narration_text(text):
    ex = _extra()
    return " ".join(spoken(t) if is_curse(t, ex) else t for t in (text or "").split(" "))

def enabled(*layers):
    """clip choice > video choice > Settings. Each layer is 'on', 'off' or empty (follow the next one)."""
    for v in layers:
        if v in ("on", True): return True
        if v in ("off", False): return False
    return bool(settings.get().get("censor", {}).get("enabled"))
