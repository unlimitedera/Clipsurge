# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Local LLM (LM Studio / any OpenAI-compatible server). Always optional."""
import json, re
import httpx
from .config import LLM_URL

def model_id():
    try:
        r = httpx.get(LLM_URL + "/models", timeout=3)
        ids = [m["id"] for m in r.json().get("data", [])]
        ids = [i for i in ids if "embed" not in i.lower()]
        return ids[0] if ids else None
    except Exception:
        return None

def chat_json(system, user, max_tokens=2000):
    mid = model_id()
    if not mid:
        return None
    try:
        r = httpx.post(LLM_URL + "/chat/completions", timeout=180, json={
            "model": mid, "temperature": 0.3, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]})
        txt = r.json()["choices"][0]["message"]["content"]
        txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
        m = re.search(r"(\[.*\]|\{.*\})", txt, flags=re.S)
        return json.loads(m.group(1)) if m else None
    except Exception:
        return None
