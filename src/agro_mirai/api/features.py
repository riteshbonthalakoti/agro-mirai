"""Builds a ``FeatureVector`` for a ``Field`` from whatever the
``DataStore`` currently holds — the same fetch-then-build shape Module 05
was designed for, wired to a real repository instead of a fixture.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from agro_mirai.persistence.models import Field_
from agro_mirai.persistence.store import DataStore
from agro_mirai.processing.feature_builder import FeatureBuilder, FeatureVector


def build_features_for_field(
    store: DataStore, farmer_id: str, field: Field_, as_of: date | None = None
) -> FeatureVector:
    as_of = as_of or datetime.now(timezone.utc).date()
    weather = store.list_weather_readings(farmer_id, field.id, limit=1000)
    soil = store.list_soil_samples(farmer_id, field.id, limit=1000)
    ndvi = store.list_ndvi_readings(farmer_id, field.id, limit=1000)
    return FeatureBuilder.build(field, weather, soil, ndvi, as_of)
