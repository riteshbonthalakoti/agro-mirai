"""Module 14 — integration tests against a real Flask app: real
DecisionEngine, real crop/irrigation artifacts, farm-001 fixture loaded
into a temp SQLite DataStore. Mirrors tests/api/test_integration.py's
setup.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


from seed_fixture import build_store, load_fixture  # noqa: E402

from agro_mirai.api.app import create_app  # noqa: E402

FIXTURES_DIR = ROOT / "specs" / "domains" / "fixtures"
API_KEY = "frontend-integration-test-key"


@pytest.fixture
def seeded_app(tmp_path):
    db_path = str(tmp_path / "frontend_integration.db")
    store = build_store("sqlite", db_path)
    data = json.loads((FIXTURES_DIR / "farm-001.json").read_text(encoding="utf-8"))
    loaded = load_fixture(store, data)
    farmer_id = loaded["farmers"][0].id
    field_id = loaded["fields"][0].id

    application = create_app(
        {
            "API_KEY": API_KEY,
            "FARMER_ID": farmer_id,
            "TESTING": True,
            "DATA_STORE": store,
        }
    )
    return application, field_id


@pytest.fixture
def client(seeded_app):
    application, _ = seeded_app
    return application.test_client()


def test_dashboard_renders_farmer_and_fields(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AGRO MIRAI" in resp.data


def test_field_detail_renders_real_advisory_data(seeded_app):
    """Acceptance check 1: advisory view renders real data matching what
    GET /fields/{id}/advisories actually returns."""
    application, field_id = seeded_app
    client = application.test_client()

    api_resp = client.get(
        f"/fields/{field_id}/advisories",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert api_resp.status_code == 200
    api_advisories = api_resp.get_json()["items"]
    assert len(api_advisories) >= 1

    page_resp = client.get(f"/field/{field_id}")
    assert page_resp.status_code == 200
    html = page_resp.data.decode("utf-8")
    for advisory in api_advisories:
        assert advisory["title"] in html
        assert advisory["id"] in html  # used as the hidden form field value


def test_unknown_field_id_renders_error_page_not_500(client):
    resp = client.get("/field/99999999-9999-4999-8999-999999999999")
    assert resp.status_code == 404
    assert b"Something went wrong" in resp.data


def test_feedback_form_posts_and_entry_is_retrievable(seeded_app):
    """Acceptance check 2: feedback form successfully posts and the
    entry is retrievable via DataStore afterward."""
    application, field_id = seeded_app
    client = application.test_client()

    api_resp = client.get(
        f"/fields/{field_id}/advisories",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    advisory_id = api_resp.get_json()["items"][0]["id"]

    resp = client.post(
        "/ui/feedback",
        data={
            "field_id": field_id,
            "advisory_id": advisory_id,
            "rating": "4",
            "helpful": "yes",
            "comment": "Useful advice",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Thanks" in resp.data

    store = application.extensions["data_store"]
    farmer_id = application.config["FARMER_ID"]
    entries = store.list_feedback_for_advisory(farmer_id, advisory_id)
    assert any(e.rating == 4 and e.comment == "Useful advice" for e in entries)


def test_feedback_form_rejects_invalid_rating(seeded_app):
    application, field_id = seeded_app
    client = application.test_client()

    api_resp = client.get(
        f"/fields/{field_id}/advisories",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    advisory_id = api_resp.get_json()["items"][0]["id"]

    resp = client.post(
        "/ui/feedback",
        data={
            "field_id": field_id,
            "advisory_id": advisory_id,
            "rating": "9",
            "helpful": "yes",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Rating must be between 1 and 5" in resp.data
