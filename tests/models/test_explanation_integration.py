"""Integration test: fixture -> FeatureBuilder -> real models ->
ExplanationService, against real crop/irrigation artifacts.

Confirms top contributors are agronomically sensible (e.g. soil_moisture
for irrigation) and that summary_en reads as a sentence, not a raw
dict/code-like string. The disease path needs no artifact — it exercises
the full scoring path directly.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from agro_mirai.models.crop_recommendation_model import (  # noqa: E402
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.crop_recommendation_model import CropRecommendationModel  # noqa: E402
from agro_mirai.models.disease_risk_model import DiseaseRiskModel  # noqa: E402
from agro_mirai.models.explanation_service import ExplanationService  # noqa: E402
from agro_mirai.models.irrigation_prediction_model import (  # noqa: E402
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (  # noqa: E402
    IrrigationPredictionModel,
)
from agro_mirai.persistence.models import (  # noqa: E402
    Field_,
    NDVIReading,
    SoilSample,
    WeatherReading,
)
from agro_mirai.processing.feature_builder import FeatureBuilder  # noqa: E402

FIXTURES_DIR = ROOT / "specs" / "domains" / "fixtures"

try:
    import shap  # noqa: F401

    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SHAP_AVAILABLE or not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="shap not installed, or models/*.joblib not present — pip install shap and/or run tools/train_*.py first",
)


def _pdt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _pdate(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _field_from(rec: dict) -> Field_:
    return Field_(
        id=rec["id"],
        farmer_id=rec["farmer_id"],
        created_at=_pdt(rec["created_at"]),
        updated_at=_pdt(rec["updated_at"]),
        name=rec["name"],
        latitude=rec["latitude"],
        longitude=rec["longitude"],
        area_ha=rec["area_ha"],
        elevation_m=rec.get("elevation_m"),
        soil_type=rec.get("soil_type"),
        current_crop=rec.get("current_crop"),
        sown_on=_pdate(rec.get("sown_on")),
    )


def _weather_from(rec: dict) -> WeatherReading:
    return WeatherReading(
        id=rec["id"],
        field_id=rec["field_id"],
        observed_at=_pdt(rec["observed_at"]),
        source=rec["source"],
        temp_c=rec["temp_c"],
        is_forecast=rec["is_forecast"],
        temp_min_c=rec.get("temp_min_c"),
        temp_max_c=rec.get("temp_max_c"),
        humidity_pct=rec.get("humidity_pct"),
        rainfall_mm=rec.get("rainfall_mm"),
        wind_mps=rec.get("wind_mps"),
    )


def _soil_from(rec: dict) -> SoilSample:
    return SoilSample(
        id=rec["id"],
        field_id=rec["field_id"],
        observed_at=_pdt(rec["observed_at"]),
        source=rec["source"],
        ph=rec.get("ph"),
        nitrogen_mg_per_kg=rec.get("nitrogen_mg_per_kg"),
        phosphorus_mg_per_kg=rec.get("phosphorus_mg_per_kg"),
        potassium_mg_per_kg=rec.get("potassium_mg_per_kg"),
        organic_carbon_pct=rec.get("organic_carbon_pct"),
        moisture_pct=rec.get("moisture_pct"),
    )


def _ndvi_from(rec: dict) -> NDVIReading:
    return NDVIReading(
        id=rec["id"],
        field_id=rec["field_id"],
        observed_at=_pdt(rec["observed_at"]),
        source=rec["source"],
        ndvi=rec["ndvi"],
        cloud_cover_pct=rec.get("cloud_cover_pct"),
        satellite=rec.get("satellite"),
    )


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _vector_for_first_field(fixture_name: str, as_of: date):
    data = _load_fixture(fixture_name)
    field_rec = data["fields"][0]
    field = _field_from(field_rec)

    weather = [_weather_from(r) for r in data["weather_readings"] if r["field_id"] == field.id]
    soil = [_soil_from(r) for r in data["soil_samples"] if r["field_id"] == field.id]
    ndvi = [_ndvi_from(r) for r in data["ndvi_readings"] if r["field_id"] == field.id]

    return FeatureBuilder.build(field, weather, soil, ndvi, as_of), field


@pytest.fixture(scope="module")
def service():
    return ExplanationService(
        crop_model=CropRecommendationModel(),
        irrigation_model=IrrigationPredictionModel(),
    )


def test_explain_crop_top_contributor_is_agronomically_sensible(service):
    vector, _ = _vector_for_first_field("farm-001.json", as_of=date(2026, 8, 24))
    recommendation = CropRecommendationModel().predict(vector)

    explanation = service.explain_crop(recommendation, vector)

    # crop pick is rule-based (EcoCrop) now: the reason is the model's own text
    assert explanation.method == "rule_weight"
    assert recommendation.recommended_crop.capitalize() in explanation.summary_en
    assert "fit" in explanation.summary_en
    assert "{" not in explanation.summary_en and "}" not in explanation.summary_en


def test_explain_irrigation_uses_water_balance_rationale(service):
    vector, _ = _vector_for_first_field("farm-001.json", as_of=date(2026, 8, 24))
    advice = IrrigationPredictionModel().predict(vector)

    explanation = service.explain_irrigation(advice, vector)

    # urgency is rule-based now, so no SHAP contributions
    assert explanation.top_contributions == []
    assert "Water balance" in explanation.summary_en


def test_explain_disease_full_scoring_path(service):
    vector, _ = _vector_for_first_field("farm-001.json", as_of=date(2026, 8, 24))
    alert = DiseaseRiskModel().predict(vector)

    explanation = service.explain_disease(alert, vector)

    assert explanation.method == "rule_weight"
    assert "shap" not in explanation.summary_en.lower()
    assert len(explanation.top_contributions) == 3
    assert isinstance(explanation.summary_en, str)
