"""JWT-based auth for the ``/v2`` multi-tenant surface (Module 26).

Supersedes the bcrypt+Flask-signed-session model built in Module 19 —
see decisions/0022-supabase-auth-migration.md. The mobile app talks
directly to Supabase Auth (via the Supabase SDK) and sends the resulting
JWT as ``Authorization: Bearer <token>`` on every ``/v2`` request;
``require_session_auth``/``require_admin`` verify that token
(``jwt_auth.verify_bearer_token``) and scope ``g.farmer_id`` to the
token's ``sub`` claim — the real Supabase-issued user id, not a value a
client could ever forge without Supabase's own signing key.

No custom session cookie is issued for API callers any more. The one
exception is the server-rendered ``/admin`` browser dashboard
(``routes/admin_ui.py``), which has no SDK of its own to hold a token in
JS state between page loads: it stores the Supabase-issued access token
inside Flask's own signed session cookie (itsdangerous-signed, so a
client still can't forge or read it) purely as browser-side storage —
the token itself is still verified the same way, through
``jwt_auth.verify_token``, on every request. ``require_session_auth``
checks the ``Authorization`` header first (the API/mobile path) and
falls back to the session-stored token (the browser path) so both
surfaces share one verification function.
"""
from __future__ import annotations

from functools import wraps

from flask import g, request, session

from agro_mirai.api.errors import ApiError
from agro_mirai.api.jwt_auth import VerifiedUser, verify_token


def issue_browser_session(access_token: str) -> None:
    """Called after a successful /admin login (routes/admin_ui.py), which
    obtains the token via a server-side Supabase password-grant call, not
    via any custom credential check of our own."""
    session.clear()
    session["access_token"] = access_token
    session.permanent = True


def clear_session() -> None:
    session.clear()


def _resolve_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return session.get("access_token")


def _ensure_farmer_profile(verified: VerifiedUser):
    """Auto-provisions a Farmer row on first authenticated request for a
    Supabase user this backend has never seen — registration now happens
    entirely on the Supabase side (direct SDK), so Flask has no
    /v2/auth/register hook to create the profile row at signup time.
    Farmer.id IS the Supabase auth.users.id (Module 26 re-keying — see
    the ADR): no separate mapping column was needed.
    """
    from datetime import datetime, timezone

    from flask import current_app

    from agro_mirai.persistence.models import Farmer

    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(verified.user_id)
    if farmer is not None:
        return farmer

    now = datetime.now(timezone.utc)
    farmer = Farmer(
        id=verified.user_id,
        created_at=now,
        updated_at=now,
        name=(verified.email or "").split("@")[0] or "Farmer",
        preferred_language="en",
        email=verified.email,
        role=verified.role,
    )
    return store.save_farmer(farmer)


def require_session_auth(view):
    """Requires a valid Supabase-issued JWT (header or browser session).
    Sets g.farmer_id and g.role from the verified token, auto-provisioning
    the Farmer profile row on first sight of a given Supabase user."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        token = _resolve_token()
        if not token:
            raise ApiError(401, "UNAUTHORIZED", "Not logged in, or session expired")
        try:
            verified = verify_token(token)
        except ApiError:
            clear_session()
            raise
        _ensure_farmer_profile(verified)
        g.farmer_id = verified.user_id
        g.role = verified.role
        return view(*args, **kwargs)

    return wrapped


def require_admin(view):
    """Requires a valid token (see require_session_auth) AND role ==
    "admin". A logged-in non-admin farmer gets 403, not 401 — they are
    authenticated, just not authorized for this surface."""

    @wraps(view)
    @require_session_auth
    def wrapped(*args, **kwargs):
        if g.role != "admin":
            raise ApiError(403, "FORBIDDEN", "Admin role required")
        return view(*args, **kwargs)

    return wrapped
