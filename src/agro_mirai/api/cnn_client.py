"""HTTP client for the standalone CNN inference service
(``services/cnn-inference``), Module 21.

Uses ``requests`` — the same HTTP client Module 03's acquisition adapters
(``acquisition/open_meteo.py``, ``acquisition/soilgrids.py``) already use
for outbound calls, kept consistent here rather than introducing a new
dependency. ``call_cnn_service`` never raises for a reachability problem
(timeout, connection refused, non-2xx, malformed response) — it returns
``None`` so the caller can apply the hard fallback-to-rule-based
requirement (never a 500) without a try/except at every call site.
"""
from __future__ import annotations

import os

import requests

DEFAULT_TIMEOUT_S = 15


def cnn_service_url() -> str | None:
    url = os.environ.get("CNN_SERVICE_URL", "").strip()
    return url or None


def cnn_service_timeout() -> float:
    raw = os.environ.get("CNN_SERVICE_TIMEOUT_S", "")
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _auth_headers() -> dict[str, str]:
    """Shared secret for a publicly reachable CNN service (e.g. a Hugging Face
    Space): sent as X-Service-Token when CNN_SERVICE_TOKEN is set."""
    token = os.environ.get("CNN_SERVICE_TOKEN", "").strip()
    return {"X-Service-Token": token} if token else {}


def call_cnn_service(
    image_bytes: bytes, field_id: str, filename: str = "image.jpg", crop_type: str | None = None
) -> dict | None:
    """POSTs the image to ``CNN_SERVICE_URL``'s ``/predict``.

    Returns the parsed JSON body (a ``DiseaseRiskAlert``-shaped dict) on a
    200 response, or ``None`` on anything else — unset base URL, network
    error, timeout, or a non-200 status. Never raises.

    Retries once on a network-level failure (timeout/connection error) only
    — never on an application response (a real 4xx/5xx or bad JSON retries
    just as pointlessly a second time). This exists because the free-tier
    service can be mid-cold-start (single worker) when the first request
    lands, e.g. right behind this process's own background /health warm-up
    ping; a second attempt a moment later reaches an already-warm worker.
    """
    base_url = cnn_service_url()
    if not base_url:
        return None

    last_exc: requests.RequestException | None = None
    for attempt in range(2):
        try:
            resp = requests.post(
                f"{base_url.rstrip('/')}/predict",
                files={"image": (filename, image_bytes)},
                data={"field_id": field_id, **({"crop": crop_type} if crop_type else {})},
                headers=_auth_headers(),
                timeout=cnn_service_timeout(),
            )
            break
        except requests.RequestException as exc:
            last_exc = exc
            continue
    else:
        return None  # both attempts failed at the network level

    if resp.status_code != 200:
        return None

    try:
        return resp.json()
    except ValueError:
        return None
