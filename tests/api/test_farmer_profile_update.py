"""Module 25: ``PATCH /v2/farmers/me`` ``preferred_language`` validation.

Real Flask test client + real ``SQLiteDataStore`` (``:memory:``), same
style as ``test_field_update.py``. Was previously hardcoded to a stale
``{"en", "kn"}`` allowlist that had drifted from ``V1_LANGUAGES``
(``src/agro_mirai/api/routes/farms_v2.py``) — these tests cover the fix.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


@pytest.fixture
def app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, phone="+919000000001"):
    from tests.api._otp_helpers import register_and_login

    assert register_and_login(client, phone).status_code == 200


@pytest.mark.parametrize("lang", ["en", "kn", "te", "hi"])
def test_patch_accepts_each_v1_language(client, lang):
    _register_and_login(client)
    resp = client.patch("/v2/farmers/me", json={"preferred_language": lang})
    assert resp.status_code == 200
    assert resp.get_json()["preferred_language"] == lang


def test_patch_rejects_unsupported_language(client):
    _register_and_login(client)
    resp = client.patch("/v2/farmers/me", json={"preferred_language": "gu"})
    assert resp.status_code == 400
    assert "preferred_language" in resp.get_json()["error"]["message"]
