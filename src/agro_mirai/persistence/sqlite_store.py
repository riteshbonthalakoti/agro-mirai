"""``SQLiteDataStore`` — the local-dev implementation of ``DataStore``.

Applies ``migrations/sqlite/001_init.sql`` against a local ``.db`` file
(or ``:memory:`` for tests) on construction, then implements every
method in ``specs/core/repository-interface.md``. Ownership is enforced
by scoping every farmer-owned query with ``farmer_id`` (design rule 3);
not-found reads return ``None`` (design rule 4); timestamps are
timezone-aware UTC ``datetime`` in the public API and ISO-8601 TEXT on
disk (design rule 6).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date, datetime, timezone
from pathlib import Path

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

ROOT = Path(__file__).resolve().parent.parent.parent.parent
MIGRATION_PATH = ROOT / "migrations" / "sqlite" / "001_init.sql"


# --------------------------------------------------------------------------
# (De)serialisation helpers
# --------------------------------------------------------------------------
def _dt_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text_to_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _date_to_text(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _text_to_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


class SQLiteDataStore:
    """Implements ``agro_mirai.persistence.store.DataStore`` against SQLite."""

    def __init__(self, db_path: str = "agro_mirai.db") -> None:
        self.db_path = db_path
        self._local = threading.local()
        self._apply_migration()

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    @property
    def _conn(self) -> sqlite3.Connection:
        # sqlite3 connections aren't safe to share across threads, and
        # Flask's dev server (and any real WSGI server) dispatches each
        # request on its own thread — so each thread gets its own
        # lazily-opened connection to the same on-disk database file.
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._new_connection()
            self._local.conn = conn
        return conn

    def _apply_migration(self) -> None:
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        conn = self._conn
        conn.executescript(sql)
        conn.commit()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # --- Farmer ---
    def get_farmer(self, farmer_id: str) -> Farmer | None:
        row = self._conn.execute(
            "SELECT * FROM farmers WHERE id = ?", (farmer_id,)
        ).fetchone()
        return self._row_to_farmer(row) if row else None

    def save_farmer(self, farmer: Farmer) -> Farmer:
        now = datetime.now(timezone.utc)
        existing = self._conn.execute(
            "SELECT id, created_at FROM farmers WHERE id = ?", (farmer.id,)
        ).fetchone()
        created_at = _text_to_dt(existing["created_at"]) if existing else (farmer.created_at or now)
        updated_at = now
        self._conn.execute(
            """
            INSERT INTO farmers (id, created_at, updated_at, name, preferred_language, phone, district, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at=excluded.updated_at, name=excluded.name,
                preferred_language=excluded.preferred_language, phone=excluded.phone,
                district=excluded.district, state=excluded.state
            """,
            (
                farmer.id,
                _dt_to_text(created_at),
                _dt_to_text(updated_at),
                farmer.name,
                farmer.preferred_language,
                farmer.phone,
                farmer.district,
                farmer.state,
            ),
        )
        self._conn.commit()
        return self.get_farmer(farmer.id)  # type: ignore[return-value]

    @staticmethod
    def _row_to_farmer(row: sqlite3.Row) -> Farmer:
        return Farmer(
            id=row["id"],
            created_at=_text_to_dt(row["created_at"]),
            updated_at=_text_to_dt(row["updated_at"]),
            name=row["name"],
            preferred_language=row["preferred_language"],
            phone=row["phone"],
            district=row["district"],
            state=row["state"],
        )

    # --- Field ---
    def get_field(self, farmer_id: str, field_id: str) -> Field_ | None:
        row = self._conn.execute(
            "SELECT * FROM fields WHERE id = ? AND farmer_id = ?", (field_id, farmer_id)
        ).fetchone()
        return self._row_to_field(row) if row else None

    def list_fields(self, farmer_id: str, limit: int = 50) -> list[Field_]:
        rows = self._conn.execute(
            "SELECT * FROM fields WHERE farmer_id = ? ORDER BY created_at DESC LIMIT ?",
            (farmer_id, limit),
        ).fetchall()
        return [self._row_to_field(r) for r in rows]

    def save_field(self, farmer_id: str, field: Field_) -> Field_:
        if self.get_farmer(farmer_id) is None:
            raise NotFoundError(f"farmer {farmer_id!r} does not exist")
        now = datetime.now(timezone.utc)
        existing = self._conn.execute(
            "SELECT id, created_at FROM fields WHERE id = ? AND farmer_id = ?",
            (field.id, farmer_id),
        ).fetchone()
        created_at = _text_to_dt(existing["created_at"]) if existing else (field.created_at or now)
        self._conn.execute(
            """
            INSERT INTO fields (id, farmer_id, created_at, updated_at, name, latitude, longitude,
                area_ha, elevation_m, soil_type, current_crop, sown_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at=excluded.updated_at, name=excluded.name, latitude=excluded.latitude,
                longitude=excluded.longitude, area_ha=excluded.area_ha, elevation_m=excluded.elevation_m,
                soil_type=excluded.soil_type, current_crop=excluded.current_crop, sown_on=excluded.sown_on
            """,
            (
                field.id,
                farmer_id,
                _dt_to_text(created_at),
                _dt_to_text(now),
                field.name,
                field.latitude,
                field.longitude,
                field.area_ha,
                field.elevation_m,
                field.soil_type,
                field.current_crop,
                _date_to_text(field.sown_on) if field.sown_on else None,
            ),
        )
        self._conn.commit()
        return self.get_field(farmer_id, field.id)  # type: ignore[return-value]

    def delete_field(self, farmer_id: str, field_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM fields WHERE id = ? AND farmer_id = ?", (field_id, farmer_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_field(row: sqlite3.Row) -> Field_:
        return Field_(
            id=row["id"],
            farmer_id=row["farmer_id"],
            created_at=_text_to_dt(row["created_at"]),
            updated_at=_text_to_dt(row["updated_at"]),
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            area_ha=row["area_ha"],
            elevation_m=row["elevation_m"],
            soil_type=row["soil_type"],
            current_crop=row["current_crop"],
            sown_on=_text_to_date(row["sown_on"]) if row["sown_on"] else None,
        )

    # --- shared: verify field is owned by farmer ---
    def _require_owned_field(self, farmer_id: str, field_id: str) -> None:
        if self.get_field(farmer_id, field_id) is None:
            raise NotFoundError(f"field {field_id!r} not owned by farmer {farmer_id!r}")

    # --- WeatherReading ---
    def save_weather_reading(self, farmer_id: str, reading: WeatherReading) -> WeatherReading:
        self._require_owned_field(farmer_id, reading.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO weather_readings (id, field_id, observed_at, source, temp_c, temp_min_c,
                    temp_max_c, humidity_pct, rainfall_mm, wind_mps, is_forecast)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reading.id,
                    reading.field_id,
                    _dt_to_text(reading.observed_at),
                    reading.source,
                    reading.temp_c,
                    reading.temp_min_c,
                    reading.temp_max_c,
                    reading.humidity_pct,
                    reading.rainfall_mm,
                    reading.wind_mps,
                    1 if reading.is_forecast else 0,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute(
            "SELECT * FROM weather_readings WHERE id = ?", (reading.id,)
        ).fetchone()
        return self._row_to_weather(row)

    def list_weather_readings(
        self, farmer_id: str, field_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[WeatherReading]:
        self._require_owned_field(farmer_id, field_id)
        if since:
            rows = self._conn.execute(
                "SELECT * FROM weather_readings WHERE field_id = ? AND observed_at >= ? "
                "ORDER BY observed_at DESC LIMIT ?",
                (field_id, _dt_to_text(since), limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM weather_readings WHERE field_id = ? ORDER BY observed_at DESC LIMIT ?",
                (field_id, limit),
            ).fetchall()
        return [self._row_to_weather(r) for r in rows]

    @staticmethod
    def _row_to_weather(row: sqlite3.Row) -> WeatherReading:
        return WeatherReading(
            id=row["id"],
            field_id=row["field_id"],
            observed_at=_text_to_dt(row["observed_at"]),
            source=row["source"],
            temp_c=row["temp_c"],
            temp_min_c=row["temp_min_c"],
            temp_max_c=row["temp_max_c"],
            humidity_pct=row["humidity_pct"],
            rainfall_mm=row["rainfall_mm"],
            wind_mps=row["wind_mps"],
            is_forecast=bool(row["is_forecast"]),
        )

    # --- SoilSample ---
    def save_soil_sample(self, farmer_id: str, sample: SoilSample) -> SoilSample:
        self._require_owned_field(farmer_id, sample.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO soil_samples (id, field_id, observed_at, source, ph, nitrogen_mg_per_kg,
                    phosphorus_mg_per_kg, potassium_mg_per_kg, organic_carbon_pct, moisture_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample.id,
                    sample.field_id,
                    _dt_to_text(sample.observed_at),
                    sample.source,
                    sample.ph,
                    sample.nitrogen_mg_per_kg,
                    sample.phosphorus_mg_per_kg,
                    sample.potassium_mg_per_kg,
                    sample.organic_carbon_pct,
                    sample.moisture_pct,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute("SELECT * FROM soil_samples WHERE id = ?", (sample.id,)).fetchone()
        return self._row_to_soil(row)

    def list_soil_samples(self, farmer_id: str, field_id: str, limit: int = 50) -> list[SoilSample]:
        self._require_owned_field(farmer_id, field_id)
        rows = self._conn.execute(
            "SELECT * FROM soil_samples WHERE field_id = ? ORDER BY observed_at DESC LIMIT ?",
            (field_id, limit),
        ).fetchall()
        return [self._row_to_soil(r) for r in rows]

    @staticmethod
    def _row_to_soil(row: sqlite3.Row) -> SoilSample:
        return SoilSample(
            id=row["id"],
            field_id=row["field_id"],
            observed_at=_text_to_dt(row["observed_at"]),
            source=row["source"],
            ph=row["ph"],
            nitrogen_mg_per_kg=row["nitrogen_mg_per_kg"],
            phosphorus_mg_per_kg=row["phosphorus_mg_per_kg"],
            potassium_mg_per_kg=row["potassium_mg_per_kg"],
            organic_carbon_pct=row["organic_carbon_pct"],
            moisture_pct=row["moisture_pct"],
        )

    # --- NDVIReading ---
    def save_ndvi_reading(self, farmer_id: str, reading: NDVIReading) -> NDVIReading:
        self._require_owned_field(farmer_id, reading.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO ndvi_readings (id, field_id, observed_at, source, ndvi, cloud_cover_pct, satellite)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reading.id,
                    reading.field_id,
                    _dt_to_text(reading.observed_at),
                    reading.source,
                    reading.ndvi,
                    reading.cloud_cover_pct,
                    reading.satellite,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute("SELECT * FROM ndvi_readings WHERE id = ?", (reading.id,)).fetchone()
        return self._row_to_ndvi(row)

    def list_ndvi_readings(
        self, farmer_id: str, field_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[NDVIReading]:
        self._require_owned_field(farmer_id, field_id)
        if since:
            rows = self._conn.execute(
                "SELECT * FROM ndvi_readings WHERE field_id = ? AND observed_at >= ? "
                "ORDER BY observed_at DESC LIMIT ?",
                (field_id, _dt_to_text(since), limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM ndvi_readings WHERE field_id = ? ORDER BY observed_at DESC LIMIT ?",
                (field_id, limit),
            ).fetchall()
        return [self._row_to_ndvi(r) for r in rows]

    @staticmethod
    def _row_to_ndvi(row: sqlite3.Row) -> NDVIReading:
        return NDVIReading(
            id=row["id"],
            field_id=row["field_id"],
            observed_at=_text_to_dt(row["observed_at"]),
            source=row["source"],
            ndvi=row["ndvi"],
            cloud_cover_pct=row["cloud_cover_pct"],
            satellite=row["satellite"],
        )

    # --- CropRecommendation ---
    def save_crop_recommendation(
        self, farmer_id: str, recommendation: CropRecommendation
    ) -> CropRecommendation:
        self._require_owned_field(farmer_id, recommendation.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO crop_recommendations (id, field_id, created_at, recommended_crop, confidence,
                    alternatives, rationale, season)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation.id,
                    recommendation.field_id,
                    _dt_to_text(recommendation.created_at),
                    recommendation.recommended_crop,
                    recommendation.confidence,
                    json.dumps(recommendation.alternatives) if recommendation.alternatives else None,
                    recommendation.rationale,
                    recommendation.season,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute(
            "SELECT * FROM crop_recommendations WHERE id = ?", (recommendation.id,)
        ).fetchone()
        return self._row_to_crop_rec(row)

    def get_latest_crop_recommendation(
        self, farmer_id: str, field_id: str
    ) -> CropRecommendation | None:
        self._require_owned_field(farmer_id, field_id)
        row = self._conn.execute(
            "SELECT * FROM crop_recommendations WHERE field_id = ? ORDER BY created_at DESC LIMIT 1",
            (field_id,),
        ).fetchone()
        return self._row_to_crop_rec(row) if row else None

    @staticmethod
    def _row_to_crop_rec(row: sqlite3.Row) -> CropRecommendation:
        return CropRecommendation(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_text_to_dt(row["created_at"]),
            recommended_crop=row["recommended_crop"],
            confidence=row["confidence"],
            alternatives=json.loads(row["alternatives"]) if row["alternatives"] else None,
            rationale=row["rationale"],
            season=row["season"],
        )

    # --- IrrigationAdvice ---
    def save_irrigation_advice(self, farmer_id: str, advice: IrrigationAdvice) -> IrrigationAdvice:
        self._require_owned_field(farmer_id, advice.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO irrigation_advices (id, field_id, created_at, recommended_depth_mm,
                    window_start_at, window_end_at, urgency, rationale)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    advice.id,
                    advice.field_id,
                    _dt_to_text(advice.created_at),
                    advice.recommended_depth_mm,
                    _dt_to_text(advice.window_start_at),
                    _dt_to_text(advice.window_end_at),
                    advice.urgency,
                    advice.rationale,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute(
            "SELECT * FROM irrigation_advices WHERE id = ?", (advice.id,)
        ).fetchone()
        return self._row_to_irrigation(row)

    def get_latest_irrigation_advice(
        self, farmer_id: str, field_id: str
    ) -> IrrigationAdvice | None:
        self._require_owned_field(farmer_id, field_id)
        row = self._conn.execute(
            "SELECT * FROM irrigation_advices WHERE field_id = ? ORDER BY created_at DESC LIMIT 1",
            (field_id,),
        ).fetchone()
        return self._row_to_irrigation(row) if row else None

    @staticmethod
    def _row_to_irrigation(row: sqlite3.Row) -> IrrigationAdvice:
        return IrrigationAdvice(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_text_to_dt(row["created_at"]),
            recommended_depth_mm=row["recommended_depth_mm"],
            window_start_at=_text_to_dt(row["window_start_at"]),
            window_end_at=_text_to_dt(row["window_end_at"]),
            urgency=row["urgency"],
            rationale=row["rationale"],
        )

    # --- DiseaseRiskAlert ---
    def save_disease_risk_alert(self, farmer_id: str, alert: DiseaseRiskAlert) -> DiseaseRiskAlert:
        self._require_owned_field(farmer_id, alert.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO disease_risk_alerts (id, field_id, created_at, disease, risk_level,
                    confidence, window_start_at, window_end_at, recommended_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.id,
                    alert.field_id,
                    _dt_to_text(alert.created_at),
                    alert.disease,
                    alert.risk_level,
                    alert.confidence,
                    _dt_to_text(alert.window_start_at) if alert.window_start_at else None,
                    _dt_to_text(alert.window_end_at) if alert.window_end_at else None,
                    alert.recommended_action,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute(
            "SELECT * FROM disease_risk_alerts WHERE id = ?", (alert.id,)
        ).fetchone()
        return self._row_to_disease(row)

    def list_disease_risk_alerts(
        self, farmer_id: str, field_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[DiseaseRiskAlert]:
        self._require_owned_field(farmer_id, field_id)
        if since:
            rows = self._conn.execute(
                "SELECT * FROM disease_risk_alerts WHERE field_id = ? AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT ?",
                (field_id, _dt_to_text(since), limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM disease_risk_alerts WHERE field_id = ? ORDER BY created_at DESC LIMIT ?",
                (field_id, limit),
            ).fetchall()
        return [self._row_to_disease(r) for r in rows]

    @staticmethod
    def _row_to_disease(row: sqlite3.Row) -> DiseaseRiskAlert:
        return DiseaseRiskAlert(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_text_to_dt(row["created_at"]),
            disease=row["disease"],
            risk_level=row["risk_level"],
            confidence=row["confidence"],
            window_start_at=_text_to_dt(row["window_start_at"]) if row["window_start_at"] else None,
            window_end_at=_text_to_dt(row["window_end_at"]) if row["window_end_at"] else None,
            recommended_action=row["recommended_action"],
        )

    # --- Advisory ---
    def save_advisory(self, farmer_id: str, advisory: Advisory) -> Advisory:
        self._require_owned_field(farmer_id, advisory.field_id)
        try:
            self._conn.execute(
                """
                INSERT INTO advisories (id, field_id, created_at, language, title, body, severity, source_refs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    advisory.id,
                    advisory.field_id,
                    _dt_to_text(advisory.created_at),
                    advisory.language,
                    advisory.title,
                    advisory.body,
                    advisory.severity,
                    json.dumps(advisory.source_refs) if advisory.source_refs else None,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute("SELECT * FROM advisories WHERE id = ?", (advisory.id,)).fetchone()
        return self._row_to_advisory(row)

    def list_advisories_for_field(
        self, farmer_id: str, field_id: str, limit: int = 50
    ) -> list[Advisory]:
        self._require_owned_field(farmer_id, field_id)
        rows = self._conn.execute(
            "SELECT * FROM advisories WHERE field_id = ? ORDER BY created_at DESC LIMIT ?",
            (field_id, limit),
        ).fetchall()
        return [self._row_to_advisory(r) for r in rows]

    def get_advisory(self, farmer_id: str, advisory_id: str) -> Advisory | None:
        row = self._conn.execute(
            """
            SELECT advisories.* FROM advisories
            JOIN fields ON fields.id = advisories.field_id
            WHERE advisories.id = ? AND fields.farmer_id = ?
            """,
            (advisory_id, farmer_id),
        ).fetchone()
        return self._row_to_advisory(row) if row else None

    @staticmethod
    def _row_to_advisory(row: sqlite3.Row) -> Advisory:
        return Advisory(
            id=row["id"],
            field_id=row["field_id"],
            created_at=_text_to_dt(row["created_at"]),
            language=row["language"],
            title=row["title"],
            body=row["body"],
            severity=row["severity"],
            source_refs=json.loads(row["source_refs"]) if row["source_refs"] else [],
        )

    # --- FeedbackEntry ---
    def save_feedback_entry(self, farmer_id: str, entry: FeedbackEntry) -> FeedbackEntry:
        if self.get_advisory(farmer_id, entry.advisory_id) is None:
            raise NotFoundError(
                f"advisory {entry.advisory_id!r} not owned by farmer {farmer_id!r}"
            )
        try:
            self._conn.execute(
                """
                INSERT INTO feedback_entries (id, farmer_id, advisory_id, created_at, rating, helpful, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    farmer_id,
                    entry.advisory_id,
                    _dt_to_text(entry.created_at),
                    entry.rating,
                    1 if entry.helpful else 0,
                    entry.comment,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(str(e)) from e
        row = self._conn.execute(
            "SELECT * FROM feedback_entries WHERE id = ?", (entry.id,)
        ).fetchone()
        return self._row_to_feedback(row)

    def list_feedback_for_advisory(
        self, farmer_id: str, advisory_id: str, limit: int = 50
    ) -> list[FeedbackEntry]:
        rows = self._conn.execute(
            "SELECT * FROM feedback_entries WHERE advisory_id = ? AND farmer_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (advisory_id, farmer_id, limit),
        ).fetchall()
        return [self._row_to_feedback(r) for r in rows]

    def list_feedback_for_farmer(
        self, farmer_id: str, limit: int = 200
    ) -> list[FeedbackEntry]:
        """Return all feedback entries for the farmer, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM feedback_entries WHERE farmer_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (farmer_id, limit),
        ).fetchall()
        return [self._row_to_feedback(r) for r in rows]

    @staticmethod
    def _row_to_feedback(row: sqlite3.Row) -> FeedbackEntry:
        return FeedbackEntry(
            id=row["id"],
            farmer_id=row["farmer_id"],
            advisory_id=row["advisory_id"],
            created_at=_text_to_dt(row["created_at"]),
            rating=row["rating"],
            helpful=bool(row["helpful"]),
            comment=row["comment"],
        )

    # --- Health ---
    def ping(self) -> bool:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
