"""``CropRecommendationModel`` - ranks crops for a field.

Used to wrap a RandomForest trained on the Kaggle crop dataset, but that
model needs plant-available N/P/K which we never really have for a field,
so live picks were wrong (watermelon for a cotton field). It now ranks the
22 crops with the FAO EcoCrop ranges (temperature, soil pH, soil texture, a
soft rainfall check) in ``ecocrop.py``. See decisions/0027. No model file
is needed; ``model_path`` is only kept so old callers still work.

Input is a ``FeatureVector``; output is a schema-valid
``CropRecommendation`` (``persistence/models.py``). ``confidence`` is now
the suitability score (0-1), not a class probability.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from agro_mirai.models import ecocrop
from agro_mirai.models.regional_suitability import (
    BELLARY_REGIONAL_CROPS,
    check_regional_fit,
    in_karnataka_bbox,
)
from agro_mirai.persistence.models import CropRecommendation
from agro_mirai.processing.feature_builder import FeatureVector

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "models" / "crop_rf.joblib"
)


def _temperature(features: FeatureVector) -> float:
    for t in (features.temp_c_mean_14d, features.temp_c_mean_7d, features.temp_c_mean_30d):
        if t is not None:
            return t
    raise ValueError("crop suggestion needs some recent temperature data for this field")


def _fit_word(score: float) -> str:
    if score >= 0.8:
        return "good"
    if score >= 0.5:
        return "fair"
    return "weak"


def _current_crop_note(features: FeatureVector, fits, temp: float) -> str:
    """How the crop already in the field compares (season ignored: it is sown)."""
    crop = features.crop_type
    if not crop or crop not in ecocrop.table():
        return ""
    mine = ecocrop.score_crops(
        temp, features.soil_ph, features.soil_type, features.rainfall_mm_sum_30d, None, None,
        features.annual_rain_mm_est,
    )
    fit = next(f for f in mine if f.crop == crop)
    word = _fit_word(fit.score)
    if word == "weak":
        return f" Your current crop, {crop}, is a weak fit for these conditions; a different crop may do better next season."
    return f" Your current crop, {crop}, is a {word} fit for these conditions, so keep growing it."


def _greenness_note(features: FeatureVector) -> str:
    """Satellite greenness (NDVI) only matters if a crop is already growing."""
    if not features.crop_type or not features.ndvi_data_available or features.ndvi_latest is None:
        return ""
    age = features.days_since_sowing
    if features.ndvi_trend is not None and features.ndvi_trend <= -0.08:
        return " Satellite greenness has dropped recently; check the crop for water stress or disease."
    if age is not None and age > 45 and features.ndvi_latest < 0.3:
        return " Satellite greenness is low for a crop this age; check the field."
    return ""


class CropRecommendationModel:
    def __init__(self, model_path: Path | None = None):
        # no trained artifact any more
        self._model = None

    def predict(self, features: FeatureVector, top_k: int = 3) -> CropRecommendation:
        temp = _temperature(features)
        regional = (
            BELLARY_REGIONAL_CROPS
            if in_karnataka_bbox(features.latitude, features.longitude)
            else None
        )
        fits = ecocrop.score_crops(
            temp,
            features.soil_ph,
            features.soil_type,
            features.rainfall_mm_sum_30d,
            regional,
            features.as_of.month,
            features.annual_rain_mm_est,
        )
        best = fits[0]
        alternatives = [f.crop for f in fits[1 : 1 + top_k]]

        fit = check_regional_fit(best.crop, alternatives)

        rationale = (
            f"{best.crop.capitalize()} is a {_fit_word(best.score)} fit: "
            + ecocrop.describe(best, temp, features.soil_ph)
            + "."
        )
        if best.season_fit < 1.0:
            rationale += " It is a bit early or late in the year to sow it."
        elif best.season_fit == 1.0 and best.crop in ecocrop.SOWING_MONTHS:
            rationale += " This is a good time of year to sow it."
        if alternatives:
            rationale += f" Other options: {', '.join(alternatives)}."
        rationale += _current_crop_note(features, fits, temp)
        rationale += _greenness_note(features)
        if features.soil_chemistry_source and "fallback" in features.soil_chemistry_source:
            rationale += " Soil values are typical for your soil type, not measured."
        if fit.out_of_region and regional is not None:
            from agro_mirai.models.explanation_service import _regional_fit_note

            rationale += _regional_fit_note(
                CropRecommendation(
                    id="", field_id="", created_at=datetime.now(timezone.utc),
                    recommended_crop=best.crop, confidence=best.score,
                    out_of_region=fit.out_of_region,
                    regional_alternative=fit.regional_alternative,
                )
            )

        return CropRecommendation(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=datetime.now(timezone.utc),
            recommended_crop=best.crop,
            confidence=float(best.score),
            alternatives=alternatives,
            rationale=rationale,
            season=features.season,
            out_of_region=fit.out_of_region,
            regional_alternative=fit.regional_alternative,
        )
