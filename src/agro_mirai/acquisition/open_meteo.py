"""Weather adapter — Open-Meteo (no API key required).

Maps Open-Meteo responses to ``WeatherReading`` records
(``specs/core/schema.yaml``). Two entry points:

* :meth:`WeatherAdapter.fetch` — current conditions plus a short-range
  daily forecast (the ``/v1/forecast`` endpoint).
* :meth:`WeatherAdapter.fetch_historical` — a date range from the
  archive/reanalysis endpoint (``/v1/archive``).

Units: Open-Meteo's defaults are already metric and match
``docs/conventions.md`` §5 — °C, mm, % — **except wind**, whose default
is km/h. We pass ``wind_speed_unit=ms`` explicitly so ``wind_mps`` needs
no conversion. There is deliberately no arithmetic unit conversion
anywhere in this file; the only "conversion" is that request parameter.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .base import (
    Adapter,
    FieldInput,
    SourceResponseError,
    SourceUnavailableError,
    iso_from_date,
    iso_from_minute,
    new_id,
)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Daily variables requested from both endpoints. Kept identical so one
# mapper handles daily rows from forecast and archive alike.
_DAILY_VARS = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "precipitation_sum",
    "wind_speed_10m_max",
]
_CURRENT_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_FORECAST_DAYS = 7


class WeatherAdapter(Adapter):
    """Open-Meteo → ``WeatherReading``."""

    source = "open_meteo"

    def __init__(
        self,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
        past_days: int = 0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.forecast_days = forecast_days
        # >0 also returns that many days of recent observed weather in the same call
        self.past_days = past_days
        self._session = session or requests.Session()

    # -- public API --------------------------------------------------------
    def fetch(self, field: FieldInput) -> list[dict[str, Any]]:
        """Current conditions + short-range daily forecast."""
        params = {
            "latitude": field.latitude,
            "longitude": field.longitude,
            "current": ",".join(_CURRENT_VARS),
            "daily": ",".join(_DAILY_VARS),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
            "forecast_days": self.forecast_days,
        }
        if self.past_days:
            params["past_days"] = self.past_days
        payload = self._get_with_retry(FORECAST_URL, params)
        return self._map_forecast(payload, field)

    def fetch_historical(
        self, field: FieldInput, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Historical daily observations over ``[start_date, end_date]``.

        Dates are ISO ``YYYY-MM-DD``. Returns one ``WeatherReading`` per
        day, all with ``is_forecast=False``.
        """
        params = {
            "latitude": field.latitude,
            "longitude": field.longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join(_DAILY_VARS),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
        }
        payload = self._get_with_retry(ARCHIVE_URL, params)
        return self._map_archive(payload, field)

    # -- mapping (pure; unit-tested against recorded payloads) -------------
    def _map_forecast(
        self, payload: dict[str, Any], field: FieldInput
    ) -> list[dict[str, Any]]:
        readings: list[dict[str, Any]] = []
        daily = payload.get("daily") or {}
        daily_dates: list[str] = daily.get("time") or []

        # index of today inside the daily arrays (0 unless past_days was asked for)
        today_idx = 0
        current = payload.get("current")
        if self.past_days and current and daily_dates:
            today_str = str(current["time"])[:10]
            today_idx = daily_dates.index(today_str) if today_str in daily_dates else self.past_days

        # Recent past days -> observed daily rows
        if today_idx:
            readings.extend(
                self._daily_rows(daily, daily_dates[:today_idx], field, is_forecast=False, start=0)
            )

        # Current conditions -> one observed (is_forecast=False) reading,
        # enriched with today's daily min/max when the dates line up.
        if current:
            reading = {
                "id": new_id(),
                "observed_at": iso_from_minute(current["time"]),
                "source": self.source,
                "temp_c": _num(current.get("temperature_2m")),
                "is_forecast": False,
            }
            self._maybe(reading, "humidity_pct", current.get("relative_humidity_2m"))
            self._maybe(reading, "rainfall_mm", current.get("precipitation"))
            self._maybe(reading, "wind_mps", current.get("wind_speed_10m"))
            if daily_dates:
                self._maybe(reading, "temp_min_c", _at(daily, "temperature_2m_min", today_idx))
                self._maybe(reading, "temp_max_c", _at(daily, "temperature_2m_max", today_idx))
            if field.field_id:
                reading["field_id"] = field.field_id
            readings.append(reading)

        # Today's daily row (day total incl. the forecast rest of the day) only
        # when history was asked for; otherwise index today_idx is the "current"
        # reading above and forecast rows start the day after.
        start = today_idx + (1 if current and not self.past_days else 0)
        readings.extend(
            self._daily_rows(daily, daily_dates, field, is_forecast=True, start=start)
        )
        if not readings:
            raise SourceResponseError("Open-Meteo forecast payload had no usable data")
        return readings

    def _map_archive(
        self, payload: dict[str, Any], field: FieldInput
    ) -> list[dict[str, Any]]:
        daily = payload.get("daily") or {}
        daily_dates: list[str] = daily.get("time") or []
        rows = self._daily_rows(daily, daily_dates, field, is_forecast=False, start=0)
        if not rows:
            raise SourceResponseError("Open-Meteo archive payload had no daily data")
        return rows

    def _daily_rows(
        self,
        daily: dict[str, Any],
        daily_dates: list[str],
        field: FieldInput,
        *,
        is_forecast: bool,
        start: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for i in range(start, len(daily_dates)):
            mean = _at(daily, "temperature_2m_mean", i)
            if mean is None:
                # temp_c is required; skip a day with no mean temperature.
                continue
            row: dict[str, Any] = {
                "id": new_id(),
                "observed_at": iso_from_date(daily_dates[i]),
                "source": self.source,
                "temp_c": _num(mean),
                "is_forecast": is_forecast,
            }
            self._maybe(row, "temp_min_c", _at(daily, "temperature_2m_min", i))
            self._maybe(row, "temp_max_c", _at(daily, "temperature_2m_max", i))
            self._maybe(row, "humidity_pct", _at(daily, "relative_humidity_2m_mean", i))
            self._maybe(row, "rainfall_mm", _at(daily, "precipitation_sum", i))
            self._maybe(row, "wind_mps", _at(daily, "wind_speed_10m_max", i))
            if field.field_id:
                row["field_id"] = field.field_id
            rows.append(row)
        return rows

    @staticmethod
    def _maybe(record: dict[str, Any], key: str, value: Any) -> None:
        """Set an optional field only when the source provided a number."""
        if value is not None:
            record[key] = _num(value)

    # -- transport ---------------------------------------------------------
    def _get_with_retry(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET with one retry on a transient failure, then a typed raise."""
        last_exc: Exception | None = None
        for attempt in range(2):  # initial try + one retry
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout_s)
                if resp.status_code >= 500:
                    raise SourceUnavailableError(
                        f"Open-Meteo returned {resp.status_code}"
                    )
                if resp.status_code >= 400:
                    # Client error (e.g. bad params) — not transient; don't retry.
                    raise SourceResponseError(
                        f"Open-Meteo returned {resp.status_code}: {resp.text[:200]}"
                    )
                return resp.json()
            except SourceResponseError:
                raise
            except (requests.RequestException, SourceUnavailableError) as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(0.5)
                    continue
        raise SourceUnavailableError(
            f"Open-Meteo unreachable after retry: {last_exc}"
        ) from last_exc


def _num(value: Any) -> float:
    """Coerce an int/float source value to float; reject anything else."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceResponseError(f"expected a number, got {value!r}")
    return float(value)


def _at(daily: dict[str, Any], key: str, idx: int) -> Any:
    arr = daily.get(key)
    if not isinstance(arr, list) or idx >= len(arr):
        return None
    return arr[idx]


_annual_rain_cache: dict[tuple[float, float], float | None] = {}


def annual_rainfall_mm(latitude: float, longitude: float, timeout_s: float = 6.0) -> float | None:
    """Rain over the last ~12 months at this spot (Open-Meteo archive, one call).

    Cached per ~10 km cell for the life of the process. None on any failure,
    callers just skip the rainfall check then. The archive lags ~2 days, so
    the window ends 3 days ago and the sum is scaled to a full year.
    """
    from datetime import date, timedelta

    key = (round(latitude, 1), round(longitude, 1))
    if key in _annual_rain_cache:
        return _annual_rain_cache[key]
    # NASA POWER first: ~1.5 s and no rate limit trouble; Open-Meteo archive is
    # the backup (7 s+ cold, and 429s on shared IPs)
    from agro_mirai.acquisition.weather_fallbacks import nasa_power_annual_rain

    total = nasa_power_annual_rain(latitude, longitude, timeout_s=max(timeout_s, 8.0))
    if total is None:
        end = date.today() - timedelta(days=3)
        start = end - timedelta(days=364)
        try:
            resp = requests.get(
                ARCHIVE_URL,
                params={
                    "latitude": latitude, "longitude": longitude,
                    "start_date": start.isoformat(), "end_date": end.isoformat(),
                    "daily": "precipitation_sum", "timezone": "UTC",
                },
                timeout=timeout_s,
            )
            resp.raise_for_status()
            vals = [v for v in (resp.json().get("daily") or {}).get("precipitation_sum", []) if v is not None]
            total = sum(vals) * 365.0 / len(vals) if len(vals) >= 300 else None
        except Exception as exc:  # noqa: BLE001 - optional signal
            logging.getLogger(__name__).warning("Open-Meteo annual rain failed: %s: %s", type(exc).__name__, exc)
            total = None
    if total is not None:  # don't cache failures
        _annual_rain_cache[key] = total
    return total
