"""``CropRecommendationModel`` — loads the trained artifact, predicts.

Wraps the sklearn ``RandomForestClassifier`` trained by
``tools/train_crop_model.py`` so callers (Modules 09-10) never touch
sklearn directly. Input is a Module 05 ``FeatureVector``; output is a
schema-valid ``CropRecommendation``
(``src/agro_mirai/persistence/models.py``), per ``specs/core/schema.yaml``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from agro_mirai.models.crop_feature_mapping import (
    MODEL_FEATURE_COLUMNS,
    map_features,
)
from agro_mirai.persistence.models import CropRecommendation
from agro_mirai.processing.feature_builder import FeatureVector

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "models" / "crop_rf.joblib"
)


class CropRecommendationModel:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        if not model_path.exists():
            raise FileNotFoundError(
                f"{model_path} not found. Train it first:\n"
                "  python tools/train_crop_model.py"
            )
        import joblib

        self._model = joblib.load(model_path)

    def predict(
        self, features: FeatureVector, top_k: int = 3
    ) -> CropRecommendation:
        """Predicts a crop for ``features``'s field.

        ``top_k`` bounds ``alternatives`` (the top-k crops by predicted
        probability, excluding the top prediction itself).
        """
        row = map_features(features)
        x = pd.DataFrame([row], columns=MODEL_FEATURE_COLUMNS)

        probabilities = self._model.predict_proba(x)[0]
        classes = self._model.classes_
        ranked = sorted(zip(classes, probabilities), key=lambda p: -p[1])

        recommended_crop, confidence = ranked[0]
        alternatives = [crop for crop, _ in ranked[1 : 1 + top_k]]

        return CropRecommendation(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=datetime.now(timezone.utc),
            recommended_crop=recommended_crop,
            confidence=float(confidence),
            alternatives=alternatives,
            season=features.season,
        )
