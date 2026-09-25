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
import pytest


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


def test_request_otp_normalizes_bare_phone_to_e164():
    # Real bug found live: the mobile client sent a bare 10-digit number
    # with no country code, and it went to the backend verbatim -- meaning
    # "9123456780" and "+919123456780" would silently be two different
    # farmer accounts. request-otp and verify-otp must agree on the same
    # normalized key regardless of how the phone was typed.
    app = _app()
    client = app.test_client()

    resp = _request_otp(client, "9123456780", name="Bare Number")
    assert resp.status_code == 200
    assert resp.get_json()["phone"] == "+919123456780"

    code = otp_store._pending["+919123456780"].code
    verify = client.post(
        "/v2/auth/verify-otp", json={"phone": "9123456780", "otp": code}
    )
    assert verify.status_code == 200
    assert verify.get_json()["phone"] == "+919123456780"


def test_request_otp_normalizes_phone_with_spaces_and_dashes():
    app = _app()
    client = app.test_client()

    resp = _request_otp(client, "+91 981-234-5678", name="Formatted")
    assert resp.status_code == 200
    assert resp.get_json()["phone"] == "+919812345678"


def test_request_otp_creates_farmer_without_leaking_hash():
    app = _app()
    client = app.test_client()
    resp = _request_otp(client, "+919876543210", name="Alice")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["otp_sent"] is True
    assert "password_hash" not in body


def test_request_otp_is_new_farmer_true_on_first_call_false_on_repeat():
    app = _app()
    client = app.test_client()
    phone = "+919876500001"

    first = _request_otp(client, phone, name="Bob")
    assert first.get_json()["is_new_farmer"] is True

    # asking for a code alone creates no account...
    assert app.extensions["data_store"].get_farmer_by_phone(phone) is None

    # ...verifying it does, and only then is the phone a known farmer
    from agro_mirai.auth.otp import otp_store

    code = otp_store._pending[phone].code
    assert client.post("/v2/auth/verify-otp", json={"phone": phone, "otp": code}).status_code == 200
    assert app.extensions["data_store"].get_farmer_by_phone(phone) is not None

    client.post("/v2/auth/logout")
    otp_store._pending.clear()  # skip the resend cooldown
    second = _request_otp(client, phone, name="Bob")
    assert second.get_json()["is_new_farmer"] is False


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
    _login(client, "+919444444444", name="Dave")
    client.post("/v2/auth/logout")
    from agro_mirai.auth.otp import otp_store

    otp_store._pending.clear()  # skip the resend cooldown
    resp = client.post("/v2/auth/request-otp", json={"phone": "+919444444444"})
    assert resp.status_code == 200


def test_second_code_request_within_seconds_is_refused():
    client = _app().test_client()
    assert _request_otp(client, "+919876500077", name="Eve").status_code == 200
    again = _request_otp(client, "+919876500077", name="Eve")
    assert again.status_code == 429
    assert again.get_json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_unverified_requests_never_create_farmers():
    app = _app()
    client = app.test_client()
    for i in range(5):
        assert _request_otp(client, f"+91987650{i:04d}", name="Spam").status_code == 200
    assert app.extensions["data_store"].list_all_farmers() == []
