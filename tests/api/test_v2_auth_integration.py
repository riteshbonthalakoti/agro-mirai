"""Module 27 integration: request-otp -> verify-otp -> access own data ->
CANNOT access another farmer's data -> logout -> session invalidated.
Real Flask test client, real SQLiteDataStore (:memory:), real session
cookies (no mocked auth) — the same genuine cross-tenant isolation proof
Module 19 established, now against Name+Phone+OTP auth instead of
email+password.
"""
from __future__ import annotations

from agro_mirai.api.app import create_app
from agro_mirai.auth.otp import otp_store
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from agro_mirai.models.crop_recommendation_model import (
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)
import pytest

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)


def _app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


def _request_otp(client, phone, name="Farmer", preferred_language="en"):
    return client.post(
        "/v2/auth/request-otp",
        json={"phone": phone, "name": name, "preferred_language": preferred_language},
    )


def _login(client, phone, name="Farmer"):
    """request-otp -> read the real code straight out of the process-local
    OtpStore (standing in for "read it off the server logs", which is
    where a human tester would get it per decisions/0023) -> verify-otp."""
    resp = _request_otp(client, phone, name=name)
    assert resp.status_code == 200
    code = otp_store._pending[phone].code
    return client.post("/v2/auth/verify-otp", json={"phone": phone, "otp": code})


def test_request_otp_creates_farmer_without_leaking_hash():
    app = _app()
    client = app.test_client()
    resp = _request_otp(client, "+919876543210", name="Alice")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["otp_sent"] is True
    assert "password_hash" not in body


def test_request_otp_rejects_missing_name_for_new_phone():
    app = _app()
    client = app.test_client()
    resp = client.post(
        "/v2/auth/request-otp", json={"phone": "+919876543211", "name": ""}
    )
    assert resp.status_code == 400


def test_request_otp_rejects_invalid_phone():
    app = _app()
    client = app.test_client()
    resp = _request_otp(client, "abc", name="Farmer")
    assert resp.status_code == 400


@pytest.mark.parametrize("lang", ["en", "kn", "te", "hi"])
def test_request_otp_accepts_each_v1_language(lang):
    app = _app()
    client = app.test_client()
    resp = client.post(
        "/v2/auth/request-otp",
        json={"phone": f"+91900000{ord(lang[0]):04d}", "name": "Farmer", "preferred_language": lang},
    )
    assert resp.status_code == 200


def test_request_otp_rejects_unsupported_language():
    app = _app()
    client = app.test_client()
    resp = client.post(
        "/v2/auth/request-otp",
        json={"phone": "+919000000002", "name": "Farmer", "preferred_language": "ta"},
    )
    assert resp.status_code == 400
    assert "preferred_language" in resp.get_json()["error"]["message"]


def test_verify_otp_wrong_code_401():
    app = _app()
    client = app.test_client()
    _request_otp(client, "+919000000003", name="Bob")
    resp = client.post(
        "/v2/auth/verify-otp", json={"phone": "+919000000003", "otp": "000000"}
    )
    assert resp.status_code == 401


def test_verify_otp_wrong_code_does_not_consume_pending_otp():
    """A wrong guess doesn't burn the real code -- the farmer can still
    retry with the correct one within MAX_VERIFY_ATTEMPTS."""
    app = _app()
    client = app.test_client()
    _request_otp(client, "+919000000004", name="Carl")
    real_code = otp_store._pending["+919000000004"].code
    wrong = client.post(
        "/v2/auth/verify-otp", json={"phone": "+919000000004", "otp": "111111"}
    )
    assert wrong.status_code == 401
    right = client.post(
        "/v2/auth/verify-otp", json={"phone": "+919000000004", "otp": real_code}
    )
    assert right.status_code == 200


def test_full_cross_tenant_isolation_flow():
    app = _app()
    client = app.test_client()

    # Farmer 1 requests+verifies OTP, creates a field, can read it back.
    login1 = _login(client, "+919111111111", name="Farmer One")
    assert login1.status_code == 200

    create = client.post(
        "/v2/fields",
        json={"name": "F1 Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert create.status_code == 201
    field_id = create.get_json()["id"]

    get_own = client.get(f"/v2/fields/{field_id}")
    assert get_own.status_code == 200
    assert get_own.get_json()["id"] == field_id

    list_own = client.get("/v2/fields")
    assert list_own.status_code == 200
    assert len(list_own.get_json()["items"]) == 1

    # Log farmer 1 out before farmer 2 logs in — Flask test client keeps
    # a single cookie jar, sessions are mutually exclusive here.
    logout1 = client.post("/v2/auth/logout")
    assert logout1.status_code == 200

    # A request after logout with no new login is rejected.
    denied_after_logout = client.get("/v2/fields")
    assert denied_after_logout.status_code == 401

    # --- Farmer 2 logs in: CANNOT see or fetch farmer 1's field.
    login2 = _login(client, "+919222222222", name="Farmer Two")
    assert login2.status_code == 200

    list_other = client.get("/v2/fields")
    assert list_other.status_code == 200
    assert list_other.get_json()["items"] == []

    get_other = client.get(f"/v2/fields/{field_id}")
    assert get_other.status_code == 404  # not owned -> not found, not leaked

    # --- Logout invalidates the session for good.
    logout2 = client.post("/v2/auth/logout")
    assert logout2.status_code == 200
    denied = client.get("/v2/fields")
    assert denied.status_code == 401


def test_unauthenticated_v2_request_401():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/fields")
    assert resp.status_code == 401


def test_v2_farmers_me_matches_logged_in_farmer():
    app = _app()
    client = app.test_client()
    login = _login(client, "+919333333333", name="Carol")
    assert login.status_code == 200
    resp = client.get("/v2/farmers/me")
    assert resp.status_code == 200
    assert resp.get_json()["phone"] == "+919333333333"
    assert resp.get_json()["name"] == "Carol"


def test_request_otp_for_existing_phone_does_not_require_name():
    """Second (and later) OTP requests for an already-registered phone
    don't need name/preferred_language again -- only first-time
    registration does."""
    app = _app()
    client = app.test_client()
    _request_otp(client, "+919444444444", name="Dave")
    resp = client.post("/v2/auth/request-otp", json={"phone": "+919444444444"})
    assert resp.status_code == 200
