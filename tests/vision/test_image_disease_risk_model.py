"""Tests for ImageDiseaseRiskModel (Module 20's CNN disease path).

Requires torch/torchvision/pillow — deliberately NOT in the main venv
(same policy as tests/voice/, see decisions/0014). Run under the
project-local .venv/:
  .venv/Scripts/python.exe -m pytest tests/vision -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agro_mirai.models.image_disease_risk_model import (
    DEFAULT_CLASS_NAMES_PATH,
    DEFAULT_WEIGHTS_PATH,
    ImageDiseaseRiskModel,
)
from agro_mirai.persistence.models import DiseaseRiskAlert

_WEIGHTS_PRESENT = DEFAULT_WEIGHTS_PATH.exists() and DEFAULT_CLASS_NAMES_PATH.exists()


def test_missing_weights_raises_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ImageDiseaseRiskModel(
            weights_path=tmp_path / "does_not_exist.pt",
            class_names_path=tmp_path / "does_not_exist.json",
        )


@pytest.mark.skipif(
    not _WEIGHTS_PRESENT,
    reason="trained artifact not present — train via tools/train_disease_cnn.py on Colab first",
)
def test_predict_returns_schema_valid_alert(tmp_path: Path):
    from PIL import Image

    image_path = tmp_path / "leaf.jpg"
    Image.new("RGB", (224, 224), color=(60, 120, 40)).save(image_path)

    model = ImageDiseaseRiskModel()
    alert = model.predict(image_path, field_id="ff000001-0000-4000-8000-000000000001")

    assert isinstance(alert, DiseaseRiskAlert)
    assert alert.field_id == "ff000001-0000-4000-8000-000000000001"
    assert alert.risk_level in {"low", "moderate", "high", "severe"}
    assert 0.0 <= alert.confidence <= 1.0
    assert alert.recommended_action
    assert alert.window_start_at is not None
    assert alert.window_end_at is not None
    assert alert.window_end_at > alert.window_start_at
