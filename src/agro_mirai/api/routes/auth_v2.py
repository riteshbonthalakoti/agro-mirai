"""``/v2/auth`` — registration, login, logout (Module 19).

Real login/session auth, not a token-in-a-cookie shortcut: registration
validates a real password strength policy and hashes via bcrypt
(``agro_mirai.auth``), login verifies the hash and issues a signed Flask
session (``agro_mirai.api.session_auth.issue_session``), logout clears
it. The login route is rate-limited specifically (on top of Module 16's
general per-key limit) — see ``_configure_login_rate_limit`` in
``api/app.py``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from agro_mirai.api.errors import ApiError
from agro_mirai.api.login_rate_limit import login_limiter
from agro_mirai.api.serializers import farmer_to_public_json
from agro_mirai.api.session_auth import clear_session, issue_session
from agro_mirai.auth.password import hash_password, verify_password
from agro_mirai.auth.validation import validate_email, validate_name, validate_password_strength
from agro_mirai.persistence.models import Farmer
from agro_mirai.persistence.store import ConflictError
from agro_mirai.voice.interface import V1_LANGUAGES

auth_v2_bp = Blueprint("auth_v2", __name__, url_prefix="/v2/auth")


@auth_v2_bp.post("/register")
def register():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    name = (body.get("name") or "").strip()
    preferred_language = body.get("preferred_language", "en")

    try:
        validate_email(email)
        validate_password_strength(password)
        validate_name(name)
    except ValueError as e:
        raise ApiError(400, "BAD_REQUEST", str(e)) from e

    # Module 25: registration previously accepted any string here
    # unvalidated (a real gap — the Farmer/RegisterRequest openapi schema
    # already declared an enum). Validated against V1_LANGUAGES, the set
    # this backend's voice stack can actually act on, not the broader
    # aspirational enums.md/openapi language_code list.
    if preferred_language not in V1_LANGUAGES:
        raise ApiError(
            400,
            "BAD_REQUEST",
            f"preferred_language must be one of: {', '.join(sorted(V1_LANGUAGES))}",
        )

    store = current_app.extensions["data_store"]
    if store.get_farmer_by_email(email) is not None:
        raise ApiError(409, "CONFLICT", "Email already registered")

    now = datetime.now(timezone.utc)
    farmer = Farmer(
        id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        name=name,
        preferred_language=preferred_language,
        email=email,
        password_hash=hash_password(password),
        role="farmer",
    )
    try:
        saved = store.save_farmer(farmer)
    except ConflictError as e:
        raise ApiError(409, "CONFLICT", "Email already registered") from e

    return jsonify(farmer_to_public_json(saved)), 201


@auth_v2_bp.post("/login")
@login_limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    store = current_app.extensions["data_store"]
    farmer = store.get_farmer_by_email(email) if email else None
    if farmer is None or not verify_password(password, farmer.password_hash):
        raise ApiError(401, "UNAUTHORIZED", "Invalid email or password")

    issue_session(farmer.id, farmer.role)
    return jsonify(farmer_to_public_json(farmer)), 200


@auth_v2_bp.post("/logout")
def logout():
    clear_session()
    return jsonify({"ok": True}), 200
