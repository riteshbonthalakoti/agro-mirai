"""Vision-LLM tier added to resolve_disease_alert (AI cascade restructure):
mocked at agro_mirai.api.gemini_client.ask_gemini_vision -- no live Gemini
key or quota used. CNN/environmental tiers below it are unchanged and
already covered by tests/api/test_disease_image_route.py."""
import json
from unittest.mock import MagicMock

from agro_mirai.models.image_or_environmental_disease import resolve_disease_alert
from agro_mirai.persistence.models import DiseaseRiskAlert
from agro_mirai.processing.feature_builder import FeatureVector


def _rule_based_alert():
    from datetime import datetime, timezone
    return DiseaseRiskAlert(
        id="rb1", field_id="f1", created_at=datetime.now(timezone.utc),
        disease="none", risk_level="low", confidence=0.1,
    )


def _features():
    return FeatureVector(
        field_id="f1", as_of=None,
        rainfall_mm_sum_7d=0, temp_c_mean_7d=25, humidity_pct_mean_7d=60,
        rainfall_mm_sum_14d=0, temp_c_mean_14d=25, humidity_pct_mean_14d=60,
        rainfall_mm_sum_30d=0, temp_c_mean_30d=25, humidity_pct_mean_30d=60,
        soil_data_available=False,
    )


def test_vision_llm_success_short_circuits_cnn(monkeypatch):
    reply = json.dumps({
        "crop": "cotton", "disease": "leaf curl", "risk_level": "high",
        "confidence": 0.8, "recommended_action": "apply fungicide",
    })
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_vision", lambda *a, **k: reply
    )
    disease_model = MagicMock()
    cnn_caller = MagicMock(return_value=None)

    alert = resolve_disease_alert(disease_model, _features(), "f1", image_bytes=b"img", cnn_caller=cnn_caller)

    assert alert.source == "vision_llm"
    assert alert.disease == "leaf curl"
    assert alert.risk_level == "high"
    cnn_caller.assert_not_called()
    disease_model.predict.assert_not_called()


def test_vision_llm_none_falls_through_to_cnn(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_vision", lambda *a, **k: None
    )
    disease_model = MagicMock()
    cnn_caller = MagicMock(return_value={
        "id": "x", "field_id": "f1", "created_at": "2026-01-01T00:00:00Z",
        "disease": "rust", "risk_level": "moderate", "confidence": 0.5,
    })

    alert = resolve_disease_alert(disease_model, _features(), "f1", image_bytes=b"img", cnn_caller=cnn_caller)

    assert alert.source == "cnn"
    cnn_caller.assert_called_once()


def test_vision_llm_malformed_json_falls_through_to_cnn(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_vision", lambda *a, **k: "not json"
    )
    disease_model = MagicMock()
    cnn_caller = MagicMock(return_value=None)
    disease_model.predict.return_value = _rule_based_alert()

    resolve_disease_alert(disease_model, _features(), "f1", image_bytes=b"img", cnn_caller=cnn_caller)

    cnn_caller.assert_called_once()  # fell through past the broken vision reply


def test_vision_llm_exception_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network on fire")

    monkeypatch.setattr("agro_mirai.api.gemini_client.ask_gemini_vision", boom)
    disease_model = MagicMock()
    cnn_caller = MagicMock(return_value=None)
    disease_model.predict.return_value = _rule_based_alert()

    # must not raise
    resolve_disease_alert(disease_model, _features(), "f1", image_bytes=b"img", cnn_caller=cnn_caller)
    cnn_caller.assert_called_once()


def test_no_image_skips_vision_tier_entirely(monkeypatch):
    called = []
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_vision",
        lambda *a, **k: called.append(1),
    )
    disease_model = MagicMock()
    disease_model.predict.return_value = _rule_based_alert()

    resolve_disease_alert(disease_model, _features(), "f1", image_bytes=None)

    assert called == []  # vision tier only runs when an image was given
