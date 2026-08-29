"""``DataStore`` — the repository interface, per
``specs/core/repository-interface.md``.

Every module that needs to read or write domain records depends on this
``Protocol``, never on SQLite or Supabase directly (CLAUDE.md hard rule
#3). ``SQLiteDataStore`` and ``SupabaseDataStore`` both implement it in
full; a parity test suite (``tests/persistence/contract/``) runs the same
assertions against both.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from agro_mirai.persistence.models import (
    Advisory,
    CropRecommendation,
    DiseaseRiskAlert,
    Farmer,
    FeedbackEntry,
    Field_,
    IrrigationAdvice,
    NDVIReading,
    SoilSample,
    WeatherReading,
)


class NotFoundError(Exception):
    """Raised when a mutation targets a parent that does not exist or is
    not owned by the given farmer."""


class ConflictError(Exception):
    """Raised on unique-constraint violations (e.g. duplicate id)."""


@runtime_checkable
class DataStore(Protocol):
    """Engine-neutral persistence contract. See repository-interface.md
    for the full design rules (ownership enforcement, None-not-exception
    for reads, default limits, UTC timestamps in/out)."""

    # --- Farmer ---
    def get_farmer(self, farmer_id: str) -> Farmer | None: ...

    def save_farmer(self, farmer: Farmer) -> Farmer: ...

    def get_farmer_by_email(self, email: str) -> Farmer | None:
        """Module 19. Lookup for login/registration; None if no farmer
        has this email (or email was never set, e.g. a /v1-only record)."""
        ...

    def list_all_farmers(self, limit: int = 500) -> list[Farmer]:
        """Module 19. Admin-only, unscoped across every farmer -- callers
        must gate this behind an admin role check, the store does not."""
        ...

    def list_all_fields(self, limit: int = 1000) -> list[Field_]:
        """Module 19. Admin-only, unscoped across every farmer's fields."""
        ...

    def list_all_feedback_with_advisories(
        self, limit: int = 2000
    ) -> list[tuple[FeedbackEntry, Advisory]]:
        """Module 19. Admin-only. Every (FeedbackEntry, Advisory) pair
        system-wide, for FeedbackAggregator.aggregate scoped to
        "all farmers" instead of one."""
        ...

    # --- Field ---
    def get_field(self, farmer_id: str, field_id: str) -> Field_ | None: ...

    def list_fields(self, farmer_id: str, limit: int = 50) -> list[Field_]: ...

    def save_field(self, farmer_id: str, field: Field_) -> Field_: ...

    def delete_field(self, farmer_id: str, field_id: str) -> bool: ...

    # --- Readings and samples ---
    def save_weather_reading(
        self, farmer_id: str, reading: WeatherReading
    ) -> WeatherReading: ...

    def list_weather_readings(
        self,
        farmer_id: str,
        field_id: str,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[WeatherReading]: ...

    def save_soil_sample(self, farmer_id: str, sample: SoilSample) -> SoilSample: ...

    def list_soil_samples(
        self, farmer_id: str, field_id: str, limit: int = 50
    ) -> list[SoilSample]: ...

    def save_ndvi_reading(
        self, farmer_id: str, reading: NDVIReading
    ) -> NDVIReading: ...

    def list_ndvi_readings(
        self,
        farmer_id: str,
        field_id: str,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NDVIReading]: ...

    # --- Recommendations, advice, alerts ---
    def save_crop_recommendation(
        self, farmer_id: str, recommendation: CropRecommendation
    ) -> CropRecommendation: ...

    def get_latest_crop_recommendation(
        self, farmer_id: str, field_id: str
    ) -> CropRecommendation | None: ...

    def save_irrigation_advice(
        self, farmer_id: str, advice: IrrigationAdvice
    ) -> IrrigationAdvice: ...

    def get_latest_irrigation_advice(
        self, farmer_id: str, field_id: str
    ) -> IrrigationAdvice | None: ...

    def save_disease_risk_alert(
        self, farmer_id: str, alert: DiseaseRiskAlert
    ) -> DiseaseRiskAlert: ...

    def list_disease_risk_alerts(
        self,
        farmer_id: str,
        field_id: str,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[DiseaseRiskAlert]: ...

    # --- Advisories and feedback ---
    def save_advisory(self, farmer_id: str, advisory: Advisory) -> Advisory: ...

    def list_advisories_for_field(
        self, farmer_id: str, field_id: str, limit: int = 50
    ) -> list[Advisory]: ...

    def get_advisory(self, farmer_id: str, advisory_id: str) -> Advisory | None: ...

    def save_feedback_entry(
        self, farmer_id: str, entry: FeedbackEntry
    ) -> FeedbackEntry: ...

    def list_feedback_for_advisory(
        self, farmer_id: str, advisory_id: str, limit: int = 50
    ) -> list[FeedbackEntry]: ...

    def list_feedback_for_farmer(
        self, farmer_id: str, limit: int = 200
    ) -> list[FeedbackEntry]: ...

    # --- Health ---
    def ping(self) -> bool: ...
