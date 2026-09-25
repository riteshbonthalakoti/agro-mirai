"""Maps PlantVillage class labels to a human-readable disease name and a
``risk_level``, and flags which of the 22 ``crop_type`` labels the trained
CNN was actually trained to recognize.

See ``decisions/0018-disease-cnn.md`` for the full training/dataset
writeup. The CNN has no ground-truth severity data for each disease, so
``risk_level`` is derived heuristically from the predicted class (healthy
vs. not) and the model's own softmax confidence — documented here rather
than invented silently, same honesty standard as ADR 0009/0016.
"""
from __future__ import annotations

# The 4 of AGRO MIRAI's 22 `crop_type` enum values (specs/core/enums.md)
# that the trained PlantVillage classes actually cover. The other 34
# PlantVillage classes (pepper, potato, tomato, blueberry, cherry, peach,
# raspberry, soybean, squash, strawberry) do not map to any crop_type
# label — a real, documented dataset-coverage gap, not an oversight.
CNN_COVERED_CROP_TYPES = frozenset({"apple", "maize", "grapes", "orange"})

_PLANTVILLAGE_CROP_TO_CROP_TYPE = {
    "Apple": "apple",
    "Corn_(maize)": "maize",
    "Grape": "grapes",
    "Orange": "orange",
}


def parse_class_name(raw_class: str) -> tuple[str, str, bool]:
    """Splits a PlantVillage folder name into ``(crop, disease, is_healthy)``.

    Folder names are ``<Crop>___<Disease>``, e.g.
    ``"Corn_(maize)___Northern_Leaf_Blight"`` or ``"Apple___healthy"``.
    """
    crop, _, disease = raw_class.partition("___")
    disease = disease.replace("_", " ").strip()
    is_healthy = disease.lower() == "healthy"
    return crop, disease, is_healthy


def crop_type_for(raw_class: str) -> str | None:
    """Returns the matching ``crop_type`` enum value, or ``None`` if this
    PlantVillage class's crop isn't in AGRO MIRAI's 22-crop enum."""
    crop, _, _ = parse_class_name(raw_class)
    return _PLANTVILLAGE_CROP_TO_CROP_TYPE.get(crop)


def risk_level_for(raw_class: str, confidence: float) -> str:
    """Heuristic risk level from the predicted class + softmax confidence.

    Healthy predictions are always ``low``. Non-healthy predictions are
    floored at ``moderate`` regardless of confidence — a low-confidence
    disease call still deserves a look, since under-alerting on a real
    disease is worse than an unnecessary scouting trip (same asymmetry
    ADR 0009's threshold table encodes for the rule-based path).
    """
    _, _, is_healthy = parse_class_name(raw_class)
    if is_healthy:
        return "low"
    if confidence >= 0.85:
        return "severe"
    if confidence >= 0.60:
        return "high"
    return "moderate"


def disease_display_name(raw_class: str) -> str:
    crop, disease, is_healthy = parse_class_name(raw_class)
    crop_label = crop.replace("_", " ")
    if is_healthy:
        return f"{crop_label}: no disease detected (healthy foliage)"
    return f"{crop_label}: {disease}"


#: Below this top-1 probability the photo model is guessing; we say so.
UNSURE_BELOW = 0.55

_CROP_LABEL_TO_TYPE = {
    "Corn (maize)": "maize", "Apple": "apple", "Grape": "grapes", "Orange": "orange",
}


def class_indices_for_crop(class_names: list[str], crop_type: str | None) -> list[int]:
    """Indices of the classes that belong to ``crop_type`` (only the 4 crops the model
    knows), or [] when the crop is unknown or not covered. The farmer already told us the
    crop, so the model only has to choose between that crop's diseases."""
    if not crop_type or crop_type not in CNN_COVERED_CROP_TYPES:
        return []
    return [i for i, n in enumerate(class_names) if crop_type_for(n) == crop_type]


def is_unsure(confidence: float) -> bool:
    return confidence < UNSURE_BELOW


def unsure_texts(raw_class: str, alternatives: list[tuple[str, float]]) -> tuple[str, str]:
    """(disease label, action) for a low-confidence photo answer: an honest
    "not sure" with the runners-up, instead of a confident-looking guess."""
    guess = disease_display_name(raw_class)
    others = "; ".join(f"{disease_display_name(c)} ({p * 100:.0f}%)" for c, p in alternatives if c != raw_class)
    action = (
        "The photo is not clear enough to be sure. Retake it close up in daylight, one leaf filling the frame, "
        "and include a leaf that shows the problem."
    )
    if others:
        action += f" Other possibilities: {others}."
    action += " If the plant looks unwell, show it to your local agriculture officer."
    return f"Not sure. Best guess: {guess}", action


def photo_coverage_note(field_crop: str | None, predicted_disease_label: str) -> str:
    """Extra sentence when the photo model may not suit the field's crop."""
    if not field_crop:
        return ""
    if field_crop not in CNN_COVERED_CROP_TYPES:
        return (
            f" Note: the photo model was not trained on {field_crop} leaves, "
            "so treat this result as a rough guide only."
        )
    predicted_crop = predicted_disease_label.split(":", 1)[0].strip()
    predicted_type = _CROP_LABEL_TO_TYPE.get(predicted_crop)
    if predicted_type is None and predicted_crop and not predicted_disease_label.startswith("Not sure"):
        return (
            f" Note: this looks like a {predicted_crop.lower()} leaf but your field grows {field_crop}. "
            "Take the photo from your own plants."
        )
    if predicted_type is not None and predicted_type != field_crop:
        return (
            f" Note: this looks like a {predicted_crop.lower()} leaf but your field grows {field_crop}. "
            "Take the photo from your own plants."
        )
    return ""
