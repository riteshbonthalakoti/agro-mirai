"""``FeatureBuilder`` — turns raw readings into a ``FeatureVector``.

Implements exactly what ``specs/core/features.md`` documents, field for
field. Pure function of its inputs: a ``Field_`` plus plain lists of
``WeatherReading``/``SoilSample``/``NDVIReading`` (already fetched by the
caller via ``DataStore`` — this module never touches the store or the
network), and an ``as_of: date`` anchor. No hidden state, no
``datetime.now()`` calls internally.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from agro_mirai.persistence.models import (
    Field_,
    NDVIReading,
    SoilSample,
    WeatherReading,
)

WEATHER_WINDOWS_DAYS: tuple[int, ...] = (7, 14, 30)

_KHARIF_MONTHS = {6, 7}
_RABI_MONTHS = {10, 11, 12}
_ZAID_MONTHS = {3, 4, 5}


@dataclass
class FeatureVector:
    field_id: str
    as_of: date

    # weather aggregates (one triple per window in WEATHER_WINDOWS_DAYS)
    rainfall_mm_sum_7d: float
    temp_c_mean_7d: float | None
    humidity_pct_mean_7d: float | None
    rainfall_mm_sum_14d: float
    temp_c_mean_14d: float | None
    humidity_pct_mean_14d: float | None
    rainfall_mm_sum_30d: float
    temp_c_mean_30d: float | None
    humidity_pct_mean_30d: float | None

    # soil
    soil_data_available: bool
    soil_ph: float | None = None
    soil_nitrogen_mg_per_kg: float | None = None
    soil_phosphorus_mg_per_kg: float | None = None
    soil_potassium_mg_per_kg: float | None = None
    soil_organic_carbon_pct: float | None = None
    soil_moisture_pct: float | None = None
    soil_npk_balance_index: float | None = None

    # ndvi
    ndvi_data_available: bool = False
    ndvi_latest: float | None = None
    ndvi_trend: float | None = None
    ndvi_confidence_source: str | None = None

    # season / derived context
    season: str | None = None
    days_since_sowing: int | None = None

    # Module 17 additions (additive-only, specs/core/features.md):
    # ET0/water-balance inputs the irrigation model needs that weren't
    # previously exposed on the vector.
    temp_c_min_7d: float | None = None
    temp_c_max_7d: float | None = None
    latitude: float | None = None
    crop_type: str | None = None


class FeatureBuilder:
    """Stateless; ``build`` is the only entry point."""

    @staticmethod
    def build(
        field: Field_,
        weather_readings: list[WeatherReading],
        soil_samples: list[SoilSample],
        ndvi_readings: list[NDVIReading],
        as_of: date,
    ) -> FeatureVector:
        weather_in_range = [
            w for w in weather_readings if w.observed_at.date() <= as_of
        ]
        if not weather_in_range:
            raise ValueError(
                f"FeatureBuilder requires at least one WeatherReading with "
                f"observed_at <= as_of ({as_of.isoformat()}) for field "
                f"{field.id!r}; weather is asserted always-available "
                f"per Module 03 acquisition design"
            )

        weather_windows: dict[int, tuple[float, float | None, float | None]] = {}
        for window_days in WEATHER_WINDOWS_DAYS:
            weather_windows[window_days] = _weather_window(
                weather_in_range, as_of, window_days
            )

        soil_available, soil_features = _soil_features(soil_samples, as_of)
        ndvi_available, ndvi_latest, ndvi_trend, ndvi_source = _ndvi_features(
            ndvi_readings, as_of
        )
        season = _season_for(field.sown_on)
        days_since_sowing = _days_since_sowing(field.sown_on, as_of)

        r7, t7, h7 = weather_windows[7]
        r14, t14, h14 = weather_windows[14]
        r30, t30, h30 = weather_windows[30]
        tmin7, tmax7 = _temp_min_max_window(weather_in_range, as_of, 7)

        return FeatureVector(
            field_id=field.id,
            as_of=as_of,
            rainfall_mm_sum_7d=r7,
            temp_c_mean_7d=t7,
            humidity_pct_mean_7d=h7,
            rainfall_mm_sum_14d=r14,
            temp_c_mean_14d=t14,
            humidity_pct_mean_14d=h14,
            rainfall_mm_sum_30d=r30,
            temp_c_mean_30d=t30,
            humidity_pct_mean_30d=h30,
            soil_data_available=soil_available,
            ndvi_data_available=ndvi_available,
            ndvi_latest=ndvi_latest,
            ndvi_trend=ndvi_trend,
            ndvi_confidence_source=ndvi_source,
            season=season,
            days_since_sowing=days_since_sowing,
            temp_c_min_7d=tmin7,
            temp_c_max_7d=tmax7,
            latitude=field.latitude,
            crop_type=field.current_crop,
            **soil_features,
        )


def _weather_window(
    readings: list[WeatherReading], as_of: date, window_days: int
) -> tuple[float, float | None, float | None]:
    lower_exclusive = as_of.toordinal() - window_days
    windowed = [
        w
        for w in readings
        if lower_exclusive < w.observed_at.date().toordinal() <= as_of.toordinal()
    ]

    rainfall_sum = sum(w.rainfall_mm or 0.0 for w in windowed)

    temps = [w.temp_c for w in windowed]
    temp_mean = sum(temps) / len(temps) if temps else None

    humidities = [w.humidity_pct for w in windowed if w.humidity_pct is not None]
    humidity_mean = sum(humidities) / len(humidities) if humidities else None

    return rainfall_sum, temp_mean, humidity_mean


def _temp_min_max_window(
    readings: list[WeatherReading], as_of: date, window_days: int
) -> tuple[float | None, float | None]:
    """Mean of per-reading ``temp_min_c``/``temp_max_c`` over the window.

    Module 17 addition: the Hargreaves-Samani ET0 formula needs a daily
    Tmin/Tmax, which the original weather aggregates (mean-only) didn't
    expose. ``temp_min_c``/``temp_max_c`` are optional per-reading
    (unlike required ``temp_c``), so a reading missing either is skipped
    for that statistic rather than treated as 0 — same "skip None, empty
    window is None" policy as ``humidity_pct_mean``.
    """
    lower_exclusive = as_of.toordinal() - window_days
    windowed = [
        w
        for w in readings
        if lower_exclusive < w.observed_at.date().toordinal() <= as_of.toordinal()
    ]

    mins = [w.temp_min_c for w in windowed if w.temp_min_c is not None]
    maxs = [w.temp_max_c for w in windowed if w.temp_max_c is not None]

    temp_min_mean = sum(mins) / len(mins) if mins else None
    temp_max_mean = sum(maxs) / len(maxs) if maxs else None
    return temp_min_mean, temp_max_mean


def _soil_features(
    samples: list[SoilSample], as_of: date
) -> tuple[bool, dict[str, float | None]]:
    if not samples:
        return False, {
            "soil_ph": None,
            "soil_nitrogen_mg_per_kg": None,
            "soil_phosphorus_mg_per_kg": None,
            "soil_potassium_mg_per_kg": None,
            "soil_organic_carbon_pct": None,
            "soil_moisture_pct": None,
            "soil_npk_balance_index": None,
        }

    in_range = [s for s in samples if s.observed_at.date() <= as_of]
    pool = in_range if in_range else samples
    latest = max(pool, key=lambda s: s.observed_at)

    n = latest.nitrogen_mg_per_kg
    p = latest.phosphorus_mg_per_kg
    k = latest.potassium_mg_per_kg
    if n is not None and p is not None and k is not None and (n + p + k) > 0:
        npk_balance = n / (n + p + k)
    else:
        npk_balance = None

    return True, {
        "soil_ph": latest.ph,
        "soil_nitrogen_mg_per_kg": n,
        "soil_phosphorus_mg_per_kg": p,
        "soil_potassium_mg_per_kg": k,
        "soil_organic_carbon_pct": latest.organic_carbon_pct,
        "soil_moisture_pct": latest.moisture_pct,
        "soil_npk_balance_index": npk_balance,
    }


def _ndvi_features(
    readings: list[NDVIReading], as_of: date
) -> tuple[bool, float | None, float | None, str | None]:
    in_range = sorted(
        (r for r in readings if r.observed_at.date() <= as_of),
        key=lambda r: r.observed_at,
    )
    if not in_range:
        return False, None, None, None

    latest = in_range[-1]
    trend = None
    if len(in_range) >= 2:
        previous = in_range[-2]
        trend = latest.ndvi - previous.ndvi

    return True, latest.ndvi, trend, latest.source


def _season_for(sown_on: date | None) -> str | None:
    if sown_on is None:
        return None
    month = sown_on.month
    if month in _KHARIF_MONTHS:
        return "kharif"
    if month in _RABI_MONTHS:
        return "rabi"
    if month in _ZAID_MONTHS:
        return "zaid"
    return None


def _days_since_sowing(sown_on: date | None, as_of: date) -> int | None:
    if sown_on is None:
        return None
    delta = (as_of - sown_on).days
    if delta < 0:
        return None
    return delta
