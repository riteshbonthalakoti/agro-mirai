from datetime import date, timedelta

from agro_mirai.models.evapotranspiration import penman_monteith_et0
from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel, _decide
from agro_mirai.models.soil_water_balance import effective_rain, run_balance
from agro_mirai.processing.feature_builder import FeatureVector

AS_OF = date(2026, 9, 24)


def _days(n_past=30, n_future=7, rain=0.0, future_rain=0.0, tmean=28.0):
    out = []
    for i in range(-n_past + 1, n_future + 1):
        d = AS_OF + timedelta(days=i)
        out.append(dict(
            date=d.isoformat(), tmean=tmean, tmin=tmean - 4, tmax=tmean + 5,
            rh=60.0, wind=5.0, rain=(rain if i <= 0 else future_rain), forecast=i > 0,
        ))
    return out


def _balance(daily, **kw):
    args = dict(as_of=AS_OF, crop="cotton", days_since_sowing=50, soil_type="black", latitude=15.0)
    args.update(kw)
    return run_balance(daily, **args)


def test_pm_et0_is_sensible_for_tropical_day():
    et0 = penman_monteith_et0(
        temp_mean_c=27, temp_min_c=24, temp_max_c=32, rh_mean_pct=69,
        wind10_max_ms=6.6, latitude_deg=15, day_of_year=270,
    )
    assert 3.5 < et0 < 6.5


def test_small_showers_do_not_count():
    assert effective_rain(1.5) == 0.0
    assert 8.0 < effective_rain(10.0) < 10.0


def test_too_little_weather_gives_no_balance():
    assert _balance(_days(n_past=3)) is None


def test_dry_month_uses_up_soil_water():
    b = _balance(_days(rain=0.0))
    assert b.depletion_share >= 0.9
    assert b.stress_in_days == 1
    assert _decide(b)[0] == "high"


def test_rainy_month_keeps_soil_wet():
    b = _balance(_days(rain=12.0))
    assert b.depletion_share < 0.3
    assert _decide(b)[0] == "low"


def test_sandy_soil_dries_faster_than_clay():
    dry = _days(rain=3.0)
    assert _balance(dry, soil_type="desert").depletion_share > _balance(dry, soil_type="black").depletion_share


def test_forecast_rain_makes_farmer_wait_and_cuts_the_amount():
    daily = _days(rain=4.0)
    without = _decide(_balance(daily))
    for d in daily:
        if d["forecast"] and d["date"] <= (AS_OF + timedelta(days=2)).isoformat():
            d["rain"] = 25.0
    urgency, depth, waiting, _ = _decide(_balance(daily))
    assert waiting is True
    assert without[2] is False
    assert depth < without[1]


def test_stress_day_is_found_in_forecast():
    b = _balance(_days(rain=6.0, future_rain=0.0))
    if b.depletion_share < 1.0:
        assert b.stress_in_days is None or 1 <= b.stress_in_days <= 7


def _fv(daily):
    return FeatureVector(
        field_id="f1", as_of=AS_OF,
        rainfall_mm_sum_7d=5.0, temp_c_mean_7d=28.0, humidity_pct_mean_7d=60.0,
        rainfall_mm_sum_14d=10.0, temp_c_mean_14d=28.0, humidity_pct_mean_14d=60.0,
        rainfall_mm_sum_30d=30.0, temp_c_mean_30d=28.0, humidity_pct_mean_30d=60.0,
        soil_data_available=False, latitude=15.0, crop_type="cotton", days_since_sowing=50,
        soil_type="black", daily_weather=daily,
    )


def test_model_uses_daily_path_and_writes_plain_rationale():
    advice = IrrigationPredictionModel().predict(_fv(_days(rain=0.0)))
    assert advice.urgency == "high"
    assert "soil water" in advice.rationale
    assert 2.0 <= advice.recommended_depth_mm <= 60.0
    assert advice.window_end_at > advice.window_start_at


def test_model_falls_back_without_daily_weather():
    advice = IrrigationPredictionModel().predict(_fv(None))
    assert advice.urgency in ("low", "moderate", "high")
    assert "Water balance" in advice.rationale


def test_lagging_weather_source_gets_gap_filled():
    daily = [d for d in _days(rain=4.0, n_future=0) if d["date"] <= (AS_OF - timedelta(days=3)).isoformat()]
    b = _balance(daily)
    assert b is not None and b.gap_days_estimated == 3
    assert "estimated" in _rationale(b)


def test_stale_weather_is_refused():
    daily = [d for d in _days(rain=4.0, n_future=0) if d["date"] <= (AS_OF - timedelta(days=9)).isoformat()]
    assert _balance(daily) is None


def _rationale(b):
    from agro_mirai.models.irrigation_prediction_model import _rationale_from_balance

    u, dep, w, _ = _decide(b)
    return _rationale_from_balance(b, u, dep, w)
