"""Render REST API client for the admin OTP-lookup backup path (Module 57).

Reads the ``otp_issued`` log line auth_v2.py writes on every OTP send,
straight out of Render's own log stream -- no new storage, no OTP ever
written anywhere but the server's existing logs. Needs RENDER_API_KEY
(a Render account API key, not a farmer/admin credential) and
RENDER_SERVICE_ID (this service's own Render service id, so it reads its
own logs) as env vars; returns None for any failure (missing config,
network, non-200) so the route can turn that into a clean 404 rather
than a 500.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

_LOGS_URL = "https://api.render.com/v1/logs"
_TIMEOUT_S = 10.0
_OTP_LINE = re.compile(r"otp_issued phone=(?P<phone>\S+) otp=(?P<otp>\d+) ts=(?P<ts>\S+)")


def find_latest_otp(phone: str, lookback_limit: int = 300) -> dict | None:
    """Most recent ``otp_issued`` log line for ``phone``, or ``None`` if
    none is found in the last ``lookback_limit`` log lines (default 300
    is comfortably more than the busiest realistic 15-minute window) or
    Render isn't reachable/configured. Logs are already newest-first
    (direction=backward), so the first match is the latest."""
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    owner_id = os.environ.get("RENDER_OWNER_ID", "").strip()
    if not api_key or not service_id or not owner_id:
        return None

    params = urlencode([
        ("resource", service_id),
        ("ownerId", owner_id),
        ("limit", str(lookback_limit)),
        ("direction", "backward"),
        ("text", "otp_issued"),
    ])
    try:
        resp = requests.get(
            f"{_LOGS_URL}?{params}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT_S,
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    try:
        logs = resp.json().get("logs", [])
    except ValueError:
        return None

    for entry in logs:
        m = _OTP_LINE.search(entry.get("message", ""))
        if m and m.group("phone") == phone:
            return {"phone": phone, "otp": m.group("otp"), "issued_at": m.group("ts")}
    return None


def seconds_old(issued_at_iso: str) -> int | None:
    try:
        issued = datetime.fromisoformat(issued_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return int((datetime.now(timezone.utc) - issued).total_seconds())
