# ADR 0009 — Disease risk model: environmental threshold scoring, not image classification

**Status:** accepted
**Date:** 2026-08-26
**Module:** 08 — Crop Health / Disease Risk

## Context

The roadmap's decision 5 locks Module 08's scope before this module
started: a threshold/lightweight risk model MVP, not a PlantVillage-trained
image CNN. No photo input exists anywhere upstream (no `Field`/`FeatureVector`
field carries an image), so an image classifier isn't a smaller version of
this module — it's a different module with a different input contract.
Building environment-driven risk from what `FeatureBuilder` already
produces is the only version of Module 08 achievable without adding a new
data-acquisition path first.

`DiseaseRiskAlert` (`specs/core/schema.yaml`) needs: `disease` (free-text
for v1), `risk_level` (`risk_level` enum: `low`/`moderate`/`high`/`severe`
— same ladder as irrigation urgency), `confidence` (float 0–1),
optionally `window_start_at`/`window_end_at`/`recommended_action`.

No proxy-labeled dataset was found that maps weather/NDVI features to a
disease-risk label the way Module 06/07 had labeled crop/irrigation
datasets — searched Kaggle for "crop disease weather" / "plant disease
environmental risk" and found only image-labeled datasets (PlantVillage
and variants), which don't fit this module's input shape. **This model
is threshold-based, calibrated against agronomic extension reasoning, not
a labeled dataset** — documented here rather than inventing thresholds
with no stated basis.

## Decision: which signals, and why each is a real disease-risk proxy

Four `FeatureVector` fields drive the score. Each is picked because it is
an established environmental driver of fungal disease pressure in
agronomy extension practice specifically — not just reused because it
happened to be available:

| Signal | `FeatureVector` field | Why this is a disease-risk signal specifically |
|---|---|---|
| Sustained humidity | `humidity_pct_mean_14d` | Relative humidity above ~80% sustained over days is the classic driver of fungal spore germination and infection — it controls leaf-wetness duration, the rate-limiting step for blast/blight/rust/powdery-mildew infection cycles. A 14-day window (not 7d) is used because disease *pressure* builds from sustained conditions, not a single humid day — same windowing rationale as ADR 0007/0008. |
| Recent rainfall | `rainfall_mm_sum_7d` | Rain drives leaf wetness directly and disperses fungal spores by splash. The 7-day window (not 30d) is deliberate here — unlike irrigation's cumulative soil-moisture need, disease pressure from rain is a *recent-event* signal: a wet week now matters more than a wet month a while back. |
| Temperature | `temp_c_mean_14d` | Most fungal pathogens affecting Indian field crops have an optimal growth window of roughly 20–30°C; both high humidity and cool/hot temperatures outside that band suppress fungal activity even when moisture is present. Temperature therefore modulates the humidity/rainfall signals rather than acting alone. |
| NDVI trend | `ndvi_trend`, gated on `ndvi_data_available` | A declining NDVI trend *co-occurring with* favorable disease weather is a real proxy for canopy stress consistent with disease progression — this is why it's combined with, not used instead of, the weather signals. Used only as a stress corroborator: on its own a declining NDVI has other causes (harvest, senescence, water stress), so a missing/absent decline contributes zero penalty rather than lowering the score. |

`season` and `soil_*` are **not used**: no defensible disease-specific
mechanism for either was found in the reasoning above — a difference
from Modules 06/07, which used season and soil chemistry because those
datasets showed those columns predictive for their targets. Reusing them
here without a mechanism would be the "included because available" trap
the module brief calls out.

## Decision: rule-based scoring, not a trained classifier

**Rule/threshold system**, not a trained model. Justification against
what's achievable: a trained classifier needs a labeled dataset mapping
these features to a risk outcome, and none was found (see Context). Faking
one — e.g. self-labeling synthetic thresholds as "ground truth" and
training a classifier on invented labels — would launder a rule into
something that looks learned, the same anti-pattern ADR 0008 rejected for
`recommended_depth_mm`. Being explicit about the rule is preferable, and
matches the module brief's threshold/lightweight-risk-model framing.

### Scoring function

`src/agro_mirai/models/disease_risk_scoring.py::score_disease_risk`
computes a weighted composite in `[0, 1]`:

```
score = 0.40 * humidity_score
      + 0.25 * rainfall_score
      + 0.15 * temp_score
      + 0.20 * ndvi_score
```

