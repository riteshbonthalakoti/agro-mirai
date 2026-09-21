from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import (
    Advisory,
    CropRecommendation,
    DiseaseRiskAlert,
    Farmer,
    Field_,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector

API_KEY = "test-secret-key"
FARMER_ID = "11111111-1111-4111-8111-111111111111"
FIELD_ID = "22222222-2222-4222-8222-222222222222"

_NOW = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)

_FIELD = Field_(
    id=FIELD_ID,
    farmer_id=FARMER_ID,
    created_at=_NOW,
    updated_at=_NOW,
    name="North Plot",
    latitude=15.1394,
    longitude=76.9214,
    area_ha=1.75,
    elevation_m=449.0,
    soil_type="red",
    current_crop="cotton",
    sown_on=date(2026, 6, 15),
)

_VECTOR = FeatureVector(
    field_id=FIELD_ID,
    as_of=date(2026, 8, 24),
    rainfall_mm_sum_7d=6.6,
    temp_c_mean_7d=25.0,
    humidity_pct_mean_7d=69.0,
    rainfall_mm_sum_14d=10.0,
    temp_c_mean_14d=25.0,
    humidity_pct_mean_14d=69.0,
    rainfall_mm_sum_30d=20.0,
    temp_c_mean_30d=25.0,
    humidity_pct_mean_30d=69.0,
    soil_data_available=True,
)


def _mock_store():
    store = MagicMock()
    store.ping.return_value = True
    store.get_farmer.return_value = Farmer(
        id=FARMER_ID,
        created_at=_NOW,
        updated_at=_NOW,
        name="Ravi Kumar",
        preferred_language="kn",
    )
    store.get_field.return_value = _FIELD
    store.list_fields.return_value = [_FIELD]
    store.list_weather_readings.return_value = ["placeholder"]  # non-empty
    store.list_soil_samples.return_value = []
    store.list_ndvi_readings.return_value = []
    store.save_field.side_effect = lambda farmer_id, field: field
    store.save_crop_recommendation.side_effect = lambda farmer_id, rec: rec
    store.save_irrigation_advice.side_effect = lambda farmer_id, adv: adv
    store.save_disease_risk_alert.side_effect = lambda farmer_id, alert: alert
    store.save_advisory.side_effect = lambda farmer_id, adv: adv
    store.list_disease_risk_alerts.return_value = []
    store.list_advisories_for_field.return_value = []
    return store


@pytest.fixture
def app(monkeypatch):
    store = _mock_store()

    crop_model = MagicMock()
    crop_model.predict.return_value = CropRecommendation(
        id="c1", field_id=FIELD_ID, created_at=_NOW,
        recommended_crop="cotton", confidence=0.9,
    )
    irrigation_model = MagicMock()
    irrigation_model.predict.return_value = IrrigationAdvice(
        id="i1", field_id=FIELD_ID, created_at=_NOW,
        recommended_depth_mm=12.0, window_start_at=_NOW, window_end_at=_NOW,
        urgency="moderate",
    )
    disease_model = MagicMock()
    disease_model.predict.return_value = DiseaseRiskAlert(
        id="d1", field_id=FIELD_ID, created_at=_NOW,
        disease="fungal_generic", risk_level="low", confidence=0.8,
    )
    decision_engine = MagicMock()
    decision_engine.recommend.return_value = Advisory(
        id="a1", field_id=FIELD_ID, created_at=_NOW,
        language="en", title="Advisory for cotton", body="body text",
        severity="moderate", source_refs=["c1", "i1", "d1"],
    )

    # Module 23: the recommendation/irrigation/disease-risk/advisories
    # handler bodies moved to value_endpoints.py, shared by /v1 and /v2 —
    # patch it there once so both surfaces' unit tests get the same fixed
    # feature vector.
    monkeypatch.setattr(
        "agro_mirai.api.value_endpoints.build_features_for_field",
        lambda *a, **k: _VECTOR,
    )

    application = create_app(
        {
            "API_KEY": API_KEY,
            "FARMER_ID": FARMER_ID,
            "TESTING": True,
            "DATA_STORE": store,
            "CROP_MODEL": crop_model,
            "IRRIGATION_MODEL": irrigation_model,
            "DISEASE_MODEL": disease_model,
            "DECISION_ENGINE": decision_engine,
        }
    )
    application.extensions["store_mock"] = store
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _auth_headers():
    return {"Authorization": f"Bearer {API_KEY}"}


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_voice_caches():
    """Module 39: voice_client caches translations/audio in memory; tests reuse
    fixed advisory ids, so start each test with empty caches."""
    from agro_mirai.api import voice_client

    voice_client._AUDIO_CACHE.clear()
    voice_client._TRANSLATION_CACHE.clear()
    yield


@pytest.fixture(autouse=True)
def _no_live_sarvam(monkeypatch):
    """Module 40: tests must never call the live Sarvam API (or spend quota)
    even if the developer's shell has SARVAM_API_KEY_* set."""
    for name in ("SARVAM_API_KEY", "SARVAM_API_KEY_1", "SARVAM_API_KEY_2", "SARVAM_API_KEY_3"):
        monkeypatch.delenv(name, raising=False)
