# Copyright (c) 2026 unlimitedera. All Rights Reserved.
"""Model connections: any OpenAI-compatible endpoint (LM Studio, Ollama, llama.cpp, vLLM,
OpenRouter, OpenAI, or an agent that exposes /v1/chat/completions). Always optional."""
import json, re, time
import httpx
from . import settings

PRESETS = {
    "lmstudio": {"name": "LM Studio (local)", "base_url": "http://127.0.0.1:1234/v1"},
    "ollama": {"name": "Ollama (local)", "base_url": "http://127.0.0.1:11434/v1"},
    "llamacpp": {"name": "llama.cpp server (local)", "base_url": "http://127.0.0.1:8080/v1"},
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1"},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
    "agent": {"name": "Agent (OpenAI-compatible)", "base_url": "http://127.0.0.1:8642/v1"},
    "custom": {"name": "Custom endpoint", "base_url": ""},
}

def _headers(p):
    return {"Authorization": "Bearer " + p["api_key"]} if p.get("api_key") else {}

def list_models(p):
    r = httpx.get(p["base_url"].rstrip("/") + "/models", headers=_headers(p), timeout=6)
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", []) if "embed" not in m["id"].lower()]

def test(p):
    """Returns {ok, models, model, ms, reply, error}."""
    out = {"ok": False, "models": [], "error": None}
    try:
        out["models"] = list_models(p)
    except Exception as e:
        out["error"] = f"Cannot reach {p['base_url']} ({type(e).__name__})"
        return out
    mid = p.get("model") or (out["models"][0] if out["models"] else None)
    out["model"] = mid
    if not mid:
        out["error"] = "Connected, but no model is loaded"
        return out
    try:
        t = time.time()
        r = httpx.post(p["base_url"].rstrip("/") + "/chat/completions", headers=_headers(p), timeout=120,
                       json={"model": mid, "max_tokens": 16, "messages": [{"role": "user", "content": "Reply with: ok"}]})
        r.raise_for_status()
        out["ms"] = int((time.time() - t) * 1000)
        out["reply"] = re.sub(r"<think>.*?</think>", "", r.json()["choices"][0]["message"]["content"], flags=re.S).strip()[:40]
        out["ok"] = True
    except Exception as e:
        out["error"] = f"Model call failed ({type(e).__name__}: {str(e)[:80]})"
    return out

def provider(role="rating"):
    ai = settings.get()["ai"]
    provs = [p for p in ai["providers"] if p.get("enabled") and p.get("base_url")]
    want = ai["roles"].get(role) or ""
    for p in provs:
        if p["id"] == want:
            return p
    return provs[0] if provs else None

def model_id(role="rating"):
    """Name of the model that would answer, or None when nothing is reachable."""
    p = provider(role)
    if not p:
        return None
    if p.get("model"):
        try:
            list_models(p)
            return p["model"]
        except Exception:
            return None
    try:
        m = list_models(p)
        return m[0] if m else None
    except Exception:
        return None

def chat_json(system, user, max_tokens=2000, role="rating"):
    p = provider(role)
    mid = model_id(role)
    if not p or not mid:
        return None
    try:
        r = httpx.post(p["base_url"].rstrip("/") + "/chat/completions", headers=_headers(p), timeout=180,
                       json={"model": mid, "temperature": 0.3, "max_tokens": max_tokens,
                             "messages": [{"role": "system", "content": system},
                                          {"role": "user", "content": user}]})
        txt = r.json()["choices"][0]["message"]["content"]
        txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
        m = re.search(r"(\[.*\]|\{.*\})", txt, flags=re.S)
        return json.loads(m.group(1)) if m else None
    except Exception:
        return None
