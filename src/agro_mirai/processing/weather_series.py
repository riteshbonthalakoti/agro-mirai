"""Turns the raw WeatherReading rows a field has collected into one clean
row per calendar day, and splits them into past/today vs forecast.

The store keeps everything ever fetched: an instantaneous "current" reading
(time of day set), daily rows, and forecast rows that were later re-fetched.
Summing all of them double counts rain, so everything downstream (rain
windows, soil water balance) goes through here first.
"""
from __future__ import annotations

from datetime import date

from agro_mirai.persistence.models import WeatherReading


def _is_daily_row(w: WeatherReading) -> bool:
    t = w.observed_at
    return t.hour == 0 and t.minute == 0 and t.second == 0


def one_row_per_day(readings: list[WeatherReading]) -> dict[date, WeatherReading]:
    """Best row for each date. Preference: a daily-aggregate row over an
    instantaneous 'current' one, an observed row over a forecast one, and
    otherwise the one seen last."""
    best: dict[date, tuple[tuple[int, int], WeatherReading]] = {}
    for w in readings:
        day = w.observed_at.date()
        rank = (1 if _is_daily_row(w) else 0, 0 if w.is_forecast else 1)
        cur = best.get(day)
        if cur is None or rank >= cur[0]:
            best[day] = (rank, w)
    return {d: v[1] for d, v in best.items()}


def split_past_and_forecast(
    days: dict[date, WeatherReading], as_of: date
) -> tuple[list[WeatherReading], list[WeatherReading]]:
    past = [days[d] for d in sorted(days) if d <= as_of]
    future = [days[d] for d in sorted(days) if d > as_of]
    return past, future


def daily_dicts(rows: list[WeatherReading]) -> list[dict]:
    """Plain dicts (JSON friendly) for the soil water balance."""
    return [
        {
            "date": w.observed_at.date().isoformat(),
            "tmean": w.temp_c,
            "tmin": w.temp_min_c,
            "tmax": w.temp_max_c,
            "rh": w.humidity_pct,
            "wind": w.wind_mps,
            "rain": w.rainfall_mm,
            "forecast": bool(w.is_forecast),
        }
        for w in rows
    ]
