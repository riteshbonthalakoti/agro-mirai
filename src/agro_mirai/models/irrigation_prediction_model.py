"""``IrrigationPredictionModel`` — loads the trained artifact, predicts.

Wraps the sklearn ``RandomForestClassifier`` trained by
``tools/train_irrigation_model.py`` so callers (Modules 09-10) never
touch sklearn directly. Input is a Module 05 ``FeatureVector``; output
is a schema-valid ``IrrigationAdvice``
(``src/agro_mirai/persistence/models.py``), per ``specs/core/schema.yaml``.

Only ``urgency`` is a trained classifier output. ``recommended_depth_mm``
and the ``window_start_at``/``window_end_at`` advisory window are a
documented rule-based lookup keyed off the predicted urgency — see
``decisions/0008-irrigation-model-feature-mapping.md`` for why no
dataset with a continuous depth-mm target was available.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from agro_mirai.models.irrigation_feature_mapping import (
    MODEL_FEATURE_COLUMNS,
    map_features,
)
from agro_mirai.persistence.models import IrrigationAdvice
from agro_mirai.processing.feature_builder import FeatureVector

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "models"
    / "irrigation_rf.joblib"
)

_LABEL_TO_URGENCY = {
    "Low": "low",
    "Medium": "moderate",
    "High": "high",
}

_URGENCY_TO_DEPTH_MM = {
    "low": 10.0,
    "moderate": 25.0,
    "high": 40.0,
    "severe": 50.0,
}

_URGENCY_TO_WINDOW_DAYS = {
    "low": 5,
    "moderate": 3,
    "high": 1,
    "severe": 1,
}


class IrrigationPredictionModel:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        if not model_path.exists():
            raise FileNotFoundError(
                f"{model_path} not found. Train it first:\n"
                "  python tools/train_irrigation_model.py"
            )
        import joblib

        self._model = joblib.load(model_path)

    def predict(self, features: FeatureVector) -> IrrigationAdvice:
        row = map_features(features)
        x = pd.DataFrame([row], columns=MODEL_FEATURE_COLUMNS)

        label = self._model.predict(x)[0]
        urgency = _LABEL_TO_URGENCY[label]

        created_at = datetime.now(timezone.utc)
        window_days = _URGENCY_TO_WINDOW_DAYS[urgency]

        return IrrigationAdvice(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=created_at,
            recommended_depth_mm=_URGENCY_TO_DEPTH_MM[urgency],
            window_start_at=created_at,
            window_end_at=created_at + timedelta(days=window_days),
            urgency=urgency,
            rationale=(
                f"Predicted irrigation need: {label.lower()} "
                f"(soil moisture {features.soil_moisture_pct:.1f}%, "
                f"season {features.season})"
            ),
        )
