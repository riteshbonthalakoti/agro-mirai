"""Liveness endpoint — public, no auth."""
from __future__ import annotations

import threading
import time

import requests
from flask import Blueprint, current_app, jsonify

from agro_mirai.api.cnn_client import cnn_service_url

health_bp = Blueprint("health", __name__)

_WARM_EVERY_S = 300
_last_warm = 0.0
_warm_lock = threading.Lock()


def _warm_cnn_service(base_url: str) -> None:
    try:
        requests.get(f"{base_url.rstrip('/')}/health", timeout=120)
    except requests.RequestException:
        pass


def _maybe_warm_cnn_service() -> None:
    """The photo-disease service runs on its own free Render instance that
    sleeps when idle. The app pings this /health when it opens, so use that to
    wake the photo service in the background (at most every 5 minutes) — by the
    time the farmer takes a leaf photo it is ready instead of timing out."""
    global _last_warm
    url = cnn_service_url()
    if not url:
        return
    with _warm_lock:
        now = time.monotonic()
        if now - _last_warm < _WARM_EVERY_S:
            return
        _last_warm = now
    threading.Thread(target=_warm_cnn_service, args=(url,), daemon=True).start()


@health_bp.get("/health")
def health():
    store = current_app.extensions["data_store"]
    ok = store.ping()
    if not current_app.config.get("TESTING"):
        _maybe_warm_cnn_service()
    return jsonify({"status": "ok" if ok else "degraded"}), 200
