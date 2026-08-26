"""Integration: real Flask test client, real DecisionEngine, real model
artifacts, farm-001/farm-002 fixtures loaded into a temp SQLite DataStore
via tools/seed_fixture.py's loader.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from agro_mirai.models.crop_recommendation_model import (  # noqa: E402
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (  # noqa: E402
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)

try:
    import shap  # noqa: F401

    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SHAP_AVAILABLE or not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="shap not installed, or models/*.joblib not present — pip install shap and/or run tools/train_*.py first",
)

from seed_fixture import build_store, load_fixture  # noqa: E402

from agro_mirai.api.app import create_app  # noqa: E402
from check_specs import (  # noqa: E402
    ENUMS_PATH,
    SCHEMA_PATH,
    _load_yaml,
    _parse_enum_doc,
    _validate_entity,
)

FIXTURES_DIR = ROOT / "specs" / "domains" / "fixtures"
API_KEY = "integration-test-key"


@pytest.fixture
def seeded_app(tmp_path):
    db_path = str(tmp_path / "api_integration.db")
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


def _auth():
    return {"Authorization": f"Bearer {API_KEY}"}


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_advisory_endpoint_returns_schema_valid_advisory(seeded_app):
    application, field_id = seeded_app
    client = application.test_client()

    resp = client.get(f"/fields/{field_id}/advisories", headers=_auth())
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert len(items) >= 1

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {field_id}}

    for record in items:
        problems = _validate_entity("Advisory", record, schema, enums, known_ids, {}, 0)
        assert problems == [], problems


def test_missing_auth_header_returns_401(client, seeded_app):
    _, field_id = seeded_app
    resp = client.get(f"/fields/{field_id}/advisories")
    assert resp.status_code == 401


def test_wrong_auth_key_returns_401(client, seeded_app):
    _, field_id = seeded_app
    resp = client.get(
        f"/fields/{field_id}/advisories", headers={"Authorization": "Bearer nope"}
    )
    assert resp.status_code == 401


def test_unknown_field_id_returns_404_not_500(client):
    resp = client.get(
        "/fields/99999999-9999-4999-8999-999999999999/advisories", headers=_auth()
    )
    assert resp.status_code == 404


def test_recommendation_endpoint_end_to_end(seeded_app):
    application, field_id = seeded_app
    client = application.test_client()
    resp = client.get(f"/fields/{field_id}/recommendation", headers=_auth())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["field_id"] == field_id
    assert 0.0 <= body["confidence"] <= 1.0
