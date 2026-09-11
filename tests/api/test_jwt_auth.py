"""Module 26: JWT verification against Supabase Auth.

Uses the HS256 fallback path (SUPABASE_JWT_SECRET) rather than mocking
the JWKS HTTP fetch — it exercises the exact same claim-validation logic
(_decode -> verify_token) real Supabase-issued ES256 tokens go through,
without needing a live network call or a fake JWKS server in every test
run. test_jwt_auth_jwks_path.py-equivalent JWKS-path coverage is exactly
what tests/api/test_v2_auth_integration.py's live-Supabase-project
integration tests provide instead (see that module's docstring).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from agro_mirai.api.errors import ApiError
from agro_mirai.api.jwt_auth import verify_bearer_token, verify_token

SECRET = "test-only-hs256-secret"


@pytest.fixture(autouse=True)
def _hs256_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from agro_mirai.api.jwt_auth import _jwks_client

    _jwks_client.cache_clear()
    yield
    _jwks_client.cache_clear()


def _make_token(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "aud": "authenticated",
        "email": "farmer@example.com",
        "app_metadata": {"role": "farmer"},
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    payload.update(overrides)
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_valid_token_verifies():
    verified = verify_token(_make_token())
    assert verified.user_id == "11111111-1111-1111-1111-111111111111"
    assert verified.email == "farmer@example.com"
    assert verified.role == "farmer"


def test_admin_role_from_app_metadata():
    token = _make_token(app_metadata={"role": "admin"})
    assert verify_token(token).role == "admin"


def test_role_defaults_to_farmer_when_absent():
    token = _make_token(app_metadata={})
    assert verify_token(token).role == "farmer"


def test_user_metadata_role_is_ignored():
    """A farmer could write to user_metadata themselves via the Supabase
    SDK -- role must never be trusted from there, only app_metadata
    (server-side-only), or any signed-up user could mint an admin token."""
    token = _make_token(app_metadata={"role": "farmer"}, user_metadata={"role": "admin"})
    assert verify_token(token).role == "farmer"


def test_expired_token_rejected():
    now = datetime.now(timezone.utc)
    token = _make_token(iat=now - timedelta(hours=2), exp=now - timedelta(hours=1))
    with pytest.raises(ApiError) as exc:
        verify_token(token)
    assert exc.value.status == 401


def test_tampered_signature_rejected():
    token = _make_token()
    tampered = token[:-4] + ("A" * 4 if not token.endswith("A" * 4) else "B" * 4)
    with pytest.raises(ApiError) as exc:
        verify_token(tampered)
    assert exc.value.status == 401


def test_wrong_secret_rejected():
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "22222222-2222-2222-2222-222222222222",
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, "a-completely-different-secret", algorithm="HS256")
    with pytest.raises(ApiError) as exc:
        verify_token(token)
    assert exc.value.status == 401


def test_wrong_audience_rejected():
    now = datetime.now(timezone.utc)
    token = _make_token(aud="something-else", iat=now, exp=now + timedelta(hours=1))
    with pytest.raises(ApiError) as exc:
        verify_token(token)
    assert exc.value.status == 401


def test_missing_sub_claim_rejected():
    now = datetime.now(timezone.utc)
    payload = {"aud": "authenticated", "iat": now, "exp": now + timedelta(hours=1)}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(ApiError) as exc:
        verify_token(token)
    assert exc.value.status == 401


def test_empty_token_rejected():
    with pytest.raises(ApiError) as exc:
        verify_token("")
    assert exc.value.status == 401


def test_no_verification_method_configured_rejected(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from agro_mirai.api.jwt_auth import _jwks_client

    _jwks_client.cache_clear()
    with pytest.raises(ApiError) as exc:
        verify_token(_make_token())
    assert exc.value.status == 401


def test_verify_bearer_token_requires_bearer_prefix():
    token = _make_token()
    with pytest.raises(ApiError):
        verify_bearer_token(token)  # missing "Bearer " prefix
    with pytest.raises(ApiError):
        verify_bearer_token(None)
    with pytest.raises(ApiError):
        verify_bearer_token("Bearer ")
    assert verify_bearer_token(f"Bearer {token}").user_id == "11111111-1111-1111-1111-111111111111"
