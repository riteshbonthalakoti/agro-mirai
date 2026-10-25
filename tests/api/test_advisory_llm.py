"""Advisory LLM tier: mocked at
agro_mirai.api.gemini_client.ask_gemini_structured -- no live Gemini key
or quota used."""
from agro_mirai.api.advisory_llm import llm_recommend_advisory
from agro_mirai.processing.feature_builder import FeatureVector


def _features():
    return FeatureVector(
        field_id="f1", as_of=None,
        rainfall_mm_sum_7d=0, temp_c_mean_7d=25, humidity_pct_mean_7d=60,
        rainfall_mm_sum_14d=0, temp_c_mean_14d=25, humidity_pct_mean_14d=60,
        rainfall_mm_sum_30d=0, temp_c_mean_30d=25, humidity_pct_mean_30d=60,
        soil_data_available=False,
    )


def test_valid_response_returns_advisory(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured",
        lambda *a, **k: {"title": "Water soon", "body": "Soil is dry, irrigate within 2 days.", "severity": "high"},
    )
    result = llm_recommend_advisory(_features())
    assert result is not None
    assert result.title == "Water soon"
    assert result.severity == "high"
    assert result.source == "llm"


def test_invalid_severity_rejected(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured",
        lambda *a, **k: {"title": "x", "body": "y", "severity": "catastrophic"},
    )
    assert llm_recommend_advisory(_features()) is None


def test_none_reply_returns_none(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured", lambda *a, **k: None
    )
    assert llm_recommend_advisory(_features()) is None


def test_missing_field_returns_none(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured",
        lambda *a, **k: {"title": "x"},
    )
    assert llm_recommend_advisory(_features()) is None


def test_exception_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("agro_mirai.api.gemini_client.ask_gemini_structured", boom)
    assert llm_recommend_advisory(_features()) is None
