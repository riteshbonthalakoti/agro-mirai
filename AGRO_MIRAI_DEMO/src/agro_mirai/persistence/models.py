"""Domain dataclasses — one per entity in ``specs/core/schema.yaml``.

Field names, types, and required/optional-ness are a 1:1 mirror of the
schema. Nothing engine-specific (no ORM base class, no SQL types) lives
here; ``sqlite_store.py`` / ``supabase_store.py`` translate to/from these.

Timestamps are timezone-aware ``datetime`` in UTC in memory (per
``repository-interface.md`` design rule 6); stores serialise to/from
their engine's native representation at the boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Farmer:
    id: str
    created_at: datetime
    updated_at: datetime
    name: str
    preferred_language: str
    phone: str | None = None
    district: str | None = None
    state: str | None = None
    # Module 19 — multi-tenant auth (additive, see decisions/0017).
    email: str | None = None
    password_hash: str | None = None
    role: str = "farmer"
    # Module 30 — profile photo, stored as a base64 data URI (no
    # file-storage service exists yet).
    photo_url: str | None = None


@dataclass
class Field_:
    id: str
    farmer_id: str
    created_at: datetime
    updated_at: datetime
    name: str
    latitude: float
    longitude: float
    area_ha: float
    elevation_m: float | None = None
    soil_type: str | None = None
    current_crop: str | None = None
    sown_on: date | None = None


@dataclass
class WeatherReading:
    id: str
    field_id: str
    observed_at: datetime
    source: str
    temp_c: float
    is_forecast: bool
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_pct: float | None = None
    rainfall_mm: float | None = None
    wind_mps: float | None = None


@dataclass
class SoilSample:
    id: str
    field_id: str
    observed_at: datetime
    source: str
    ph: float | None = None
    nitrogen_mg_per_kg: float | None = None
    phosphorus_mg_per_kg: float | None = None
    potassium_mg_per_kg: float | None = None
    organic_carbon_pct: float | None = None
    moisture_pct: float | None = None


@dataclass
class NDVIReading:
    id: str
    field_id: str
    observed_at: datetime
    source: str
    ndvi: float
    cloud_cover_pct: float | None = None
    satellite: str | None = None


@dataclass
class CropRecommendation:
    id: str
    field_id: str
    created_at: datetime
    recommended_crop: str
    confidence: float
    alternatives: list[str] | None = None
    rationale: str | None = None
    season: str | None = None
    out_of_region: bool | None = None
    regional_alternative: str | None = None


@dataclass
class IrrigationAdvice:
    id: str
    field_id: str
    created_at: datetime
    recommended_depth_mm: float
    window_start_at: datetime
    window_end_at: datetime
    urgency: str
    rationale: str | None = None


@dataclass
class DiseaseRiskAlert:
    id: str
    field_id: str
    created_at: datetime
    disease: str
    risk_level: str
    confidence: float
    window_start_at: datetime | None = None
    window_end_at: datetime | None = None
    recommended_action: str | None = None
    source: str | None = None  # Module 21: "cnn" | "environmental" | "environmental_fallback"


@dataclass
class Advisory:
    id: str
    field_id: str
    created_at: datetime
    language: str
    title: str
    body: str
    severity: str
    source_refs: list[str] = field(default_factory=list)


@dataclass
class FeedbackEntry:
    id: str
    farmer_id: str
    advisory_id: str
    created_at: datetime
    rating: int
    helpful: bool
    comment: str | None = None


@dataclass
class BugReport:
    """A farmer-submitted in-app bug report -- deliberately separate from
    FeedbackEntry (no advisory_id/rating/helpful requirement); see
    migrations/sqlite/009_bug_reports.sql's header for why."""

    id: str
    farmer_id: str
    created_at: datetime
    category: str | None = None
    message: str | None = None
    photo_url: str | None = None
    app_version: str | None = None
    platform: str | None = None
