"""JWT verification against Supabase Auth (Module 26).

Replaces ``session_auth.py``'s bcrypt+signed-cookie model. Flask is now a
pure resource server: the mobile app authenticates directly against
Supabase Auth (the Supabase RN/JS SDK) and sends the resulting JWT as
``Authorization: Bearer <token>`` on every ``/v2`` request. This module
verifies that token and extracts the farmer id from its ``sub`` claim —
see decisions/0022-supabase-auth-migration.md for the full reasoning.

Verification strategy: direct ``PyJWT`` decode, not the ``supabase-py``
SDK's ``auth.get_user(token)``. The SDK call is a network round trip to
Supabase on every single authenticated request; local verification
(after an initial, cached JWKS fetch) is what every other Supabase-Auth
resource-server integration does and is materially cheaper for an API
that authenticates every ``/v2`` call. Two verification modes are
supported, tried in order, because Supabase projects can be configured
either way and this project's project has not been confirmed to use one
exclusively:

* **Asymmetric (ES256), current Supabase default** — verified via the
  project's JWKS endpoint (``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``),
  fetched once and cached in-process via ``jwt.PyJWKClient``.
* **Legacy HS256 shared secret** — if ``SUPABASE_JWT_SECRET`` is set
  (Project Settings -> API -> JWT Settings -> Legacy JWT Secret), used as
  a fallback for projects still on the legacy signing key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from agro_mirai.api.errors import ApiError

_AUDIENCE = "authenticated"


@dataclass(frozen=True)
class VerifiedUser:
    user_id: str
    email: str | None
    role: str


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        return None
    return PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def _decode(token: str) -> dict:
    hs256_secret = os.environ.get("SUPABASE_JWT_SECRET")
    errors: list[str] = []

    client = _jwks_client()
    if client is not None:
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token, signing_key.key, algorithms=["ES256", "RS256"], audience=_AUDIENCE
            )
        except Exception as e:  # noqa: BLE001 - fall through to HS256 attempt
            errors.append(str(e))

    if hs256_secret:
        try:
            return jwt.decode(
                token, hs256_secret, algorithms=["HS256"], audience=_AUDIENCE
            )
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    raise ApiError(401, "UNAUTHORIZED", "Invalid or expired token: " + "; ".join(errors or ["no verification method configured"]))


def verify_token(token: str) -> VerifiedUser:
    """Raises ApiError(401) on a missing/invalid/expired token."""
    if not token:
        raise ApiError(401, "UNAUTHORIZED", "Missing token")

    payload = _decode(token)
    user_id = payload.get("sub")
    if not user_id:
        raise ApiError(401, "UNAUTHORIZED", "Token missing sub claim")

    # app_metadata is set server-side only (via the Supabase Admin API),
    # unlike user_metadata which the end user can write themselves —
    # role MUST come from here, never user_metadata, or any signed-up
    # farmer could mint themselves an admin token client-side.
    role = (payload.get("app_metadata") or {}).get("role", "farmer")
    email = payload.get("email")
    return VerifiedUser(user_id=user_id, email=email, role=role)


def verify_bearer_token(authorization_header: str | None) -> VerifiedUser:
    """Raises ApiError(401) on any missing/malformed/invalid/expired token."""
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise ApiError(401, "UNAUTHORIZED", "Missing or malformed Authorization header")
    return verify_token(authorization_header[len("Bearer "):].strip())
