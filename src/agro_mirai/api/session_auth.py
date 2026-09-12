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
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import g, session

from agro_mirai.api.errors import ApiError

SESSION_LIFETIME = timedelta(hours=24)


def issue_session(farmer_id: str, role: str) -> None:
    """Called on successful login. Overwrites any prior session content."""
    session.clear()
    session["farmer_id"] = farmer_id
    session["role"] = role or "farmer"
    session["issued_at"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True


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
    """Requires a valid, non-expired session cookie. Sets g.farmer_id and
    g.role. Every /v2 route (other than register/login) that touches
    farmer-owned data uses this, never the raw session dict directly, so
    the expiry check can't accidentally be skipped."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        farmer_id = session.get("farmer_id")
        issued_at = session.get("issued_at")
        if not farmer_id or not issued_at or is_expired(issued_at):
            clear_session()
            raise ApiError(401, "UNAUTHORIZED", "Not logged in, or session expired")
        g.farmer_id = farmer_id
        g.role = session.get("role", "farmer")
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
