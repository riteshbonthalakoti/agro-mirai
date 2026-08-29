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

**Modules 01–15 (the original capstone scope) are complete. A second, explicitly non-academic-pace push — Modules 16–19 — is now underway to take the project from "capstone MVP" toward "production grade"; see `docs/ROADMAP_PRODUCTION.md` for why and what's in scope.** Module 16 (Reliability & CI Hardening — workstream A) landed 2026-08-29: GitHub Actions CI (`.github/workflows/ci.yml`, gates on `pytest --ignore=tests/voice` + `check_specs.py`, non-blocking `ruff` lint), Sentry error monitoring (`sentry-sdk[flask]`, no-op without `SENTRY_DSN`), request-id structured logging, an input-validation audit of `POST /fields`/`POST /feedback` (real gaps found and fixed — see `src/agro_mirai/api/validation.py`), `tools/backup_supabase.py` + `docs/BACKUPS.md`, and per-API-key rate limiting (Flask-Limiter, 60/min default).

Module 17 (ET0-based irrigation water balance) landed 2026-08-29, ahead
of multi-tenant/Admin per Ritesh's explicit sequencing call (model/
backend logic first, so multi-tenant auth isn't layered on top of models
about to change — see `module-17-prompt.md`'s sequencing note and
`docs/ROADMAP_PRODUCTION.md`'s renumbering note). `recommended_depth_mm`
on `IrrigationAdvice` is no longer the fixed `_URGENCY_TO_DEPTH_MM`
lookup from Module 07 — `IrrigationPredictionModel.predict`
(`src/agro_mirai/models/irrigation_prediction_model.py`) now runs a
water balance: reference evapotranspiration via the Hargreaves-Samani
method (`src/agro_mirai/models/evapotranspiration.py`, FAO-56 Ch.3
Eq 21/52, needs only temperature + latitude/day-of-year — chosen over
Penman-Monteith because this project doesn't reliably have solar
radiation/wind/VPD) times a crop coefficient Kc looked up by crop and
FAO-56-approximated growth stage
(`src/agro_mirai/models/crop_coefficients.py`, FAO-56 Table 12, covers
all 22 `crop_type` labels from `docs/eval/crop_rf_eval.json`, three
crops mapped to a documented closest analog where FAO-56 has no direct
entry), minus `rainfall_mm_sum_7d`, floored at a 2mm minimum. The
trained `urgency` classifier (low/moderate/high, RandomForest, unchanged
from Module 07) still gates the advisory window length via
`_URGENCY_TO_WINDOW_DAYS`. `FeatureVector`
(`src/agro_mirai/processing/feature_builder.py`) gained four additive
optional fields the water balance needed and didn't previously have:
`temp_c_min_7d`/`temp_c_max_7d` (from `WeatherReading.temp_min_c`/
`temp_max_c`, previously only aggregated into means),
`latitude`/`crop_type` (pass-through from `Field_`) —
`specs/core/features.md` documents all four.
`decisions/0015-et0-water-balance.md` supersedes the
`recommended_depth_mm` section of `decisions/0008-irrigation-model-feature-mapping.md`
(0008 itself is annotated, not rewritten) and has the full reasoning,
including the missing-Tmin/Tmax fallback (a documented +/-4C diurnal-
range approximation from the mean, not a raised error, per this
project's degrade-not-fail doctrine) and why urgency still drives the
window instead of being derived from the deficit. 20 new/updated tests
across `tests/models/test_evapotranspiration.py` (new, golden Ra/ET0
values), `tests/models/test_crop_coefficients.py` (new, full label-set
coverage + stage breakpoints), and
`tests/models/test_irrigation_prediction_model.py` (extended — the old
fixed-depth assertions are gone, replaced with assertions that depth
varies with rainfall and the rationale cites real ET0/ETc/deficit
numbers); `tests/models/test_irrigation_model_integration.py` and the
full API/`DecisionEngine` regression suite pass unchanged against the
new code path. Module 18 (multi-tenant data model + real login/session
auth + read-only Admin dashboard) and Module 19 (CNN disease model on
PlantVillage) are next — see `docs/ROADMAP_PRODUCTION.md` and
`PROGRESS.md`'s Module 17 entry for the full handoff. See
`decisions/0014-deploy-target-and-voice-scope.md` for Module 15's
deploy-target and voice-scope calls, `docs/DEMO_DAY.md`/
`docs/DEMO_SCRIPT.md` for the live review. The crop recommendation model
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

Module 09 (Explainability) is done: `ExplanationService`
(`src/agro_mirai/models/explanation_service.py`) turns any of the three
models' predictions into a uniform `Explanation`
(`src/agro_mirai/models/explanation.py`) — `explain_crop` and
`explain_irrigation` use `shap.TreeExplainer` against the real
`crop_rf.joblib`/`irrigation_rf.joblib` artifacts (`method="shap_tree"`);
`explain_disease` has no trained artifact to explain, so it reports the
exact weight×signal decomposition `disease_risk_scoring.py` already
computes (`method="rule_weight"`), explicitly labeled "contributing
factor," never "SHAP value" — `decisions/0010-explainability.md` has
the full reasoning for the split. `summary_kn` is populated by calling
an injected `VoiceService.translate` (Module 12); the service defaults
to no `VoiceService` and leaves `summary_kn=None`, so it's testable
without the AI4Bharat stack. `shap` was added as a new dependency
(no project-wide manifest exists yet, so it's installed directly into
the interpreter the way `scikit-learn`/`joblib` were for Modules 06/07).
9 tests in `tests/models/` cover unit plumbing (mocked
`shap.TreeExplainer` for crop/irrigation, no mocking needed for
disease) and integration against the real crop/irrigation artifacts and
farm-001/farm-002 fixtures — irrigation's top contributors include
`Soil_Moisture`, as expected agronomically. Module 10
(Decision & Recommendation Engine) can start now.

Module 10 (Decision & Recommendation Engine) is done:
`DecisionEngine.recommend(field, features) -> Advisory`
(`src/agro_mirai/models/decision_engine.py`) orchestrates Modules 06/07/08
and `ExplanationService` for a single `FeatureVector`, always calling all
three model wrappers (no data-availability gating in the engine itself —
each wrapper already degrades under partial data per its own module's
policy) and never synthesizing across their outputs — `Advisory.body` is
the three `Explanation.summary_en` sentences concatenated unmodified.
`Advisory.severity` is the max of `IrrigationAdvice.urgency` and
`DiseaseRiskAlert.risk_level` on the shared `risk_level` ladder; this
doubles as the immediate-action alert signal
(`severity in {"high", "severe"}`) — no new schema field was added,
since `severity` already carries that information.
`decisions/0011-decision-engine.md` documents the full reasoning:
pass-through synthesis over conflict resolution, always-call over
per-model gating, and the `Advisory` field mapping table.

18 tests in `tests/models/`: 15 unit tests (`test_decision_engine.py`,
all four dependencies mocked) covering schema-valid output and the
severity/alert-threshold logic across the full urgency x risk_level
matrix, and 3 integration tests (`test_decision_engine_integration.py`)
running farm-001/farm-002 through the real `FeatureBuilder` and real
crop/irrigation artifacts end to end, plus a synthetic high-urgency
input confirming the alert threshold fires. This is the first test
proving Modules 05-09 compose correctly together. Module 11 (API Layer,
Flask) can start now.

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
all passing under `.venv/Scripts/python.exe`.

Module 11 (API Layer) is done: `src/agro_mirai/api/` exposes Modules
06-10's `DecisionEngine` and the underlying models plus the `DataStore`
behind Flask endpoints matching `specs/core/openapi.yaml` exactly (no
new endpoints were needed — the spec already covered
farmers/fields/recommendation/irrigation/disease-risk/advisories/feedback).
`create_app(config=None) -> Flask` (`src/agro_mirai/api/app.py`) is the
app factory: it builds the `DataStore`/model singletons once per app and
stores them in `app.extensions`, never as module-level globals, so tests
can inject mocks or a real `SQLiteDataStore` via the `config` dict
(`DATA_STORE`, `CROP_MODEL`, `IRRIGATION_MODEL`, `DISEASE_MODEL`,
`DECISION_ENGINE` keys). Auth is a single shared `API_KEY` checked
against `Authorization: Bearer <key>` (`src/agro_mirai/api/auth.py`) —
not JWT/OAuth, per the module's own scope — mapped to one `FARMER_ID`
per ADR 0003 (single-farmer-per-account). Every 400/401/404/422/500
response uses the `{"error": {"code","message","details"}}` envelope
(`src/agro_mirai/api/errors.py`), never Flask's default HTML error page.

Because `openapi.yaml` has no separate "generate" endpoint, each
GET under `/fields/{field_id}/...` (recommendation, irrigation,
disease-risk, advisories) both computes and persists: it builds a fresh
`FeatureVector` from whatever the `DataStore` currently holds
(`src/agro_mirai/api/features.py`), runs the relevant model (or the full
`DecisionEngine` for advisories), saves the result via `DataStore`, and
returns it — a missing-weather `FeatureBuilder` error becomes a 422, not
a 500. `POST /feedback` is fully implemented against
`DataStore.save_feedback_entry` (not a placeholder stub) since the CRUD
was trivial to wire; Module 13 builds aggregation/analysis on top of what
this persists.

22 tests: 16 unit tests (`tests/api/test_routes_unit.py`, `DataStore` and
all four model/engine dependencies mocked) covering response shape, auth
rejection (missing/wrong key -> 401), and 404s; 6 integration tests
(`tests/api/test_integration.py`) against a real Flask test client, a
real `SQLiteDataStore` seeded from `farm-001.json` via
`tools/seed_fixture.py`'s loader, and the real crop/irrigation
artifacts — confirming a schema-valid `Advisory` end to end, health,
auth, and unknown-field-id -> 404 (not 500). Full suite (excluding
`tests/voice/`, which needs the project-local `.venv/` for `torch`):
145 passed, 0 failed, 19 skipped.

Module 14 (Frontend) ran concurrently with Module 13, in a separate
session working the same repo/origin — no conflicts on push.
`decisions/0013-frontend-platform-sequencing.md` locks the platform
build order (web now, mobile next, WhatsApp/messaging after, so it
isn't re-litigated) and the stack: server-rendered Jinja2 templates and
a new `frontend` blueprint added additively inside Module 11's own
Flask process (`src/agro_mirai/api/templates/`,
`src/agro_mirai/api/static/`, `src/agro_mirai/api/routes/frontend.py`)
— not a separate React/Vite SPA service, so Module 15 has one process
to deploy, not two. The frontend calls Module 11's JSON API
exclusively, never `DecisionEngine`/model classes directly, via
`src/agro_mirai/api/frontend_client.py`: an in-process helper that runs
real request/response round trips through `current_app.test_client()`
with the server-held `API_KEY` attached server-side (never sent to the
browser). Three screens: single-farmer dashboard (per ADR 0003), field
detail (crop recommendation / irrigation advice / disease-risk alerts /
advisories with severity badges, all pulled from the real GET
endpoints), and an inline feedback form per advisory posting to
`POST /feedback`. "Listen in Kannada" TTS was not built — no endpoint
exposes `Explanation.summary_kn` or `VoiceService` audio today; noted
as a known limitation in the ADR and on the page itself rather than
silently dropped. 15 tests in `tests/frontend/`: 8 unit (mocked API
layer, covering the 404/422-tolerant degradation helpers) and 7
integration (real Flask app, real `DecisionEngine`, real crop/irrigation
artifacts, farm-001 fixture) confirming the field-detail page's
rendered advisory data matches `GET /fields/{id}/advisories` exactly,
an unknown field id renders a 404 error page not a 500, and a feedback
POST is retrievable afterward via `DataStore.list_feedback_for_advisory`.
No new API endpoints were needed. Full suite (excluding `tests/voice/`):
177 passed, 0 failed, 19 skipped.

Modules 13 and 14 are both done. Module 14b (UI/UX Uplift) is also
done — a presentation-layer-only redesign of the Module 14 web
frontend (design tokens, real visual hierarchy, colorblind-safe
severity indicators, accessible star rating), with no route/contract
changes; see `PROGRESS.md` for details. Module 15 (Integration,
deploy, docs) can start now — see `PROGRESS.md` for the full
15-module plan and status.
