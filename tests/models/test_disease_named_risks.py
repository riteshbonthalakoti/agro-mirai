from datetime import date, timedelta

from agro_mirai.models.disease_cnn_labels import (
    is_unsure,
    photo_coverage_note,
    unsure_texts,
)
from agro_mirai.models.disease_named_risks import RISKS, score_named
from agro_mirai.models.disease_risk_model import DiseaseRiskModel
from agro_mirai.models.disease_risk_scoring import score_disease_risk
from agro_mirai.processing.feature_builder import FeatureVector

AS_OF = date(2026, 9, 24)


def _vec(crop, rain, rh, temp=26.0, fc3=0.0, fc7=0.0, days=14):
    daily = []
    for i in range(-days + 1, 8):
        d = AS_OF + timedelta(days=i)
        daily.append(dict(date=d.isoformat(), tmean=temp, tmin=temp - 4, tmax=temp + 5, rh=rh, wind=4.0,
                          rain=rain if i <= 0 else fc7 / 7, forecast=i > 0))
    return FeatureVector(
        field_id="f1", as_of=AS_OF,
        rainfall_mm_sum_7d=rain * 7, temp_c_mean_7d=temp, humidity_pct_mean_7d=rh,
        rainfall_mm_sum_14d=rain * 14, temp_c_mean_14d=temp, humidity_pct_mean_14d=rh,
        rainfall_mm_sum_30d=rain * 30, temp_c_mean_30d=temp, humidity_pct_mean_30d=rh,
        soil_data_available=False, crop_type=crop, daily_weather=daily,
        rain_forecast_mm_3d=fc3, rain_forecast_mm_7d=fc7,
    )


def test_every_listed_crop_is_one_of_the_22():
    from agro_mirai.models.ecocrop import table

    assert set(RISKS) <= set(table())


def test_wet_humid_rice_week_names_rice_blast_and_scores_high():
    r = score_disease_risk(_vec("rice", rain=8.0, rh=90, fc3=15.0, fc7=40.0))
    assert "Rice blast" in r.disease and "not a diagnosis" in r.disease
    assert r.risk_level in ("high", "severe")
    assert "Check the leaves" in r.recommended_action


def test_dry_week_is_low_even_for_a_listed_crop():
    r = score_disease_risk(_vec("rice", rain=0.0, rh=40))
    assert r.risk_level == "low"
    assert "Check the leaves" not in r.recommended_action  # low risk: no scouting checklist


def test_unlisted_or_missing_crop_keeps_the_generic_label():
    for crop in (None, "lentil"):
        r = score_disease_risk(_vec(crop, rain=8.0, rh=90))
        assert r.disease.startswith("Generic fungal disease risk")
        assert r.named is None


def test_forecast_rain_raises_the_score_and_marks_trend_rising():
    calm = score_named(_vec("grapes", rain=0.5, rh=82, temp=22.0))
    wet_ahead = score_named(_vec("grapes", rain=0.5, rh=82, temp=22.0, fc3=25.0, fc7=60.0))
    assert wet_ahead.score > calm.score
    assert wet_ahead.trend == "rising"


def test_cold_or_hot_outside_the_disease_band_lowers_risk():
    inside = score_named(_vec("rice", rain=6.0, rh=90, temp=26.0)).score
    outside = score_named(_vec("rice", rain=6.0, rh=90, temp=40.0)).score
    assert outside < inside


def test_works_without_the_daily_series_using_weekly_numbers():
    v = _vec("rice", rain=6.0, rh=90)
    v.daily_weather = None
    assert score_named(v).days_counted == 0
    assert score_disease_risk(v).risk_level in ("low", "moderate", "high", "severe")


def test_details_for_crop_specific_and_generic():
    m = DiseaseRiskModel()
    d = m.details_for(_vec("maize", rain=6.0, rh=88))
    assert d["crop_specific"] is True and d["named_disease"] == "Northern leaf blight"
    assert set(d) >= {"trend", "humid_days_last_7", "wet_days_last_7", "favourable_temp_c"}
    g = m.details_for(_vec(None, rain=6.0, rh=88))
    assert g["crop_specific"] is False and g["named_disease"] is None


def test_low_photo_confidence_is_reported_as_not_sure_with_alternatives():
    assert is_unsure(0.4) and not is_unsure(0.8)
    label, action = unsure_texts(
        "Corn_(maize)___Northern_Leaf_Blight",
        [("Corn_(maize)___Northern_Leaf_Blight", 0.41), ("Corn_(maize)___Common_rust_", 0.3)],
    )
    assert label.startswith("Not sure") and "Northern Leaf Blight" in label
    assert "Common rust (30%)" in action and "Retake" in action


def test_photo_coverage_notes():
    assert "not trained on cotton" in photo_coverage_note("cotton", "Tomato: Early blight")
    assert "tomato leaf" in photo_coverage_note("maize", "Tomato: Early blight")
    assert photo_coverage_note("maize", "Corn (maize): Common rust") == ""
    assert photo_coverage_note(None, "Tomato: Early blight") == ""


def test_class_indices_for_crop():
    from agro_mirai.models.disease_cnn_labels import class_indices_for_crop

    names = ["Apple___healthy", "Corn_(maize)___Common_rust_", "Tomato___Late_blight", "Corn_(maize)___healthy"]
    assert class_indices_for_crop(names, "maize") == [1, 3]
    assert class_indices_for_crop(names, "cotton") == []
    assert class_indices_for_crop(names, None) == []
