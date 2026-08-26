"""Bearer API-key auth.

Not OAuth, not JWT — a single shared key (``API_KEY`` env var) checked
against the ``Authorization: Bearer <key>`` header. Per ADR 0003
(single-farmer-per-account), the key maps to exactly one ``farmer_id``
(``FARMER_ID`` env var); there is no per-user key store yet.
"""
from __future__ import annotations

from functools import wraps

from flask import current_app, g, request

from agro_mirai.api.errors import ApiError


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError(401, "UNAUTHORIZED", "Missing bearer token")
        token = header[len("Bearer "):].strip()
        expected = current_app.config["API_KEY"]
        if not expected or token != expected:
            raise ApiError(401, "UNAUTHORIZED", "Invalid API key")
        g.farmer_id = current_app.config["FARMER_ID"]
        return view(*args, **kwargs)

    return wrapped
