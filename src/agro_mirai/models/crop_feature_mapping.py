"""Maps a Module 05 ``FeatureVector`` to the crop model's input row.

Implements exactly the mapping documented in
``decisions/0007-crop-model-feature-mapping.md`` — read that ADR before
changing any of the column choices here. Column order matches
``tools/train_crop_model.py``'s ``FEATURE_COLUMNS`` exactly; the two
must stay in sync.
"""
from __future__ import annotations

from agro_mirai.processing.feature_builder import FeatureVector

MODEL_FEATURE_COLUMNS: tuple[str, ...] = (
    "N",
    "P",
    "K",
    "temperature",
    "humidity",
    "ph",
    "rainfall",
)


def map_features(vector: FeatureVector) -> dict[str, float]:
    """Maps ``vector`` to a ``{column: value}`` row for the crop model.

    Raises ``ValueError`` if soil data is unavailable (no N/P/K/ph to
    map) or if both weather signals the model needs (14d temp/humidity
    means, 30d rainfall sum) are missing.
    """
    if not vector.soil_data_available:
        raise ValueError(
            "crop feature mapping requires soil_data_available=True "
            "(no N/P/K/ph to map from a field with zero soil samples)"
        )
    missing_soil = [
        name
        for name, value in (
            ("soil_nitrogen_mg_per_kg", vector.soil_nitrogen_mg_per_kg),
            ("soil_phosphorus_mg_per_kg", vector.soil_phosphorus_mg_per_kg),
            ("soil_potassium_mg_per_kg", vector.soil_potassium_mg_per_kg),
            ("soil_ph", vector.soil_ph),
        )
        if value is None
    ]
    if missing_soil:
        raise ValueError(
            f"crop feature mapping requires {missing_soil} to be non-None "
            "on the FeatureVector"
        )
    if vector.temp_c_mean_14d is None or vector.humidity_pct_mean_14d is None:
        raise ValueError(
            "crop feature mapping requires temp_c_mean_14d and "
            "humidity_pct_mean_14d to be non-None"
        )

    return {
        "N": vector.soil_nitrogen_mg_per_kg,
        "P": vector.soil_phosphorus_mg_per_kg,
        "K": vector.soil_potassium_mg_per_kg,
        "temperature": vector.temp_c_mean_14d,
        "humidity": vector.humidity_pct_mean_14d,
        "ph": vector.soil_ph,
        "rainfall": vector.rainfall_mm_sum_30d,
    }
