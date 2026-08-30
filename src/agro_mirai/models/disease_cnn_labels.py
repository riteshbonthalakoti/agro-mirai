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
