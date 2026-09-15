"""``/v2/auth`` — Name+Phone+OTP auth (Module 27).

Replaces Module 19's email+password auth (and the reverted Module 26
Supabase Auth migration) with the simplest thing that works for a
farmer identified only by name and phone: ``POST /request-otp`` finds-
or-creates the farmer by phone and generates a 6-digit code (logged to
the server's own output, not sent anywhere yet — see
``agro_mirai.auth.otp``'s docstring and
decisions/0023-name-phone-otp-auth.md); ``POST /verify-otp`` checks that
code and, on success, issues the same signed Flask session
(``agro_mirai.api.session_auth.issue_session``) every other ``/v2``
route already expects. ``POST /logout`` is unchanged from Module 19.

The admin-account email+password login path
(``agro_mirai.api.routes.admin_ui``) is untouched — admin accounts stay
provisioned out-of-band with a real password, per
``MANUAL_TEST_GUIDE.md``'s step 8.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from agro_mirai.api.errors import ApiError
from agro_mirai.api.login_rate_limit import otp_request_limiter
from agro_mirai.api.serializers import farmer_to_public_json
from agro_mirai.api.session_auth import issue_session, clear_session
from agro_mirai.auth.otp import otp_store, send_otp
from agro_mirai.auth.validation import validate_name, validate_otp_code, validate_phone
from agro_mirai.persistence.models import Farmer
from agro_mirai.persistence.store import ConflictError
from agro_mirai.voice.interface import V1_LANGUAGES

auth_v2_bp = Blueprint("auth_v2", __name__, url_prefix="/v2/auth")


def _normalize_phone(raw) -> str:
    """Real bug found live: the mobile client sent whatever the farmer
    typed verbatim (e.g. a bare "9123456780") with no country code, while
    every fixture/seeded farmer is stored E.164-style ("+919812345678").
    Two farmers typing the "same" number differently -- with or without
    +91, with spaces/dashes -- would silently become two different
    accounts, and a returning farmer who once registered with +91 could
    never log back in by typing the bare 10 digits. Normalize here, once,
    so request-otp and verify-otp (both call this) always resolve to the
    same key regardless of how it was typed.

    Loose on purpose: only handles the common case (a 10-digit Indian
    mobile number, optionally with spaces/dashes, no country code) --
    anything already carrying a "+" or that doesn't match this shape is
    left alone rather than guessed at.
    """
    phone = (raw or "").strip()
    has_plus = phone.startswith("+")
    cleaned = re.sub(r"[\s\-()]", "", phone)
    if not has_plus and re.fullmatch(r"[6-9]\d{9}", cleaned):
        return f"+91{cleaned}"
    return cleaned


@auth_v2_bp.post("/request-otp")
@otp_request_limiter.limit(lambda: current_app.config["OTP_RATE_LIMIT"])
def request_otp():
    """Find-or-create the farmer by phone, then issue and "send" (log)
    an OTP. Idempotent to call again for the same phone — each call
    overwrites any prior pending code (agro_mirai.auth.otp.OtpStore)."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    phone = _normalize_phone(body.get("phone"))
    name = (body.get("name") or "").strip()
    preferred_language = body.get("preferred_language", "en")

    try:
        validate_phone(phone)
    except ValueError as e:
        raise ApiError(400, "BAD_REQUEST", str(e)) from e

    store = current_app.extensions["data_store"]
    farmer = store.get_farmer_by_phone(phone)
    is_new_farmer = farmer is None

    if farmer is None:
        # First time this phone has ever requested an OTP: name is
        # required so the new farmer record has one.
        try:
            validate_name(name)
        except ValueError as e:
            raise ApiError(400, "BAD_REQUEST", str(e)) from e

        if preferred_language not in V1_LANGUAGES:
            raise ApiError(
                400,
                "BAD_REQUEST",
                f"preferred_language must be one of: {', '.join(sorted(V1_LANGUAGES))}",
            )

        now = datetime.now(timezone.utc)
        farmer = Farmer(
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            name=name,
            preferred_language=preferred_language,
            phone=phone,
            role="farmer",
        )
        try:
            farmer = store.save_farmer(farmer)
        except ConflictError as e:
            raise ApiError(409, "CONFLICT", "Phone already registered") from e

    code = otp_store.issue(phone)
    send_otp(phone, code)

    # Additive field (ADR 0017/0023's additive-only rule): lets the client
    # route a first-time phone to a short profile-completion step after OTP
    # verification, and a returning phone straight to the dashboard, without
    # a second round trip to guess which case it is.
    return jsonify({"phone": phone, "otp_sent": True, "is_new_farmer": is_new_farmer}), 200


@auth_v2_bp.post("/verify-otp")
def verify_otp():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    phone = _normalize_phone(body.get("phone"))
    code = (body.get("otp") or "").strip()

    try:
        validate_phone(phone)
        validate_otp_code(code)
    except ValueError as e:
        raise ApiError(400, "BAD_REQUEST", str(e)) from e

    if not otp_store.verify(phone, code):
        raise ApiError(401, "UNAUTHORIZED", "Invalid or expired OTP")

    store = current_app.extensions["data_store"]
    farmer = store.get_farmer_by_phone(phone)
    if farmer is None:
        # OTP was valid but the farmer record vanished between
        # request-otp and verify-otp (e.g. deleted) -- not a client error
        # to spam retries against, but no session to issue either.
        raise ApiError(401, "UNAUTHORIZED", "No account for this phone number")

    issue_session(farmer.id, farmer.role)
    return jsonify(farmer_to_public_json(farmer)), 200


@auth_v2_bp.post("/logout")
def logout():
    clear_session()
    return jsonify({"ok": True}), 200
