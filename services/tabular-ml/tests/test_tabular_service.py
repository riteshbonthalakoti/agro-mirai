"""Unit tests for services/tabular-ml microservice."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

_HERE = Path(__file__).resolve().parent
_SERVICE_DIR = _HERE.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_feature_vector_dict():
    return {
        "field_id": "field-test-001",
        "as_of": "2026-09-22",
        "rainfall_mm_sum_7d": 12.5,
        "temp_c_mean_7d": 28.4,
        "humidity_pct_mean_7d": 65.0,
        "rainfall_mm_sum_14d": 30.0,
        "temp_c_mean_14d": 28.0,
        "humidity_pct_mean_14d": 64.0,
        "rainfall_mm_sum_30d": 75.0,
        "temp_c_mean_30d": 27.5,
        "humidity_pct_mean_30d": 62.0,
        "soil_data_available": True,
        "soil_ph": 6.8,
        "soil_nitrogen_mg_per_kg": 140.0,
        "soil_phosphorus_mg_per_kg": 45.0,
        "soil_potassium_mg_per_kg": 190.0,
        "soil_organic_carbon_pct": 0.55,
        "soil_moisture_pct": 22.0,
        "soil_npk_balance_index": 0.85,
        "soil_chemistry_source": "soilgrids",
        "soil_moisture_source": "soilgrids",
        "ndvi_data_available": True,
        "ndvi_latest": 0.62,
        "ndvi_trend": 0.05,
        "ndvi_confidence_source": "gee_live",
        "crop_type": "cotton",
        "season": "kharif",
    }


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "tabular-ml"


def test_predict_crop(client, sample_feature_vector_dict):
    response = client.post(
        "/predict/crop",
        json={"feature_vector": sample_feature_vector_dict, "top_k": 3},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "recommended_crop" in data
    assert "confidence" in data
    assert data["field_id"] == "field-test-001"


def test_predict_irrigation(client, sample_feature_vector_dict):
    response = client.post(
        "/predict/irrigation",
        json={"feature_vector": sample_feature_vector_dict},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "recommended_depth_mm" in data
    assert "urgency" in data
    assert data["field_id"] == "field-test-001"
