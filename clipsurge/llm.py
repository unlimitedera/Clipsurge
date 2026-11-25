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
    "anthropic": {"name": "Claude (Anthropic API)", "base_url": "https://api.anthropic.com/v1"},
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
        if not p.get("model"):   # some providers hide /models: a typed model name is enough
            out["error"] = f"Cannot list models at {p['base_url']} ({type(e).__name__}). Type a model name and test again."
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
        return p["model"]   # typed by the user: trust it, calls fail softly if wrong
    try:
        m = list_models(p)
        return m[0] if m else None
    except Exception:
        return None

def _chat(p, mid, messages, max_tokens, temperature=0.3):
    """Chat call. Asks reasoning models (Qwen, etc.) not to think out loud: otherwise they spend the
    whole token budget on hidden reasoning and return an empty answer. Retries without the hint
    for servers that reject it."""
    url = p["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": mid, "temperature": temperature, "max_tokens": max_tokens, "messages": messages}
    r = httpx.post(url, headers=_headers(p), timeout=180, json={**body, "reasoning_effort": "none"})
    if r.status_code == 400:
        r = httpx.post(url, headers=_headers(p), timeout=180, json=body)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""

def stream_chat(messages, role="rating", max_tokens=1400, temperature=0.6):
    """Yields the answer piece by piece. Hidden reasoning (<think>...</think>) is never shown."""
    p = provider(role); mid = model_id(role)
    if not p or not mid:
        yield "No AI model is connected. Add one under Settings > AI and agents (LM Studio, Ollama, or a model Clipsurge runs for you), then ask again."
        return
    url = p["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": mid, "temperature": temperature, "max_tokens": max_tokens, "messages": messages, "stream": True}
    try:
        for extra in ({"reasoning_effort": "none"}, {}):
            with httpx.stream("POST", url, headers=_headers(p), json={**body, **extra}, timeout=httpx.Timeout(180, connect=8)) as r:
                if r.status_code == 400 and extra:
                    continue                               # this server does not know reasoning_effort
                if r.status_code >= 400:
                    r.read(); yield f"The model returned an error ({r.status_code}): {r.text[:160]}"; return
                buf, hidden, got = "", False, False
                for line in r.iter_lines():
                    if not line.startswith("data:"): continue
                    d = line[5:].strip()
                    if d == "[DONE]": break
                    try: piece = json.loads(d)["choices"][0].get("delta", {}).get("content") or ""
                    except Exception: continue
                    buf += piece
                    while True:                            # drop <think> blocks, even when split across chunks
                        if hidden:
                            k = buf.find("</think>")
                            if k < 0: buf = buf[-8:]; break
                            buf = buf[k + 8:]; hidden = False
                        else:
                            k = buf.find("<think>")
                            if k >= 0:
                                if buf[:k]: got = True; yield buf[:k]
                                buf = buf[k + 7:]; hidden = True
                            else:
                                keep = 7 if buf.endswith(("<", "<t", "<th", "<thi", "<thin", "<think")) else 0
                                out, buf = (buf[:-keep], buf[-keep:]) if keep else (buf, "")
                                if out: got = True; yield out
                                break
                if buf and not hidden: got = True; yield buf
                if not got: yield "(The model sent an empty answer. Try again, or use a model that is not a reasoning model.)"
                return
    except httpx.ConnectError:
        yield f"Cannot reach the model at {p['base_url']}. Is it running?"
    except Exception as e:
        yield f"The model call failed ({type(e).__name__}: {str(e)[:120]})"

def chat_json(system, user, max_tokens=2000, role="rating"):
    p = provider(role)
    mid = model_id(role)
    if not p or not mid:
        return None
    try:
        txt = _chat(p, mid, [{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens)
        txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
        m = re.search(r"(\[.*\]|\{.*\})", txt, flags=re.S)
        return json.loads(m.group(1)) if m else None
    except Exception:
        return None
