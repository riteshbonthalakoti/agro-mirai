"""Builds a ``FeatureVector`` for a ``Field`` from whatever the
``DataStore`` currently holds — the same fetch-then-build shape Module 05
was designed for, wired to a real repository instead of a fixture.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

from agro_mirai.persistence.models import Field_
from agro_mirai.persistence.store import DataStore
from agro_mirai.processing.feature_builder import FeatureBuilder, FeatureVector


def build_features_for_field(
    store: DataStore, farmer_id: str, field: Field_, as_of: date | None = None,
    refresh: bool = True,
) -> FeatureVector:
    as_of = as_of or datetime.now(timezone.utc).date()
    weather = store.list_weather_readings(farmer_id, field.id, limit=1000)
    # AGRO_WEATHER_REFRESH=0 turns the live refetch off (tests, offline runs)
    if refresh and os.environ.get("AGRO_WEATHER_REFRESH", "1") != "0":
        try:
            from agro_mirai.api.field_data_acquisition import ensure_fresh_weather

            if ensure_fresh_weather(store, farmer_id, field, as_of, weather):
                weather = store.list_weather_readings(farmer_id, field.id, limit=1000)
        except Exception:  # noqa: BLE001 - stale weather is better than no advice
            pass
    soil = store.list_soil_samples(farmer_id, field.id, limit=1000)
    ndvi = store.list_ndvi_readings(farmer_id, field.id, limit=1000)
    return FeatureBuilder.build(field, weather, soil, ndvi, as_of)
