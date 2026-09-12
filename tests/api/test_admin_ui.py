"""Module 19: server-rendered /admin dashboard (Jinja2, ADR 0013 pattern)."""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.models.crop_recommendation_model import (
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def test_admin_dashboard_redirects_when_not_logged_in():
    app, client = _app_and_client()
    resp = client.get("/admin", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Admin login" in resp.data


def test_admin_login_rejects_non_admin_account():
    app, client = _app_and_client()
    client.post(
        "/v2/auth/register",
        json={
            "email": "farmer@example.com",
            "password": "Sup3rSecret1",
            "name": "F",
            "preferred_language": "en",
        },
    )
    resp = client.post(
        "/admin/login",
        data={"email": "farmer@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin login" in resp.data  # bounced back, not the dashboard


def test_admin_login_and_dashboard_render():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    client.post(
        "/v2/auth/register",
        json={
            "email": "admin@example.com",
            "password": "Sup3rSecret1",
            "name": "Admin",
            "preferred_language": "en",
        },
    )
    admin_farmer = store.get_farmer_by_email("admin@example.com")
    admin_farmer.role = "admin"
    store.save_farmer(admin_farmer)

    resp = client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin dashboard" in resp.data
    assert b"admin@example.com" in resp.data
