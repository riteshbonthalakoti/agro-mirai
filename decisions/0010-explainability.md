# ADR 0010 — Explainability: SHAP for trained classifiers, direct attribution for the rule-based model

**Status:** accepted
**Date:** 2026-08-26
**Module:** 09 — Explainability

## Context

Module 10 (Decision & Recommendation Engine) needs to attach an
explanation to any advisory output — crop recommendation, irrigation
advice, disease risk alert — regardless of which of the three Module
06/07/08 models produced it. The three models are not uniform under the
hood: Modules 06 and 07 wrap `RandomForestClassifier` artifacts
(`models/crop_rf.joblib`, `models/irrigation_rf.joblib`); Module 08
(`decisions/0009-disease-risk-model.md`) is a documented weighted
threshold formula with no trained artifact at all. An explainability
layer that pretends these are the same kind of thing would misrepresent
what Module 08 actually is — the opposite of ADR 0009's stated
commitment to being explicit about the rule rather than laundering it
into something that looks learned.

## Decision: SHAP for Modules 06/07, direct attribution for Module 08

### Why `shap.TreeExplainer` fits Modules 06/07

`shap.TreeExplainer` computes exact Shapley values for tree ensembles
(no sampling approximation, unlike `KernelExplainer`) — appropriate
here because both artifacts are `RandomForestClassifier` instances and
the exact algorithm is available and fast for tree models. For a single
prediction, it returns a per-feature contribution to the predicted
class's log-odds/probability, which is exactly the "why did the model
say this" question a farmer-facing advisory needs to answer: e.g. "soil
pH was the biggest factor pushing toward `Medium` irrigation need." SHAP
values are additive (they sum to the difference between the prediction
and the model's average output), which is what makes "top-3
contributors" a coherent, non-arbitrary summary rather than an ad hoc
ranking.

In the farmer-facing context, a SHAP value is presented as "how much
this factor pushed the recommendation, and in which direction" — not as
a probability or a causal claim. `Explanation.summary_en` states this in
plain language (e.g. "high soil nitrogen and moderate rainfall were the
biggest factors favoring rice"), never as a raw SHAP number.

### Why SHAP does not apply to Module 08, and what replaces it

There is no trained model for SHAP to explain — `score_disease_risk`
(`src/agro_mirai/models/disease_risk_scoring.py`) is a fixed linear
weighted sum: `score = 0.40*humidity_score + 0.25*rainfall_score +
0.15*temp_score + 0.20*ndvi_score`. Running `TreeExplainer` (or any
SHAP explainer) against a formula with no `predict`/`predict_proba`
model object and no training data to sample a background distribution
from does not compute anything meaningful — it would require wrapping
the formula in a fake "model" purely to produce SHAP-shaped output,
which is exactly the kind of laundering ADR 0009 already rejected once
for this module (inventing a trained-looking artifact where none
exists).

**Instead**: `ExplanationService.explain_disease` reads the same four
weighted terms `score_disease_risk` already computes
(`weight × component_score` for humidity/rainfall/temp/ndvi) and reports
them directly as per-feature contributions. This is not an
approximation of SHAP — it is the exact, complete decomposition of the
formula, because the formula is already a linear sum of weighted terms.
No estimation step exists to introduce SHAP's semantics (baseline
comparison, coalition sampling) where there is no model to sample
around.

Every `Explanation` produced by `explain_disease` sets
`method="rule_weight"` and each `FeatureContribution.label` is rendered
as `"contributing factor"`, never `"SHAP value"` — enforced by the
`method` field, not left to the caller to remember. Module 10 (or any
future caller) can branch on `Explanation.method` if it needs to treat
the two differently (e.g. show a "statistically learned" vs.
"rule-based" badge in the UI); it never has to guess which kind of
explanation it received.

## The `Explanation` output shape

```python
@dataclass
class FeatureContribution:
    feature_name: str        # e.g. "soil_ph", "humidity_pct_mean_14d"
    feature_value: float
    contribution: float      # signed magnitude — SHAP value or weight×signal
    direction: str           # "increases" | "decreases", sign of contribution

@dataclass
class Explanation:
    id: str
    field_id: str
    created_at: datetime
    subject_type: str         # "crop_recommendation" | "irrigation_advice" | "disease_risk_alert"
    subject_id: str           # id of the CropRecommendation/IrrigationAdvice/DiseaseRiskAlert explained
    method: str                # "shap_tree" | "rule_weight"
    top_contributions: list[FeatureContribution]  # top-k, ordered by |contribution| descending
    summary_en: str
    summary_kn: str | None     # None when no VoiceService was injected
```

This is a plain dataclass in `src/agro_mirai/models/explanation.py`, not
a `schema.yaml` entity — it is Module 09's own output contract, only
consumed in-process by Module 10, not persisted or exposed over an API
in v1. If a later module needs to persist or serve explanations,
promoting it into `schema.yaml` is an additive schema change (hard rule
2), not a redesign of this shape.

`subject_type`/`subject_id` let Module 10 correlate an `Explanation`
back to the specific advisory record it explains, since one
`FeatureVector` can produce three separate advisories (crop, irrigation,
disease) each needing its own explanation.

`summary_kn` is produced by calling the injected `VoiceService.translate`
(`specs/core/voice-interface.md`) on `summary_en` — `ExplanationService`
does not reimplement translation. The `VoiceService` is a constructor
argument defaulting to `None`; when `None`, `summary_kn` stays `None`
and no translation is attempted. This keeps `ExplanationService`
testable without pulling in the AI4Bharat model stack
(`decisions"/0009` and the Module 12 handoff both note that stack's
`.venv/`-only dependency weight), and matches the injection pattern
already used for cross-module dependencies elsewhere in the codebase.

## Consequences

- Modules 06/07 explanations depend on `shap` (new dependency — no
  project-wide requirements manifest exists yet in this repo, so `shap`
  is installed directly into the interpreter Modules 06-09 already run
  under, same as `scikit-learn`/`joblib` were for Modules 06/07).
- Module 08's explanation is honest about being formula decomposition,
  not SHAP — `method="rule_weight"` is a durable, machine-checkable
  marker of this, not just a prose caveat.
- If Module 08 ever gains a trained artifact (the CNN upgrade path in
  ADR 0009), `explain_disease` would be replaced by a SHAP-based path
  the same shape as `explain_crop`/`explain_irrigation` — no change to
  `Explanation`'s shape, only to which method populates it.
