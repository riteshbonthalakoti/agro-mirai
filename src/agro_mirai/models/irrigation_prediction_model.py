"""``IrrigationPredictionModel`` — loads the trained artifact, predicts.

Wraps the sklearn ``RandomForestClassifier`` trained by
``tools/train_irrigation_model.py`` so callers (Modules 09-10) never
touch sklearn directly. Input is a Module 05 ``FeatureVector``; output
is a schema-valid ``IrrigationAdvice``
(``src/agro_mirai/persistence/models.py``), per ``specs/core/schema.yaml``.

``urgency`` used to come from a RandomForest (72% accuracy, barely useful);
it is now worked out from the same FAO-56 water balance as the depth, see
``_urgency_from_deficit`` below and decisions/0027. No model file is needed
any more, so the ``model_path`` argument is only kept for old callers.
``recommended_depth_mm`` is now derived from an ET0 (Hargreaves-Samani)
x Kc water balance against ``rainfall_mm_sum_7d``, not a fixed lookup
keyed off urgency — see ``decisions/0015-et0-water-balance.md``, which
supersedes the relevant section of
``decisions/0008-irrigation-model-feature-mapping.md``. The advisory
window length (``window_start_at``/``window_end_at``) still comes from
``_URGENCY_TO_WINDOW_DAYS`` — the classifier's low/moderate/high signal
is a reasonable proxy for "how soon should this be acted on" and
ADR 0015 documents why that part of ADR 0008 was kept rather than
recomputed from the deficit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agro_mirai.models.crop_coefficients import growth_stage_for, kc_for
from agro_mirai.models.evapotranspiration import hargreaves_samani_et0
from agro_mirai.persistence.models import IrrigationAdvice
from agro_mirai.processing.feature_builder import FeatureVector

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "models"
    / "irrigation_rf.joblib"
)

# Share of the 7-day crop water demand that rain did NOT cover. Cut-offs
# are a judgement call around FAO-56's usual 50% allowable depletion.
_MODERATE_DEFICIT_SHARE = 0.35
_HIGH_DEFICIT_SHARE = 0.70

_URGENCY_TO_WINDOW_DAYS = {
    "low": 5,
    "moderate": 3,
    "high": 1,
    "severe": 1,
}

# Fallback diurnal temperature range (Tmax - Tmin) used only when a
# field's WeatherReading history has temp_c_mean but no temp_min_c/
# temp_max_c at all (both are optional per the schema, even though
# Open-Meteo — this project's only weather source, see
# src/agro_mirai/acquisition/open_meteo.py — populates them in
# practice). 8C is a documented, approximate typical diurnal swing for
# semi-arid/tropical Indian cropping regions rather than a precise
# per-field value; see decisions/0015-et0-water-balance.md.
_FALLBACK_DIURNAL_RANGE_C = 8.0

# Minimum window (days) over which the deficit is applied when
# computing recommended_depth_mm, independent of the advisory window
# above — the deficit itself is always measured over the 7-day window
# feeding rainfall_mm_sum_7d (see decisions/0015-et0-water-balance.md).
_DEFICIT_WINDOW_DAYS = 7.0


def _water_balance(features: FeatureVector) -> tuple[float, float, float, float]:
    """Returns (et0_mm_day, etc_mm_day, deficit_mm, depth_mm).

    ETc = ET0 * Kc (crop evapotranspiration, mm/day) over
    ``_DEFICIT_WINDOW_DAYS``, minus ``rainfall_mm_sum_7d`` already
    received -> net deficit, floored at 0 (a rainfall surplus doesn't
    produce a negative recommended depth).
    """
    # Degrade-not-fail: prefer the 7-day mean, but a field whose weather
    # history has a gap in the last 7 days (new farmer, an acquisition
    # outage, or — as discovered live — a golden fixture whose dates
    # aged out of the window) still has a usable, just-less-precise
    # temperature signal in the 14d/30d aggregates. Same fallback
    # philosophy as the tmin/tmax diurnal-range approximation below and
    # the GEE/CNN fallback paths elsewhere in this project — only raise
    # once every window is genuinely empty.
    temp_mean = (
        features.temp_c_mean_7d
        if features.temp_c_mean_7d is not None
        else features.temp_c_mean_14d
        if features.temp_c_mean_14d is not None
        else features.temp_c_mean_30d
    )
    temp_min = features.temp_c_min_7d
    temp_max = features.temp_c_max_7d
    if temp_mean is None:
        raise ValueError(
            "FeatureVector has no usable temperature mean (7d/14d/30d all "
            "None) — the ET0 water balance cannot run"
        )
    if temp_min is None or temp_max is None:
        # Documented fallback: approximate the missing extreme(s) with a
        # symmetric offset from the mean using the typical diurnal range.
        half_range = _FALLBACK_DIURNAL_RANGE_C / 2.0
        temp_min = temp_mean - half_range if temp_min is None else temp_min
        temp_max = temp_mean + half_range if temp_max is None else temp_max

    day_of_year = features.as_of.timetuple().tm_yday
    latitude = features.latitude if features.latitude is not None else 0.0

    et0 = hargreaves_samani_et0(
        temp_mean_c=temp_mean,
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        latitude_deg=latitude,
        day_of_year=day_of_year,
    )

    stage = growth_stage_for(features.crop_type, features.days_since_sowing)
    kc = kc_for(features.crop_type, stage)
    etc = et0 * kc

    demand_mm = etc * _DEFICIT_WINDOW_DAYS
    rainfall_mm = features.rainfall_mm_sum_7d
    deficit_mm = max(0.0, demand_mm - rainfall_mm)

    # A near-zero deficit still gets a small floor so "no rain needed
    # right now" isn't reported as a literal 0.0mm advisory, which reads
    # as broken rather than "conditions are fine".
    depth_mm = max(deficit_mm, 2.0)
    return et0, etc, deficit_mm, depth_mm


def _urgency_from_deficit(deficit_mm: float, demand_mm: float) -> str:
    if demand_mm <= 0:
        return "low"
    share = deficit_mm / demand_mm
    if share >= _HIGH_DEFICIT_SHARE:
        return "high"
    if share >= _MODERATE_DEFICIT_SHARE:
        return "moderate"
    return "low"


class IrrigationPredictionModel:
    def __init__(self, model_path: Path | None = None):
        # no trained artifact any more; model_path is ignored
        self._model = None

    def predict(self, features: FeatureVector) -> IrrigationAdvice:
        et0, etc, deficit_mm, depth_mm = _water_balance(features)
        urgency = _urgency_from_deficit(deficit_mm, etc * _DEFICIT_WINDOW_DAYS)

        created_at = datetime.now(timezone.utc)
        window_days = _URGENCY_TO_WINDOW_DAYS[urgency]
        soil_note = (
            f"soil moisture {features.soil_moisture_pct:.1f}%"
            if features.soil_moisture_pct is not None
            else "soil moisture not available"
        )

        return IrrigationAdvice(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=created_at,
            recommended_depth_mm=round(depth_mm, 1),
            window_start_at=created_at,
            window_end_at=created_at + timedelta(days=window_days),
            urgency=urgency,
            rationale=(
                f"Predicted irrigation need: {'medium' if urgency == 'moderate' else urgency} "
                f"({soil_note}). Water balance: ET0="
                f"{et0:.2f}mm/day, crop ETc={etc:.2f}mm/day over "
                f"{_DEFICIT_WINDOW_DAYS:.0f} days minus "
                f"{features.rainfall_mm_sum_7d:.1f}mm rainfall received "
                f"= {deficit_mm:.1f}mm net deficit -> "
                f"{depth_mm:.1f}mm recommended."
            ),
        )
