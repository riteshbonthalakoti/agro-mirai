"""Session-based auth for the /v2 multi-tenant surface (Module 19).

Distinct from ``auth.py``'s ``require_auth`` (the /v1 shared-``API_KEY``
decorator, which maps every request to the single ``FARMER_ID`` per ADR
0003). This module authenticates via Flask's signed session cookie —
issued at login (``issue_session``), read back on every ``/v2`` request
(``require_session_auth``), and scopes ``g.farmer_id`` to whoever is
actually logged in, enforcing ADR 0003's ownership rule per-farmer for
real instead of via the single-shared-identity shortcut. See
decisions/0017-multi-tenant-v2.md.

No separate session store: Flask's session cookie is itsdangerous-signed
and already tamper-proof; a client cannot forge ``farmer_id``/``role``
without ``FLASK_SECRET_KEY``. Expiry is enforced two ways — Flask's own
cookie ``max-age`` (``PERMANENT_SESSION_LIFETIME``, cookie stops being
sent/accepted after that) and an explicit ``issued_at`` timestamp check
here (``is_expired``), which is what makes expiry unit-testable without
needing to forge or wait out an actual signed cookie.
"""
from datetime import datetime, timedelta, timezone
from functools import wraps

import itsdangerous
from flask import current_app, g, request, session

from agro_mirai.api.errors import ApiError

SESSION_LIFETIME = timedelta(hours=24)
DEFAULT_BEARER_TOKEN_LIFETIME_DAYS = 180
_TOKEN_SALT = "agro-mirai-bearer-token"


def _bearer_token_lifetime() -> timedelta:
    days = current_app.config.get("BEARER_TOKEN_LIFETIME_DAYS", DEFAULT_BEARER_TOKEN_LIFETIME_DAYS)
    return timedelta(days=int(days))


def _serializer():
    return itsdangerous.URLSafeTimedSerializer(current_app.secret_key, salt=_TOKEN_SALT)


def issue_session(farmer_id: str, role: str) -> str:
    """Called on successful login. Overwrites any prior session content.
    Also returns a signed bearer token carrying the same claims as the cookie."""
    session.clear()
    issued_at = datetime.now(timezone.utc).isoformat()
    session["farmer_id"] = farmer_id
    session["role"] = role or "farmer"
    session["issued_at"] = issued_at
    session.permanent = True
    return _serializer().dumps({"farmer_id": farmer_id, "role": role or "farmer", "issued_at": issued_at})


def decode_token(token: str) -> dict | None:
    """Verifies the token's signature and shape. Doesn't check expiry."""
    try:
        data = _serializer().loads(token)
    except itsdangerous.BadSignature:
        return None
    if not isinstance(data, dict) or "farmer_id" not in data or "issued_at" not in data:
        return None
    return data


def clear_session() -> None:
    """Called on logout. Also called internally when a session is found
    expired, so a stale cookie doesn't keep re-triggering the same 401
    check every request."""
    session.clear()


def is_expired(
    issued_at_iso: str, lifetime: timedelta = SESSION_LIFETIME, now: datetime | None = None
) -> bool:
    """Pure function, unit-testable without a real Flask request/response
    cycle or needing to sleep out a real expiry window."""
    now = now or datetime.now(timezone.utc)
    try:
        issued_at = datetime.fromisoformat(issued_at_iso)
    except (TypeError, ValueError):
        return True
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    return (now - issued_at) > lifetime


def require_session_auth(view):
    """Requires a valid, non-expired session: the cookie, or a bearer token.
    Sets g.farmer_id and g.role either way."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        farmer_id = None
        issued_at = None
        role = "farmer"
        lifetime = SESSION_LIFETIME

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            data = decode_token(auth_header[len("Bearer "):].strip())
            if data:
                farmer_id = data.get("farmer_id")
                issued_at = data.get("issued_at")
                role = data.get("role", "farmer")
                lifetime = _bearer_token_lifetime()

        if not farmer_id:
            farmer_id = session.get("farmer_id")
            issued_at = session.get("issued_at")
            role = session.get("role", "farmer")
            lifetime = SESSION_LIFETIME

        if not farmer_id or not issued_at or is_expired(issued_at, lifetime=lifetime):
            clear_session()
            raise ApiError(401, "UNAUTHORIZED", "Not logged in, or session expired")
        g.farmer_id = farmer_id
        g.role = role
        return view(*args, **kwargs)

    return wrapped


def require_admin(view):
    """Requires a valid session (see require_session_auth) AND role ==
    "admin". A logged-in non-admin farmer gets 403, not 401 — they are
    authenticated, just not authorized for this surface."""

    @wraps(view)
    @require_session_auth
    def wrapped(*args, **kwargs):
        if g.role != "admin":
            raise ApiError(403, "FORBIDDEN", "Admin role required")
        return view(*args, **kwargs)

    return wrapped
