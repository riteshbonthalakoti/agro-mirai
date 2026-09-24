"""Remote client for tabular ML microservice (decisions/0024-microservices-split).

Queries `TABULAR_SERVICE_URL` (`agro-mirai-tabular` on Render) for crop and
irrigation predictions, offloading Scikit-Learn RandomForest inference from the
main API service. Hard fallback to local models on network error or if URL is unset.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, date, timezone
import logging
import os
import requests

from agro_mirai.persistence.models import CropRecommendation, IrrigationAdvice
from agro_mirai.processing.feature_builder import FeatureVector

logger = logging.getLogger(__name__)


def _serialize_features(features: FeatureVector) -> dict:
    res = asdict(features)
    for k, v in res.items():
        if isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
    return res


def _post_with_retry(url: str, payload: dict, timeout_s: float):
    """One retry: a free-tier service that was just spun up or recycled often
    drops the first connection (observed: RemoteProtocolError 'Server disconnected')."""
    try:
        return requests.post(url, json=payload, timeout=timeout_s)
    except (requests.ConnectionError, requests.Timeout):
        return requests.post(url, json=payload, timeout=timeout_s * 2)


def _parse_datetime(val: str | datetime | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if val.endswith("Z"):
        val = val[:-1] + "+00:00"
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class RemoteCropModel:
    """Wrapper that tries TABULAR_SERVICE_URL first, falling back to local model."""

    def __init__(self, local_model=None, service_url: str | None = None, timeout_s: float = 15.0):
        self._local_model = local_model
        self._service_url = service_url or os.environ.get("TABULAR_SERVICE_URL", "").rstrip("/")
        self._timeout_s = timeout_s

    @property
    def _model(self):
        if self._local_model is None:
            from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
            self._local_model = CropRecommendationModel()
        return self._local_model._model

    def predict(self, features: FeatureVector, top_k: int = 3) -> CropRecommendation:
        if self._service_url:
            try:
                url = f"{self._service_url}/predict/crop"
                payload = {
                    "feature_vector": _serialize_features(features),
                    "top_k": top_k,
                }
                resp = _post_with_retry(url, payload, self._timeout_s)
                if resp.status_code == 200:
                    data = resp.json()
                    return CropRecommendation(
                        id=data["id"],
                        field_id=data["field_id"],
                        created_at=_parse_datetime(data["created_at"]),
                        recommended_crop=data["recommended_crop"],
                        confidence=float(data["confidence"]),
                        alternatives=data.get("alternatives"),
                        rationale=data.get("rationale"),
                        season=data.get("season"),
                        out_of_region=data.get("out_of_region"),
                        regional_alternative=data.get("regional_alternative"),
                    )
                logger.warning(f"Tabular service /predict/crop returned HTTP {resp.status_code}, falling back to local")
            except Exception as exc:
                logger.warning(f"Tabular service /predict/crop failed: {exc}, falling back to local")

        if self._local_model is None:
            from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
            self._local_model = CropRecommendationModel()
        return self._local_model.predict(features, top_k=top_k)


class RemoteIrrigationModel:
    """Wrapper that tries TABULAR_SERVICE_URL first, falling back to local model."""

    def __init__(self, local_model=None, service_url: str | None = None, timeout_s: float = 15.0):
        self._local_model = local_model
        self._service_url = service_url or os.environ.get("TABULAR_SERVICE_URL", "").rstrip("/")
        self._timeout_s = timeout_s

    @property
    def _model(self):
        if self._local_model is None:
            from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel
            self._local_model = IrrigationPredictionModel()
        return self._local_model._model

    def predict(self, features: FeatureVector) -> IrrigationAdvice:
        if self._service_url:
            try:
                url = f"{self._service_url}/predict/irrigation"
                payload = {
                    "feature_vector": _serialize_features(features),
                }
                resp = _post_with_retry(url, payload, self._timeout_s)
                if resp.status_code == 200:
                    data = resp.json()
                    return IrrigationAdvice(
                        id=data["id"],
                        field_id=data["field_id"],
                        created_at=_parse_datetime(data["created_at"]),
                        recommended_depth_mm=float(data["recommended_depth_mm"]),
                        window_start_at=_parse_datetime(data["window_start_at"]),
                        window_end_at=_parse_datetime(data["window_end_at"]),
                        urgency=data["urgency"],
                        rationale=data.get("rationale"),
                    )
                logger.warning(f"Tabular service /predict/irrigation returned HTTP {resp.status_code}, falling back to local")
            except Exception as exc:
                logger.warning(f"Tabular service /predict/irrigation failed: {exc}, falling back to local")

        if self._local_model is None:
            from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel
            self._local_model = IrrigationPredictionModel()
        return self._local_model.predict(features)
