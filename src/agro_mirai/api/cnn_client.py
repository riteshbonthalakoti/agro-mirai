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


def call_cnn_service(image_bytes: bytes, field_id: str, filename: str = "image.jpg") -> dict | None:
    """POSTs the image to ``CNN_SERVICE_URL``'s ``/predict``.

    Returns the parsed JSON body (a ``DiseaseRiskAlert``-shaped dict) on a
    200 response, or ``None`` on anything else — unset base URL, network
    error, timeout, or a non-200 status. Never raises.
    """
    base_url = cnn_service_url()
    if not base_url:
        return None

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/predict",
            files={"image": (filename, image_bytes)},
            data={"field_id": field_id},
            timeout=cnn_service_timeout(),
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        return resp.json()
    except ValueError:
        return None
