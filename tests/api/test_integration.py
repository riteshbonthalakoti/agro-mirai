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
    # Module 39: the crop pick carries its own SHAP-based "why" (it used to be null).
    assert body["rationale"] and "fit" in body["rationale"]


def test_irrigation_endpoint_end_to_end(seeded_app):
    """Module 22: this is the route a live curl repro found 500ing on
    farm-001 — the fixture's fixed Aug-2026 weather dates aged out of
    the 7-day window `_water_balance` needs, and the resulting
    ValueError wasn't caught anywhere. `seeded_app` uses the real
    current date (no `as_of` override), so this genuinely exercises the
    same failure mode a live server call would hit, not just a frozen
    date that happens to still be "recent"."""
    application, field_id = seeded_app
    client = application.test_client()
    resp = client.get(f"/fields/{field_id}/irrigation", headers=_auth())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["field_id"] == field_id
    assert body["recommended_depth_mm"] > 0


def test_disease_risk_endpoint_end_to_end(seeded_app):
    application, field_id = seeded_app
    client = application.test_client()
    resp = client.get(f"/fields/{field_id}/disease-risk", headers=_auth())
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert len(items) >= 1


def test_advisories_endpoint_live_against_real_current_date(seeded_app):
    """Module 22 regression: `GET /fields/{id}/advisories` against the
    real, unfrozen golden fixture and the real current date — the exact
    live repro that originally 500'd. If the fixture's weather ever
    ages out of every window again, this fails loudly instead of
    silently passing because some other test froze `as_of` to a date
    inside the fixture's original window."""
    application, field_id = seeded_app
    client = application.test_client()
    resp = client.get(f"/fields/{field_id}/advisories", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) >= 1


def test_irrigation_endpoint_returns_422_not_500_when_all_temp_windows_empty(
    client, seeded_app, monkeypatch
):
    """A field with a genuine multi-week weather gap (not just the
    fixture staleness this module fixed) must get a handled 422, never
    an uncaught 500 — proves the route-level ``_predict_or_422`` catch
    added in Module 22, independent of the fixture-shift fix. Forces the
    real condition (every temperature window ``None``) by monkeypatching
    ``FeatureBuilder.build`` to null out the temperature aggregates on an
    otherwise-real feature vector, rather than relying on fragile
    fixture date arithmetic."""
    application, field_id = seeded_app

    import agro_mirai.api.features as features_module

    real_build = features_module.FeatureBuilder.build

    def _build_with_no_temp_data(*args, **kwargs):
        vector = real_build(*args, **kwargs)
        vector.temp_c_mean_7d = None
        vector.temp_c_mean_14d = None
        vector.temp_c_mean_30d = None
        vector.daily_weather = None  # the daily balance would otherwise still answer
        return vector

    monkeypatch.setattr(features_module.FeatureBuilder, "build", staticmethod(_build_with_no_temp_data))

    resp = client.get(f"/fields/{field_id}/irrigation", headers=_auth())
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_recommendation_and_irrigation_carry_details_object(seeded_app):
    """Module 43: structured numbers (additive `details`) for the app to show as tiles."""
    from agro_mirai.api import value_endpoints

    application, field_id = seeded_app
    store = application.extensions["data_store"]
    farmer_id = application.config["FARMER_ID"]

    crop = value_endpoints.compute_recommendation(store, application.extensions, farmer_id, field_id)
    d = crop["details"]
    assert d["method"] == "ecocrop_rules" and d["mode"] == "best_fit"
    assert 1 <= len(d["ranking"]) <= 5
    assert {"crop", "score", "fit", "good_time_to_sow"} <= set(d["ranking"][0])

    irr = value_endpoints.compute_irrigation(store, application.extensions, farmer_id, field_id)
    assert irr["details"]["method"] in ("soil_water_balance", "weekly_shortcut")


def test_keep_current_crop_advises_on_the_crop_already_growing(seeded_app):
    from agro_mirai.api import value_endpoints

    application, field_id = seeded_app
    store = application.extensions["data_store"]
    farmer_id = application.config["FARMER_ID"]
    field = store.get_field(farmer_id, field_id)
    assert field.current_crop  # fixture field has a current crop

    kept = value_endpoints.compute_recommendation(
        store, application.extensions, farmer_id, field_id, keep_current=True
    )
    assert kept["recommended_crop"] == field.current_crop
    assert kept["rationale"].startswith("Keeping your current crop")
    assert kept["details"]["mode"] == "keep_current"
    assert field.current_crop not in kept["alternatives"]


def test_keep_current_without_a_current_crop_gives_the_normal_pick(seeded_app):
    import dataclasses

    from agro_mirai.api import value_endpoints

    application, field_id = seeded_app
    store = application.extensions["data_store"]
    farmer_id = application.config["FARMER_ID"]
    field = store.get_field(farmer_id, field_id)
    store.save_field(farmer_id, dataclasses.replace(field, current_crop=None))

    out = value_endpoints.compute_recommendation(
        store, application.extensions, farmer_id, field_id, keep_current=True
    )
    assert not out["rationale"].startswith("Keeping")
    assert out["details"]["mode"] == "best_fit"
