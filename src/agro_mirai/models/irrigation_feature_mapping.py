"""Maps a Module 05 ``FeatureVector`` to the irrigation model's input row.

Implements exactly the mapping documented in
``decisions/0008-irrigation-model-feature-mapping.md`` — read that ADR
before changing any of the column choices here. Column order matches
``tools/train_irrigation_model.py``'s ``build_model_matrix`` output
exactly; the two must stay in sync.
"""
from __future__ import annotations

from agro_mirai.processing.feature_builder import FeatureVector

MODEL_FEATURE_COLUMNS: tuple[str, ...] = (
    "Soil_pH",
    "Soil_Moisture",
    "Temperature_C",
    "Humidity",
    "Rainfall_mm",
    "season_Kharif",
    "season_Rabi",
    "season_Zaid",
)

_SEASON_TO_COLUMN = {
    "kharif": "season_Kharif",
    "rabi": "season_Rabi",
    "zaid": "season_Zaid",
}


def map_features(vector: FeatureVector) -> dict[str, float]:
    """Maps ``vector`` to a ``{column: value}`` row for the irrigation model.

    Raises ``ValueError`` if soil data is unavailable (no
    ``soil_ph``/``soil_moisture_pct`` to map), if the 14d temperature/
    humidity means are both missing, or if ``season`` is not one of
    ``kharif``/``rabi``/``zaid``.
    """
    if not vector.soil_data_available:
        raise ValueError(
            "irrigation feature mapping requires soil_data_available=True "
            "(no soil_ph/soil_moisture_pct to map from a field with zero "
            "soil samples)"
        )
    missing_soil = [
        name
        for name, value in (
            ("soil_ph", vector.soil_ph),
            ("soil_moisture_pct", vector.soil_moisture_pct),
        )
        if value is None
    ]
    if missing_soil:
        raise ValueError(
            f"irrigation feature mapping requires {missing_soil} to be "
            "non-None on the FeatureVector"
        )
    if vector.temp_c_mean_14d is None or vector.humidity_pct_mean_14d is None:
        raise ValueError(
            "irrigation feature mapping requires temp_c_mean_14d and "
            "humidity_pct_mean_14d to be non-None"
        )
    if vector.season not in _SEASON_TO_COLUMN:
        raise ValueError(
            f"irrigation feature mapping requires season to be one of "
            f"{sorted(_SEASON_TO_COLUMN)}, got {vector.season!r}"
        )

    row = {column: 0.0 for column in MODEL_FEATURE_COLUMNS}
    row["Soil_pH"] = vector.soil_ph
    row["Soil_Moisture"] = vector.soil_moisture_pct
    row["Temperature_C"] = vector.temp_c_mean_14d
    row["Humidity"] = vector.humidity_pct_mean_14d
    row["Rainfall_mm"] = vector.rainfall_mm_sum_30d
    row[_SEASON_TO_COLUMN[vector.season]] = 1.0
    return row
