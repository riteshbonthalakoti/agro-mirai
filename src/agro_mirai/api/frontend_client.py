"""In-process HTTP client the frontend blueprint uses to talk to Module
11's JSON API — never imports ``DecisionEngine`` or any model class
directly (see ``decisions/0013-frontend-platform-sequencing.md``).

Uses ``current_app.test_client()`` to issue a real request/response round
trip through the full blueprint/auth/error-handling stack, attaching the
server-held ``API_KEY`` itself so the browser never sees it.
"""
from __future__ import annotations

from flask import current_app


class ApiError(Exception):
    """Raised when the in-process API call returns a non-2xx status."""

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload
        message = (payload or {}).get("error", {}).get("message", "API error")
        super().__init__(f"{status_code}: {message}")


def _headers() -> dict:
    return {"Authorization": f"Bearer {current_app.config['API_KEY']}"}


def api_get(path: str) -> dict:
    client = current_app.test_client()
    resp = client.get(path, headers=_headers())
    body = resp.get_json(silent=True) or {}
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, body)
    return body


def api_post(path: str, json_body: dict) -> tuple[dict, int]:
    client = current_app.test_client()
    resp = client.post(path, json=json_body, headers=_headers())
    body = resp.get_json(silent=True) or {}
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, body)
    return body, resp.status_code
