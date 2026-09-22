"""Unit tests for RemoteCropModel and RemoteIrrigationModel client wrappers."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from agro_mirai.models.remote_tabular_client import RemoteCropModel, RemoteIrrigationModel
from agro_mirai.processing.feature_builder import FeatureVector


@pytest.fixture
def sample_feature_vector():
    from datetime import date
    return FeatureVector(
        field_id="field-001",
        as_of=date(2026, 9, 22),
        rainfall_mm_sum_7d=10.0,
        temp_c_mean_7d=28.0,
        humidity_pct_mean_7d=60.0,
        rainfall_mm_sum_14d=25.0,
        temp_c_mean_14d=27.5,
        humidity_pct_mean_14d=62.0,
        rainfall_mm_sum_30d=60.0,
        temp_c_mean_30d=27.0,
        humidity_pct_mean_30d=65.0,
        soil_data_available=True,
        soil_ph=6.5,
        soil_nitrogen_mg_per_kg=120.0,
        soil_phosphorus_mg_per_kg=40.0,
        soil_potassium_mg_per_kg=180.0,
        soil_organic_carbon_pct=0.5,
        soil_moisture_pct=20.0,
        soil_npk_balance_index=0.8,
        soil_chemistry_source="soilgrids",
        soil_moisture_source="soilgrids",
        ndvi_data_available=True,
        ndvi_latest=0.6,
        ndvi_trend=0.04,
        ndvi_confidence_source="gee_live",
        crop_type="cotton",
        season="kharif",
    )


def test_remote_crop_model_success(sample_feature_vector):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "rec-123",
        "field_id": "field-001",
        "created_at": "2026-09-22T12:00:00Z",
        "recommended_crop": "cotton",
        "confidence": 0.95,
        "alternatives": ["maize", "rice"],
        "rationale": "High NPK fit",
        "season": "kharif",
        "out_of_region": False,
        "regional_alternative": None,
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client = RemoteCropModel(service_url="http://mock-tabular-service")
        res = client.predict(sample_feature_vector, top_k=3)
        assert res.recommended_crop == "cotton"
        assert res.confidence == 0.95
        assert mock_post.called


def test_remote_crop_model_fallback(sample_feature_vector):
    mock_local = MagicMock()
    mock_local.predict.return_value = MagicMock(recommended_crop="fallback-crop")

    with patch("requests.post", side_effect=Exception("Connection refused")):
        client = RemoteCropModel(local_model=mock_local, service_url="http://mock-tabular-service")
        res = client.predict(sample_feature_vector)
        assert res.recommended_crop == "fallback-crop"
        assert mock_local.predict.called


def test_remote_irrigation_model_success(sample_feature_vector):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "irr-123",
        "field_id": "field-001",
        "created_at": "2026-09-22T12:00:00Z",
        "recommended_depth_mm": 25.0,
        "window_start_at": "2026-09-22T12:00:00Z",
        "window_end_at": "2026-09-25T12:00:00Z",
        "urgency": "moderate",
        "rationale": "Moisture deficit detected",
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client = RemoteIrrigationModel(service_url="http://mock-tabular-service")
        res = client.predict(sample_feature_vector)
        assert res.recommended_depth_mm == 25.0
        assert res.urgency == "moderate"
        assert mock_post.called


def test_remote_irrigation_model_fallback(sample_feature_vector):
    mock_local = MagicMock()
    mock_local.predict.return_value = MagicMock(urgency="low", recommended_depth_mm=0.0)

    with patch("requests.post", side_effect=Exception("Connection refused")):
        client = RemoteIrrigationModel(local_model=mock_local, service_url="http://mock-tabular-service")
        res = client.predict(sample_feature_vector)
        assert res.urgency == "low"
        assert mock_local.predict.called
