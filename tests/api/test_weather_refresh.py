from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from agro_mirai.api import field_data_acquisition as fda
from agro_mirai.persistence.models import WeatherReading

TODAY = date(2026, 9, 24)


def _row(d):
    return WeatherReading(
        id=str(d), field_id="f1", observed_at=datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
        source="open_meteo", temp_c=27.0, is_forecast=False,
    )


def _field():
    f = MagicMock()
    f.id, f.latitude, f.longitude = "f1", 15.1, 76.9
    return f


def setup_function(_):
    fda._last_refresh.clear()


def test_fresh_and_full_history_is_left_alone():
    rows = [_row(TODAY - timedelta(days=i)) for i in range(10)]
    with patch.object(fda, "fetch_and_save_weather") as fetch:
        assert fda.ensure_fresh_weather(MagicMock(), "u", _field(), TODAY, rows) is False
    fetch.assert_not_called()


def test_no_row_for_today_triggers_a_refresh_once():
    rows = [_row(TODAY - timedelta(days=i)) for i in range(1, 12)]
    with patch.object(fda, "fetch_and_save_weather", return_value=True) as fetch:
        assert fda.ensure_fresh_weather(MagicMock(), "u", _field(), TODAY, rows) is True
        # second call within the gap must not hit the API again
        assert fda.ensure_fresh_weather(MagicMock(), "u", _field(), TODAY, rows) is False
    assert fetch.call_count == 1


def test_thin_history_triggers_a_refresh():
    rows = [_row(TODAY)]  # only today (how old fields were saved)
    with patch.object(fda, "fetch_and_save_weather", return_value=True) as fetch:
        assert fda.ensure_fresh_weather(MagicMock(), "u", _field(), TODAY, rows) is True
    fetch.assert_called_once()


def test_refresh_replaces_old_forecast_rows_instead_of_piling_up(monkeypatch):
    from unittest.mock import MagicMock

    store = MagicMock()
    fresh = [
        {"id": "f1", "field_id": "f1", "observed_at": "2026-09-25T00:00:00Z", "source": "open_meteo",
         "temp_c": 27.0, "is_forecast": True},
        {"id": "f2", "field_id": "f1", "observed_at": "2026-09-26T00:00:00Z", "source": "open_meteo",
         "temp_c": 28.0, "is_forecast": True},
    ]
    monkeypatch.setattr(fda, "WeatherAdapter", lambda **kw: MagicMock(fetch=lambda fi: fresh))
    from agro_mirai.acquisition.base import FieldInput

    assert fda.fetch_and_save_weather(store, "u", FieldInput(latitude=15.1, longitude=76.9, field_id="f1")) is True
    store.delete_weather_forecasts.assert_called_once_with("u", "f1", "2026-09-25")
