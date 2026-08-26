# AGRO MIRAI

AI-driven smart agriculture advisory system — VTU Sem 7 capstone, BITM Dept. of AIML.

## Hard rules [LOCKED]

1. **CLI-first, always.** Before touching any external service (GitHub,
   Supabase, Render, Google Cloud/Earth Engine, Hugging Face, Kaggle), use
   its official CLI. Never hand-describe a dashboard click-path when a CLI
   command does the same thing.
2. **Additive-only data contracts.** Once a schema/contract is published in
   `specs/`, changes are additive (new optional fields, new endpoints) —
   never breaking renames or removals without a new versioned contract.
3. **SQLite-dev / Supabase-prod via a repository interface.** No module
   talks to a database engine directly. All persistence goes through a
   repository abstraction so the same code runs against local SQLite in dev
   and Supabase Postgres in prod.
4. **GEE-live-with-NDVI-cache fallback.** Google Earth Engine is the live
   source for satellite/NDVI data; every GEE-dependent module must degrade
   to a local NDVI cache when GEE is unavailable, not fail outright.
5. **Module N+1 never starts before module N is tested and committed.**
   Strict dependency gating — no skipping ahead.

## Nothing is hand-faked

If a step needs human auth (browser OAuth, API key), STOP, print the exact
command and what it will ask for, wait for the human. Never simulate
success.

## Repo map

```
agro-mirai/
  CLAUDE.md              # this file — doctrine, hard rules, current phase
  PROGRESS.md            # session handoff log, regenerated state block
  docs/
    TOOLING.md             # verified CLI versions + auth status
    architecture.md        # system architecture (from Module 02)
  specs/
    core/                  # cross-cutting contracts (from Module 02):
                            #   schema.yaml, enums.md, openapi.yaml,
                            #   repository-interface.md
    domains/               # per-domain contracts + golden fixtures
  decisions/
    0001-index.md           # ADR index
    NNNN-<slug>.md           # individual ADRs
  modules/
    01-foundation/           # this module's notes + tests
    ...                      # one dir per module, each with a STATUS file
  tools/
    update_state.py          # regenerates PROGRESS.md's state block
  tests/
```

Each `modules/NN-<name>/` directory carries a `STATUS` file
(`not-started` / `in-progress` / `done`) that `tools/update_state.py` reads
to build the phase table in `PROGRESS.md`.

## Current phase

**Modules 06, 07, 08, and 12 complete. Module 09 next.** The crop recommendation model
(`src/agro_mirai/models/crop_recommendation_model.py`) wraps a
`RandomForestClassifier` (`tools/train_crop_model.py`, seed=42) trained
on the Kaggle crop-recommendation-dataset's native 7 columns against all
22 `crop_type` labels — held-out accuracy 0.9955, macro-F1 0.9955
(`docs/eval/crop_rf_eval.json`). The artifact (`models/crop_rf.joblib`)
is gitignored and reproducible by re-running the training script; the
eval report is committed. `decisions/0007-crop-model-feature-mapping.md`
documents the `FeatureVector` → model-input mapping
(`src/agro_mirai/models/crop_feature_mapping.py`) used at prediction
time: soil N/P/K/ph pass through, 14-day temp/humidity means, 30-day
rainfall sum; NDVI and season are not consumed by this model version.
`CropRecommendationModel.predict(FeatureVector) -> CropRecommendation`
matches `specs/core/schema.yaml` exactly and keeps sklearn out of the
public interface. 12 tests in `tests/models/` cover the feature-mapping
function in isolation, schema-valid wrapper output (reusing
`check_specs.py`'s validation logic), and the full
farm-001/farm-002 → `FeatureBuilder` → mapping → `predict` chain end to
end. Module 07 (Irrigation Prediction Model) can start now.

Module 07 (Irrigation Prediction Model) is done: `IrrigationPredictionModel`
(`src/agro_mirai/models/irrigation_prediction_model.py`) wraps a
`RandomForestClassifier` (`tools/train_irrigation_model.py`, seed=42)
trained on the Kaggle irrigation-water-requirement-prediction-dataset's
6 columns (soil pH/moisture, 14d temp/humidity means, 30d rainfall sum,
one-hot season) against the 3-class `Irrigation_Need` label — held-out
accuracy 0.7240, macro-F1 0.5796 (`docs/eval/irrigation_rf_eval.json`).
Only `urgency` is a trained output; `recommended_depth_mm` and the
advisory window are a documented rule-based lookup keyed off the
predicted urgency, since no dataset with a continuous depth-mm target
was found — `decisions/0008-irrigation-model-feature-mapping.md` has
the full reasoning. Module 09-10 can consume `IrrigationPredictionModel`
the same way they consume `CropRecommendationModel`.

Module 08 (Crop Health / Disease Risk) is done: `DiseaseRiskModel`
(`src/agro_mirai/models/disease_risk_model.py`) wraps a documented
threshold/scoring MVP — `score_disease_risk`
(`src/agro_mirai/models/disease_risk_scoring.py`) — not a trained
classifier or image CNN, per the roadmap's locked scope decision 5. The
score is a weighted composite over `FeatureVector`'s
`humidity_pct_mean_14d` (weight 0.40), `rainfall_mm_sum_7d` (0.25),
`temp_c_mean_14d` (0.15), and `ndvi_trend` when available (0.20), each
picked for an agronomic disease-risk mechanism, not just availability —
`decisions/0009-disease-risk-model.md` has the full reasoning, the
threshold table, the confidence-as-evidence-completeness formula, and
the explicit CNN upgrade path (additive — no `DiseaseRiskAlert` schema
change needed). No labeled dataset exists for this target, unlike
Modules 06/07, so there is no trained artifact and no `models/*.joblib`
for this module. `DiseaseRiskModel.predict(FeatureVector) ->
DiseaseRiskAlert` matches `specs/core/schema.yaml` exactly and follows
Modules 06/07's calling convention. 16 tests in `tests/models/` cover
the scoring function in isolation (including a deliberately high-risk
and a deliberately low-risk synthetic input), schema-valid wrapper
output, and the full farm-001/farm-002 → `FeatureBuilder` → score →
predict chain end to end. Module 09 (Explainability/SHAP) can start
now — it needs Modules 06, 07, and 08 all done.

Module 12 (Voice & Language) ran concurrently, independent of 06:
`VoiceService` (`specs/core/voice-interface.md`,
`src/agro_mirai/voice/interface.py`) covers translate/speech_to_text/
text_to_speech for v1's `en`+`kn` scope. `AI4BharatVoiceService`
(`src/agro_mirai/voice/ai4bharat_voice.py`) is the live implementation —
IndicTrans2 distilled 200M for translation, `indic-conformer-600m-multilingual`
+ `whisper-tiny.en` for ASR, Piper + `vits_rasa_13` for TTS, three
substitutions away from the module's original per-capability picks
forced by real gaps in what AI4Bharat/Piper actually ship (see
`docs/architecture.md`). `BhashiniVoiceAdapter`
(`src/agro_mirai/voice/bhashini_voice.py`) is a stub behind the same
interface, not blocked on Bhashini access. Requires the project-local
`.venv/` (transformers pinned to 4.49.0 — the global interpreter's
transformers 5.x is incompatible with these AI4Bharat models in three
separate ways, see `docs/architecture.md`). 25 tests in `tests/voice/`,
all passing under `.venv/Scripts/python.exe`. See `PROGRESS.md` for the
full 15-module plan and status.