| Component | Formula | Rationale for the shape |
|---|---|---|
| `humidity_score` | `clip((humidity_pct_mean_14d − 50) / 40, 0, 1)` | 0 at ≤50% RH (no meaningful fungal pressure below this), 1.0 at ≥90% RH (saturation-level infection conditions); linear between. Highest weight (0.40) — humidity is the single strongest driver per the Context table. |
| `rainfall_score` | `clip(rainfall_mm_sum_7d / 40, 0, 1)` | 0 at no rain, 1.0 at ≥40mm in 7 days (a heavy monsoon week). |
| `temp_score` | `1 − clip(abs(temp_c_mean_14d − 25) / 10, 0, 1)` | Peaks at 25°C (center of the 20–30°C fungal-optimal band), decays linearly to 0 by 15°C or 35°C. Lowest weight (0.15) — a modulator, not a primary driver. |
| `ndvi_score` | if `ndvi_data_available` and `ndvi_trend < 0`: `clip(−ndvi_trend / 0.05, 0, 1)`, else `0` | A single-step NDVI drop of 0.05 or more is treated as a strong stress signal (full weight); no data or a flat/rising trend contributes nothing — never a penalty for missing NDVI, per the missing-data policy precedent in ADR 0006. |

Risk-level thresholds on the composite score:

| `score` | `risk_level` |
|---|---|
| `< 0.30` | `low` |
| `0.30 – 0.50` | `moderate` |
| `0.50 – 0.70` | `high` |
| `≥ 0.70` | `severe` |

### Confidence

Not a model probability (there is no trained model) — it reflects
**evidence completeness**, and is documented as such rather than
implying statistical certainty it doesn't have:

```
confidence = 0.5 (weather, always available per FeatureBuilder)
           + 0.3 if ndvi_data_available else 0.0
           + 0.2 if rainfall/humidity 14d values are both non-None else 0.0
```

Range: `0.5` (weather only, e.g. farm-002-shaped fields with no NDVI) up
to `1.0` (full data). `humidity_pct_mean_14d`/`temp_c_mean_14d` are only
`None` if `FeatureBuilder`'s 14d window has zero readings, which cannot
happen given `FeatureBuilder.build`'s weather-required invariant — the
`+0.2` term is effectively always earned; the check exists so the
function degrades explicitly rather than raising if that invariant ever
changes upstream.

### `disease`, `recommended_action`, advisory window

`disease` is a fixed generic string for v1 —
`"Generic fungal disease risk (environmental proxy — no image-based diagnosis)"`
— honest about what this model version can and can't name, per
`schema.yaml`'s own "free-text for v1" note on the field.

`recommended_action` and the `window_start_at`/`window_end_at` pair are
rule-based lookups keyed off `risk_level`, same pattern as ADR 0008's
depth/window lookup:

| `risk_level` | `recommended_action` | Window |
|---|---|---|
| `low` | Continue routine monitoring; no action needed. | 14 days |
| `moderate` | Increase field scouting frequency; watch for early lesions or leaf spotting. | 7 days |
| `high` | Scout field within 2 days; consider preventive fungicide application per local extension guidance. | 2 days |
| `severe` | Scout immediately; apply fungicide per local extension guidance and consider improving field drainage/airflow. | 1 day |

## CNN upgrade path (explicit, additive)

A future image-based classifier would need:

1. A new input path — a photo, not a `FeatureVector` — meaning a new
   acquisition/storage concern (image upload, storage location) that
   doesn't exist yet anywhere in this codebase. This is genuinely new
   surface area, not a drop-in replacement of `score_disease_risk`.
2. A new wrapper, e.g. `ImageDiseaseRiskModel`, with its own
   `predict(image, field_id) -> DiseaseRiskAlert` — **not** a change to
   `DiseaseRiskModel.predict(FeatureVector) -> DiseaseRiskAlert`'s
   signature. Both can coexist; a caller (Module 09+) picks whichever is
   available for a given field, or a future `DiseaseRiskModel` could try
   the image path first and fall back to the environmental one, mirroring
   the GEE-live/NDVI-cache fallback pattern in hard rule 4.
3. **No change to `DiseaseRiskAlert`'s shape.** Confirmed field by field:
   `disease` becomes species-specific instead of the fixed generic string
   (still a free-text string — no type change); `confidence` becomes a
   real softmax probability instead of an evidence-completeness score
   (still a float in `[0, 1]` — no type change); `risk_level` is derived
   from the predicted class's known severity instead of the composite
   score (still the same `risk_level` enum); `window_*`/`recommended_action`
   keep the same risk-level-keyed lookup. This is a genuinely additive
   swap — a new model implementation behind the same output contract —
   not a rewrite of the schema or of Module 09's calling convention.

## Consequences

- `DiseaseRiskModel.predict` returns a schema-valid `DiseaseRiskAlert`
  end to end, but nothing in it is a trained-model output — this must be
  stated plainly in the Module 08 handoff, same as ADR 0008 called out
  the depth-mm gap.
- No trained-artifact coupling risk (unlike Modules 06/07): there is no
  `.joblib` file, no column-order pinning, no `models/` gitignore entry
  needed for this module.
- If a proxy-labeled dataset is found later, only `score_disease_risk`'s
  internals need to change — `DiseaseRiskModel`'s public interface and
  `DiseaseRiskAlert`'s shape stay the same, same durability argument as
  ADR 0008's depth-mm lookup.
