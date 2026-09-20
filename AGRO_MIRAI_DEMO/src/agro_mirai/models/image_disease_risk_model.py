"""``ImageDiseaseRiskModel`` — MobileNetV2 image classifier over a leaf photo.

Module 20's CNN upgrade path from ADR 0009: a second, independent
``predict`` entry point alongside ``DiseaseRiskModel`` — same
``DiseaseRiskAlert`` output shape, different input (an image instead of a
``FeatureVector``). Neither model changes the other; a caller picks
whichever is available for a given field (Module 09's `ExplanationService`/
`DecisionEngine` still only calls the environmental `DiseaseRiskModel` —
wiring this into that call path is a follow-up, not part of this module).

torch/torchvision are NOT in the main ``requirements.txt`` (same
deliberate exclusion as the Module 12 voice/AI4Bharat stack — see
``decisions/0014-deploy-target-and-voice-scope.md``); they live in the
project-local ``.venv/``. Importing torch happens lazily inside
``__init__`` so importing this module doesn't require torch to be
installed — only instantiating the model does.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agro_mirai.models.disease_cnn_labels import (
    disease_display_name,
    risk_level_for,
)
from agro_mirai.models.disease_risk_scoring import RISK_ACTION, RISK_WINDOW_DAYS
from agro_mirai.persistence.models import DiseaseRiskAlert

_MODELS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"
DEFAULT_WEIGHTS_PATH = _MODELS_DIR / "disease_cnn_mobilenetv2.pt"
DEFAULT_CLASS_NAMES_PATH = _MODELS_DIR / "disease_cnn_class_names.json"

_IMG_SIZE = 224
_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]


class ImageDiseaseRiskModel:
    def __init__(
        self,
        weights_path: Path = DEFAULT_WEIGHTS_PATH,
        class_names_path: Path = DEFAULT_CLASS_NAMES_PATH,
    ):
        if not weights_path.exists():
            raise FileNotFoundError(
                f"{weights_path} not found. Train it on Colab first — see "
                "decisions/0018-disease-cnn.md and tools/train_disease_cnn.py — "
                "then drop disease_cnn_mobilenetv2.pt and "
                "disease_cnn_class_names.json into models/."
            )
        if not class_names_path.exists():
            raise FileNotFoundError(f"{class_names_path} not found alongside {weights_path}.")

        import torch
        from torchvision import models as tv_models

        with open(class_names_path) as f:
            self._class_names: list[str] = json.load(f)

        model = tv_models.mobilenet_v2(weights=None)
        model.classifier[1] = torch.nn.Linear(model.last_channel, len(self._class_names))
        state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)
        model.eval()

        self._torch = torch
        self._model = model

    def predict(self, image_path: str | Path, field_id: str) -> DiseaseRiskAlert:
        """Classifies a leaf photo at ``image_path`` for ``field_id``."""
        return self.predict_detailed(image_path, field_id)[0]

    def predict_detailed(self, image_path, field_id: str):
        """Same as ``predict`` (path or file-like object), but also returns the
        model's top-3 classes with probabilities, so a demo can show the network
        really looked at the image."""
        from PIL import Image
        from torchvision import transforms

        transform = transforms.Compose(
            [
                transforms.Resize((_IMG_SIZE, _IMG_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
            ]
        )
        image = Image.open(image_path).convert("RGB")
        tensor = transform(image).unsqueeze(0)

        torch = self._torch
        with torch.no_grad():
            logits = self._model(tensor)
            probs = torch.softmax(logits, dim=1)[0]
            top_idx = int(torch.argmax(probs).item())
            confidence = float(probs[top_idx].item())
            top_p, top_i = torch.topk(probs, 3)
        top3 = [
            {"class": self._class_names[int(i)], "probability": round(float(p), 4)}
            for p, i in zip(top_p, top_i)
        ]

        raw_class = self._class_names[top_idx]
        risk_level = risk_level_for(raw_class, confidence)
        created_at = datetime.now(timezone.utc)

        alert = DiseaseRiskAlert(
            id=str(uuid.uuid4()),
            field_id=field_id,
            created_at=created_at,
            disease=disease_display_name(raw_class),
            risk_level=risk_level,
            confidence=confidence,
            window_start_at=created_at,
            window_end_at=created_at + timedelta(days=RISK_WINDOW_DAYS[risk_level]),
            recommended_action=RISK_ACTION[risk_level],
        )
        return alert, top3
