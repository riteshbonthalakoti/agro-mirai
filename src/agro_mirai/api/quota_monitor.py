"""Checks real remaining free-tier quota on every OpenRouter/Groq key
pool this project uses (Module 60) -- the thing tools/quota_alert_sweep.py
runs periodically to email the admin before a pool actually runs dry.

Three logical pools, each backed by an OpenRouter sub-pool and a Groq
sub-pool (same KeyPool env-var convention used everywhere else in this
project -- see api/key_pool.py):

- "chat"   -- OPENROUTER_CHAT_API_KEY_*  / GROQ_CHAT_API_KEY_*
- "scan"   -- OPENROUTER_VISION_API_KEY_* / GROQ_VISION_API_KEY_*
- "voice"  -- OPENROUTER_API_KEY_*       / GROQ_API_KEY_*

OpenRouter's own ``/auth/key`` endpoint reports real daily free-model
usage without costing a request against that quota. Groq has no such
metadata endpoint -- its remaining-requests count only comes back as a
response header on a real (cheap, 1-token) completion call, so checking
a Groq key costs it exactly one of its ~1000 daily requests.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

_OPENROUTER_AUTH_URL = "https://openrouter.ai/api/v1/auth/key"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT_S = 12.0
_MAX_KEYS = 9

# One cheap, known-good model per Groq pool, just to get rate-limit headers back.
_GROQ_PROBE_MODEL = {
    "chat": "openai/gpt-oss-20b",
    "scan": "qwen/qwen3.8-27b",
    "voice": "openai/gpt-oss-20b",
}

POOLS = {
    "chat": {"label": "Chatbot", "openrouter_prefix": "OPENROUTER_CHAT_API_KEY", "groq_prefix": "GROQ_CHAT_API_KEY"},
    "scan": {"label": "Scan Leaf (vision)", "openrouter_prefix": "OPENROUTER_VISION_API_KEY", "groq_prefix": "GROQ_VISION_API_KEY"},
    "voice": {"label": "Voice/STT", "openrouter_prefix": "OPENROUTER_API_KEY", "groq_prefix": "GROQ_API_KEY"},
}


def _configured_keys(env_prefix: str) -> list[str]:
    return [
        key
        for i in range(1, _MAX_KEYS + 1)
        if (key := os.environ.get(f"{env_prefix}_{i}", "").strip())
    ]


def _check_openrouter_key(key: str) -> dict | None:
    try:
        resp = requests.get(_OPENROUTER_AUTH_URL, headers={"Authorization": f"Bearer {key}"}, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        fmdr = resp.json().get("data", {}).get("free_model_daily_requests", {})
        used, limit = fmdr.get("used"), fmdr.get("limit")
        if used is None or not limit:
            return None
        return {"used": used, "limit": limit, "remaining": fmdr.get("remaining", limit - used)}
    except Exception as exc:  # noqa: BLE001 -- a monitoring check must never raise
        logger.warning("quota_monitor: OpenRouter key check failed: %s", exc)
        return None


def _check_groq_key(key: str, model: str) -> dict | None:
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=_TIMEOUT_S,
        )
        limit = resp.headers.get("x-ratelimit-limit-requests")
        remaining = resp.headers.get("x-ratelimit-remaining-requests")
        if limit is None or remaining is None:
            return None
        limit, remaining = int(limit), int(remaining)
        return {"used": limit - remaining, "limit": limit, "remaining": remaining}
    except Exception as exc:  # noqa: BLE001
        logger.warning("quota_monitor: Groq key check failed: %s", exc)
        return None


def check_pool(pool_name: str) -> dict:
    """Combined remaining/limit across every configured key (both
    providers) in one logical pool, plus the per-key breakdown."""
    cfg = POOLS[pool_name]
    keys_detail = []
    total_remaining = 0
    total_limit = 0

    for key in _configured_keys(cfg["openrouter_prefix"]):
        r = _check_openrouter_key(key)
        if r:
            keys_detail.append({"provider": "openrouter", "suffix": key[-6:], **r})
            total_remaining += r["remaining"]
            total_limit += r["limit"]

    for key in _configured_keys(cfg["groq_prefix"]):
        r = _check_groq_key(key, _GROQ_PROBE_MODEL[pool_name])
        if r:
            keys_detail.append({"provider": "groq", "suffix": key[-6:], **r})
            total_remaining += r["remaining"]
            total_limit += r["limit"]

    pct_remaining = round(100 * total_remaining / total_limit, 1) if total_limit else None
    return {
        "pool": pool_name,
        "label": cfg["label"],
        "total_remaining": total_remaining,
        "total_limit": total_limit,
        "pct_remaining": pct_remaining,
        "keys": keys_detail,
    }


def check_all_pools() -> dict[str, dict]:
    return {name: check_pool(name) for name in POOLS}
