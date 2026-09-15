"""``SupabaseDataStore`` — the prod implementation of ``DataStore``.

Talks to Supabase Postgres via the ``supabase-py`` client (PostgREST
under the hood), against the tables created by
``migrations/postgres/001_init.sql`` (applied out-of-band via the
``supabase`` CLI — see ``docs/TOOLING.md`` and
``decisions/0005-migration-generation.md``; this module never runs DDL
itself).

Credentials come from ``SUPABASE_URL`` / ``SUPABASE_KEY`` env vars
(placeholders documented in ``.env.example``, never committed for real).
Construction raises ``RuntimeError`` immediately if either is unset —
callers (including the parity test suite) are expected to catch that and
skip rather than limp along without a backend.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

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
from agro_mirai.persistence.store import ConflictError, NotFoundError


def _dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: str) -> datetime:
    # Postgres/PostgREST returns timestamptz as ISO8601 with offset, e.g.
    # "2026-08-25T09:00:00+00:00" — normalise via fromisoformat.
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class SupabaseDataStore:
    """Implements ``agro_mirai.persistence.store.DataStore`` against Supabase.

    Raises ``RuntimeError`` at construction time if ``SUPABASE_URL`` /
    ``SUPABASE_KEY`` are not set — see module docstring.
    """

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set to construct SupabaseDataStore "
                "(see .env.example)"
            )
        from supabase import Client, create_client  # local import: optional dep

        self._client: Client = create_client(url, key)

    # --- Farmer ---
    def get_farmer(self, farmer_id: str) -> Farmer | None:
        res = self._client.table("farmers").select("*").eq("id", farmer_id).execute()
        rows = res.data
        return self._row_to_farmer(rows[0]) if rows else None

    def save_farmer(self, farmer: Farmer) -> Farmer:
        existing = self.get_farmer(farmer.id)
        now = datetime.now(timezone.utc)
        created_at = existing.created_at if existing else (farmer.created_at or now)
        payload = {
            "id": farmer.id,
            "created_at": _dt(created_at),
            "updated_at": _dt(now),
            "name": farmer.name,
            "preferred_language": farmer.preferred_language,
            "phone": farmer.phone,
            "district": farmer.district,
            "state": farmer.state,
            "email": farmer.email,
            "password_hash": farmer.password_hash,
            "role": farmer.role or "farmer",
            "photo_url": farmer.photo_url,
        }
        try:
            self._client.table("farmers").upsert(payload).execute()
        except Exception as e:  # pragma: no cover - network/PostgREST errors
            raise ConflictError(str(e)) from e
        return self.get_farmer(farmer.id)  # type: ignore[return-value]

    def get_farmer_by_email(self, email: str) -> Farmer | None:
        """Module 19. See sqlite_store.py's twin for the contract."""
        res = self._client.table("farmers").select("*").eq("email", email).execute()
        rows = res.data
        return self._row_to_farmer(rows[0]) if rows else None

    def get_farmer_by_phone(self, phone: str) -> Farmer | None:
        """Module 27. See sqlite_store.py's twin for the contract."""
        res = self._client.table("farmers").select("*").eq("phone", phone).execute()
        rows = res.data
        return self._row_to_farmer(rows[0]) if rows else None

    def list_all_farmers(self, limit: int = 500) -> list[Farmer]:
        """Module 19. Admin-only, unscoped -- see repository-interface.md."""
        res = (
            self._client.table("farmers")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_farmer(r) for r in res.data]

    def list_all_fields(self, limit: int = 1000) -> list[Field_]:
        """Module 19. Admin-only, unscoped -- see repository-interface.md."""
        res = (
            self._client.table("fields")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_field(r) for r in res.data]

    def list_all_feedback_with_advisories(
        self, limit: int = 2000
    ) -> list[tuple[FeedbackEntry, Advisory]]:
        """Module 19. Admin-only. No PostgREST cross-table join helper is
        used here (keeps this store's PostgREST usage consistent with
        every other method); fetches feedback then advisories by id and
        joins client-side."""
        res = (
            self._client.table("feedback_entries")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        entries = [self._row_to_feedback(r) for r in res.data]
        if not entries:
            return []
        advisory_ids = sorted({e.advisory_id for e in entries})
        adv_res = self._client.table("advisories").select("*").in_("id", advisory_ids).execute()
        advisories = {r["id"]: self._row_to_advisory(r) for r in adv_res.data}
        pairs = []
        for e in entries:
            adv = advisories.get(e.advisory_id)
            if adv is not None:
                pairs.append((e, adv))
        return pairs

    @staticmethod
    def _row_to_farmer(row: dict) -> Farmer:
        return Farmer(
            id=row["id"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            name=row["name"],
            preferred_language=row["preferred_language"],
            phone=row.get("phone"),
            district=row.get("district"),
            state=row.get("state"),
            email=row.get("email"),
            password_hash=row.get("password_hash"),
            role=row.get("role") or "farmer",
            photo_url=row.get("photo_url"),
        )

    # --- Field ---
    def get_field(self, farmer_id: str, field_id: str) -> Field_ | None:
        res = (
            self._client.table("fields")
            .select("*")
            .eq("id", field_id)
            .eq("farmer_id", farmer_id)
            .execute()
        )
        rows = res.data
        return self._row_to_field(rows[0]) if rows else None

    def list_fields(self, farmer_id: str, limit: int = 50) -> list[Field_]:
        res = (
            self._client.table("fields")
            .select("*")
            .eq("farmer_id", farmer_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_field(r) for r in res.data]

    def save_field(self, farmer_id: str, field: Field_) -> Field_:
        if self.get_farmer(farmer_id) is None:
            raise NotFoundError(f"farmer {farmer_id!r} does not exist")
        existing = self.get_field(farmer_id, field.id)
        now = datetime.now(timezone.utc)
        created_at = existing.created_at if existing else (field.created_at or now)
        payload = {
            "id": field.id,
            "farmer_id": farmer_id,
            "created_at": _dt(created_at),
            "updated_at": _dt(now),
            "name": field.name,
            "latitude": field.latitude,
            "longitude": field.longitude,
            "area_ha": field.area_ha,
            "elevation_m": field.elevation_m,
            "soil_type": field.soil_type,
            "current_crop": field.current_crop,
            "sown_on": field.sown_on.isoformat() if field.sown_on else None,
        }
        try:
            self._client.table("fields").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        return self.get_field(farmer_id, field.id)  # type: ignore[return-value]

    def delete_field(self, farmer_id: str, field_id: str) -> bool:
        existing = self.get_field(farmer_id, field_id)
        if existing is None:
            return False
        self._client.table("fields").delete().eq("id", field_id).eq(
            "farmer_id", farmer_id
        ).execute()
        return True

    @staticmethod
    def _row_to_field(row: dict) -> Field_:
        return Field_(
            id=row["id"],
            farmer_id=row["farmer_id"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            area_ha=row["area_ha"],
            elevation_m=row.get("elevation_m"),
            soil_type=row.get("soil_type"),
            current_crop=row.get("current_crop"),
            sown_on=datetime.strptime(row["sown_on"], "%Y-%m-%d").date() if row.get("sown_on") else None,
        )

    def _require_owned_field(self, farmer_id: str, field_id: str) -> None:
        if self.get_field(farmer_id, field_id) is None:
            raise NotFoundError(f"field {field_id!r} not owned by farmer {farmer_id!r}")

    # --- WeatherReading ---
    def save_weather_reading(self, farmer_id: str, reading: WeatherReading) -> WeatherReading:
        self._require_owned_field(farmer_id, reading.field_id)
        payload = {
            "id": reading.id,
            "field_id": reading.field_id,
            "observed_at": _dt(reading.observed_at),
            "source": reading.source,
            "temp_c": reading.temp_c,
            "temp_min_c": reading.temp_min_c,
            "temp_max_c": reading.temp_max_c,
            "humidity_pct": reading.humidity_pct,
            "rainfall_mm": reading.rainfall_mm,
            "wind_mps": reading.wind_mps,
            "is_forecast": reading.is_forecast,
        }
        try:
            self._client.table("weather_readings").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("weather_readings").select("*").eq("id", reading.id).execute()
        return self._row_to_weather(res.data[0])

    def list_weather_readings(
        self, farmer_id: str, field_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[WeatherReading]:
        self._require_owned_field(farmer_id, field_id)
        q = self._client.table("weather_readings").select("*").eq("field_id", field_id)
        if since:
            q = q.gte("observed_at", _dt(since))
        res = q.order("observed_at", desc=True).limit(limit).execute()
        return [self._row_to_weather(r) for r in res.data]

    @staticmethod
    def _row_to_weather(row: dict) -> WeatherReading:
        return WeatherReading(
            id=row["id"],
            field_id=row["field_id"],
            observed_at=_parse_dt(row["observed_at"]),
            source=row["source"],
            temp_c=row["temp_c"],
            temp_min_c=row.get("temp_min_c"),
            temp_max_c=row.get("temp_max_c"),
            humidity_pct=row.get("humidity_pct"),
            rainfall_mm=row.get("rainfall_mm"),
            wind_mps=row.get("wind_mps"),
            is_forecast=bool(row["is_forecast"]),
        )

    # --- SoilSample ---
    def save_soil_sample(self, farmer_id: str, sample: SoilSample) -> SoilSample:
        self._require_owned_field(farmer_id, sample.field_id)
        payload = {
            "id": sample.id,
            "field_id": sample.field_id,
            "observed_at": _dt(sample.observed_at),
            "source": sample.source,
            "ph": sample.ph,
            "nitrogen_mg_per_kg": sample.nitrogen_mg_per_kg,
            "phosphorus_mg_per_kg": sample.phosphorus_mg_per_kg,
            "potassium_mg_per_kg": sample.potassium_mg_per_kg,
            "organic_carbon_pct": sample.organic_carbon_pct,
            "moisture_pct": sample.moisture_pct,
        }
        try:
            self._client.table("soil_samples").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("soil_samples").select("*").eq("id", sample.id).execute()
        return self._row_to_soil(res.data[0])

    def list_soil_samples(self, farmer_id: str, field_id: str, limit: int = 50) -> list[SoilSample]:
        self._require_owned_field(farmer_id, field_id)
        res = (
            self._client.table("soil_samples")
            .select("*")
            .eq("field_id", field_id)
            .order("observed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_soil(r) for r in res.data]

    @staticmethod
    def _row_to_soil(row: dict) -> SoilSample:
        return SoilSample(
            id=row["id"],
            field_id=row["field_id"],
            observed_at=_parse_dt(row["observed_at"]),
            source=row["source"],
            ph=row.get("ph"),
            nitrogen_mg_per_kg=row.get("nitrogen_mg_per_kg"),
            phosphorus_mg_per_kg=row.get("phosphorus_mg_per_kg"),
            potassium_mg_per_kg=row.get("potassium_mg_per_kg"),
            organic_carbon_pct=row.get("organic_carbon_pct"),
            moisture_pct=row.get("moisture_pct"),
        )

    # --- NDVIReading ---
    def save_ndvi_reading(self, farmer_id: str, reading: NDVIReading) -> NDVIReading:
        self._require_owned_field(farmer_id, reading.field_id)
        payload = {
            "id": reading.id,
            "field_id": reading.field_id,
            "observed_at": _dt(reading.observed_at),
            "source": reading.source,
            "ndvi": reading.ndvi,
            "cloud_cover_pct": reading.cloud_cover_pct,
            "satellite": reading.satellite,
        }
        try:
            self._client.table("ndvi_readings").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("ndvi_readings").select("*").eq("id", reading.id).execute()
        return self._row_to_ndvi(res.data[0])

    def list_ndvi_readings(
        self, farmer_id: str, field_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[NDVIReading]:
        self._require_owned_field(farmer_id, field_id)
        q = self._client.table("ndvi_readings").select("*").eq("field_id", field_id)
        if since:
            q = q.gte("observed_at", _dt(since))
        res = q.order("observed_at", desc=True).limit(limit).execute()
        return [self._row_to_ndvi(r) for r in res.data]

    @staticmethod
    def _row_to_ndvi(row: dict) -> NDVIReading:
        return NDVIReading(
            id=row["id"],
            field_id=row["field_id"],
            observed_at=_parse_dt(row["observed_at"]),
            source=row["source"],
            ndvi=row["ndvi"],
            cloud_cover_pct=row.get("cloud_cover_pct"),
            satellite=row.get("satellite"),
        )

    # --- CropRecommendation ---
    def save_crop_recommendation(
        self, farmer_id: str, recommendation: CropRecommendation
    ) -> CropRecommendation:
        self._require_owned_field(farmer_id, recommendation.field_id)
        payload = {
            "id": recommendation.id,
            "field_id": recommendation.field_id,
            "created_at": _dt(recommendation.created_at),
            "recommended_crop": recommendation.recommended_crop,
            "confidence": recommendation.confidence,
            "alternatives": recommendation.alternatives,
            "rationale": recommendation.rationale,
            "season": recommendation.season,
            "out_of_region": recommendation.out_of_region,
            "regional_alternative": recommendation.regional_alternative,
        }
        try:
            self._client.table("crop_recommendations").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = (
            self._client.table("crop_recommendations")
            .select("*")
            .eq("id", recommendation.id)
            .execute()
        )
        return self._row_to_crop_rec(res.data[0])

    def get_latest_crop_recommendation(
        self, farmer_id: str, field_id: str
    ) -> CropRecommendation | None:
        self._require_owned_field(farmer_id, field_id)
        res = (
            self._client.table("crop_recommendations")
            .select("*")
            .eq("field_id", field_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return self._row_to_crop_rec(res.data[0]) if res.data else None

    @staticmethod
    def _row_to_crop_rec(row: dict) -> CropRecommendation:
        return CropRecommendation(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_parse_dt(row["created_at"]),
            recommended_crop=row["recommended_crop"],
            confidence=row["confidence"],
            alternatives=row.get("alternatives"),
            rationale=row.get("rationale"),
            season=row.get("season"),
            out_of_region=row.get("out_of_region"),
            regional_alternative=row.get("regional_alternative"),
        )

    # --- IrrigationAdvice ---
    def save_irrigation_advice(self, farmer_id: str, advice: IrrigationAdvice) -> IrrigationAdvice:
        self._require_owned_field(farmer_id, advice.field_id)
        payload = {
            "id": advice.id,
            "field_id": advice.field_id,
            "created_at": _dt(advice.created_at),
            "recommended_depth_mm": advice.recommended_depth_mm,
            "window_start_at": _dt(advice.window_start_at),
            "window_end_at": _dt(advice.window_end_at),
            "urgency": advice.urgency,
            "rationale": advice.rationale,
        }
        try:
            self._client.table("irrigation_advices").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("irrigation_advices").select("*").eq("id", advice.id).execute()
        return self._row_to_irrigation(res.data[0])

    def get_latest_irrigation_advice(
        self, farmer_id: str, field_id: str
    ) -> IrrigationAdvice | None:
        self._require_owned_field(farmer_id, field_id)
        res = (
            self._client.table("irrigation_advices")
            .select("*")
            .eq("field_id", field_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return self._row_to_irrigation(res.data[0]) if res.data else None

    @staticmethod
    def _row_to_irrigation(row: dict) -> IrrigationAdvice:
        return IrrigationAdvice(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_parse_dt(row["created_at"]),
            recommended_depth_mm=row["recommended_depth_mm"],
            window_start_at=_parse_dt(row["window_start_at"]),
            window_end_at=_parse_dt(row["window_end_at"]),
            urgency=row["urgency"],
            rationale=row.get("rationale"),
        )

    # --- DiseaseRiskAlert ---
    def save_disease_risk_alert(self, farmer_id: str, alert: DiseaseRiskAlert) -> DiseaseRiskAlert:
        self._require_owned_field(farmer_id, alert.field_id)
        payload = {
            "id": alert.id,
            "field_id": alert.field_id,
            "created_at": _dt(alert.created_at),
            "disease": alert.disease,
            "risk_level": alert.risk_level,
            "confidence": alert.confidence,
            "window_start_at": _dt(alert.window_start_at),
            "window_end_at": _dt(alert.window_end_at),
            "recommended_action": alert.recommended_action,
            "source": alert.source,
        }
        try:
            self._client.table("disease_risk_alerts").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("disease_risk_alerts").select("*").eq("id", alert.id).execute()
        return self._row_to_disease(res.data[0])

    def list_disease_risk_alerts(
        self, farmer_id: str, field_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[DiseaseRiskAlert]:
        self._require_owned_field(farmer_id, field_id)
        q = self._client.table("disease_risk_alerts").select("*").eq("field_id", field_id)
        if since:
            q = q.gte("created_at", _dt(since))
        res = q.order("created_at", desc=True).limit(limit).execute()
        return [self._row_to_disease(r) for r in res.data]

    @staticmethod
    def _row_to_disease(row: dict) -> DiseaseRiskAlert:
        return DiseaseRiskAlert(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_parse_dt(row["created_at"]),
            disease=row["disease"],
            risk_level=row["risk_level"],
            confidence=row["confidence"],
            window_start_at=_parse_dt(row["window_start_at"]) if row.get("window_start_at") else None,
            window_end_at=_parse_dt(row["window_end_at"]) if row.get("window_end_at") else None,
            recommended_action=row.get("recommended_action"),
            source=row.get("source"),
        )

    # --- Advisory ---
    def save_advisory(self, farmer_id: str, advisory: Advisory) -> Advisory:
        self._require_owned_field(farmer_id, advisory.field_id)
        payload = {
            "id": advisory.id,
            "field_id": advisory.field_id,
            "created_at": _dt(advisory.created_at),
            "language": advisory.language,
            "title": advisory.title,
            "body": advisory.body,
            "severity": advisory.severity,
            "source_refs": advisory.source_refs or [],
        }
        try:
            self._client.table("advisories").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("advisories").select("*").eq("id", advisory.id).execute()
        return self._row_to_advisory(res.data[0])

    def list_advisories_for_field(
        self, farmer_id: str, field_id: str, limit: int = 50
    ) -> list[Advisory]:
        self._require_owned_field(farmer_id, field_id)
        res = (
            self._client.table("advisories")
            .select("*")
            .eq("field_id", field_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_advisory(r) for r in res.data]

    def get_advisory(self, farmer_id: str, advisory_id: str) -> Advisory | None:
        res = self._client.table("advisories").select("*").eq("id", advisory_id).execute()
        if not res.data:
            return None
        row = res.data[0]
        if self.get_field(farmer_id, row["field_id"]) is None:
            return None
        return self._row_to_advisory(row)

    @staticmethod
    def _row_to_advisory(row: dict) -> Advisory:
        return Advisory(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_parse_dt(row["created_at"]),
            language=row["language"],
            title=row["title"],
            body=row["body"],
            severity=row["severity"],
            source_refs=row.get("source_refs") or [],
        )

    # --- FeedbackEntry ---
    def save_feedback_entry(self, farmer_id: str, entry: FeedbackEntry) -> FeedbackEntry:
        if self.get_advisory(farmer_id, entry.advisory_id) is None:
            raise NotFoundError(
                f"advisory {entry.advisory_id!r} not owned by farmer {farmer_id!r}"
            )
        payload = {
            "id": entry.id,
            "farmer_id": farmer_id,
            "advisory_id": entry.advisory_id,
            "created_at": _dt(entry.created_at),
            "rating": entry.rating,
            "helpful": entry.helpful,
            "comment": entry.comment,
        }
        try:
            self._client.table("feedback_entries").upsert(payload).execute()
        except Exception as e:  # pragma: no cover
            raise ConflictError(str(e)) from e
        res = self._client.table("feedback_entries").select("*").eq("id", entry.id).execute()
        return self._row_to_feedback(res.data[0])

    def list_feedback_for_advisory(
        self, farmer_id: str, advisory_id: str, limit: int = 50
    ) -> list[FeedbackEntry]:
        res = (
            self._client.table("feedback_entries")
            .select("*")
            .eq("advisory_id", advisory_id)
            .eq("farmer_id", farmer_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_feedback(r) for r in res.data]

    def list_feedback_for_farmer(
        self, farmer_id: str, limit: int = 200
    ) -> list[FeedbackEntry]:
        """Return all feedback entries for the farmer, newest first."""
        res = (
            self._client.table("feedback_entries")
            .select("*")
            .eq("farmer_id", farmer_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_feedback(r) for r in res.data]

    @staticmethod
    def _row_to_feedback(row: dict) -> FeedbackEntry:
        return FeedbackEntry(
            id=row["id"],
            farmer_id=row["farmer_id"],
            advisory_id=row["advisory_id"],
            created_at=_parse_dt(row["created_at"]),
            rating=row["rating"],
            helpful=bool(row["helpful"]),
            comment=row.get("comment"),
        )

    # --- Health ---
    def ping(self) -> bool:
        try:
            self._client.table("farmers").select("id").limit(1).execute()
            return True
        except Exception:
            return False
