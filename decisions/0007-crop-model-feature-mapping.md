# ADR 0007 — Crop model feature mapping (FeatureVector → Kaggle model inputs)

**Status:** accepted
**Date:** 2026-08-26
**Module:** 06 — Crop Recommendation Model

## Context

The Kaggle crop-recommendation dataset (`atharvaingle/crop-recommendation-dataset`,
Apache-2.0) has 2200 rows, 22 balanced crop labels (100 each), and seven
feature columns: `N`, `P`, `K` (soil NPK, mg/kg-equivalent), `temperature`
(°C), `humidity` (%), `ph`, `rainfall` (mm). All 22 labels are already
present in `specs/core/enums.md`'s `crop_type` (that enum was sourced
from this exact dataset — see the enum doc's own citation).

This is not the same shape as `FeatureVector`
(`src/agro_mirai/processing/feature_builder.py`, per
`specs/core/features.md`): `FeatureVector` has rolling weather windows
(7/14/30-day sums/means), soil pass-through plus a derived NPK balance
index, NDVI latest/trend/source, and a season heuristic — none of which
line up 1:1 with the Kaggle columns. A mapping has to be chosen and
documented before training, not reverse-engineered from the trained
model's `feature_names_in_` afterward.

## Decision

The model is trained directly on the Kaggle dataset's native 7 columns
(`N, P, K, temperature, humidity, ph, rainfall`) — training data is not
reshaped to match `FeatureVector`, because the Kaggle dataset has no
NDVI or rolling-window weather columns to train against and fabricating
them would invent signal that isn't in the data. Instead,
`crop_feature_mapping.py` (`src/agro_mirai/models/crop_feature_mapping.py`)
maps a `FeatureVector` to the model's expected input row at
**prediction** time:

| Model column | `FeatureVector` source | Notes |
|---|---|---|
| `N` | `soil_nitrogen_mg_per_kg` | direct pass-through |
| `P` | `soil_phosphorus_mg_per_kg` | direct pass-through |
| `K` | `soil_potassium_mg_per_kg` | direct pass-through |
| `temperature` | `temp_c_mean_14d` | 14-day window chosen as the middle ground: 7d is noisy day-to-day, 30d smooths past recent conditions too much for a point-in-time recommendation |
| `humidity` | `humidity_pct_mean_14d` | same 14d rationale as temperature |
| `ph` | `soil_ph` | direct pass-through |
| `rainfall` | `rainfall_mm_sum_30d` | rainfall is a monthly-scale signal in the Kaggle data (values range ~20-300mm); 30d sum is the closest analog to "seasonal rainfall available to the crop", vs. 7d/14d which would read as too low relative to training distribution |

`ndvi_*` and `season`/`days_since_sowing` are **not used** by this
model version — the Kaggle dataset has no vegetation-index or
sowing-date signal to train against, so there is nothing for those
`FeatureVector` fields to map onto. They remain available on the vector
for other consumers (Modules 07-08) and for a future model version that
trains against a richer feature set.

`soil_npk_balance_index` is also not used directly — the model gets the
raw N/P/K instead of the derived ratio, since that is what it was
trained on.

**Missing-data handling at prediction time:** the mapping function
raises `ValueError` if `soil_data_available` is `False` (no `N`/`P`/`K`/
`ph` to map) or if all three 14d/14d/30d weather windows it needs are
`None`. This mirrors `FeatureBuilder`'s own "fail loudly on required-data
absence" policy (ADR 0006) rather than silently defaulting to `0.0`,
which — per ADR 0006's own reasoning — would misrepresent "we don't
know" as a real measurement the model would trust.

## Consequences

- The model wrapper (`CropRecommendationModel`) depends on both the
  trained artifact's column order and this mapping being kept in sync;
  a change to either needs a corresponding change to the other, and
  `tests/models/test_crop_feature_mapping.py` pins the exact column
  order as a regression guard.
- If a future module wants NDVI or season signal to influence crop
  recommendation, that requires either retraining against an augmented
  dataset or a second model stage — not a change to this mapping.
- Because soil data availability is a hard requirement for this mapping,
  `CropRecommendationModel.predict` cannot serve a field with no soil
  sample at all; callers must check `soil_data_available` before calling
  it, same as any other Module 06+ consumer of `FeatureVector`.
