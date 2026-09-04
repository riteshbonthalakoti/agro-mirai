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

**Modules 01–23 are complete. The backend/production-hardening push (Modules 16–23, `docs/ROADMAP_PRODUCTION.md`) that took the project from "capstone MVP" toward "production grade" is now finished — Module 23 froze `specs/core/openapi.yaml` as the contract the frontend gets built against. Next: the frontend phase (PRD, then Antigravity — React Native + Expo mobile app, Next.js landing page, Module 19's Jinja2 admin kept as-is), not yet started.** Module 16 (Reliability & CI Hardening — workstream A) landed 2026-08-29: GitHub Actions CI (`.github/workflows/ci.yml`, gates on `pytest --ignore=tests/voice` + `check_specs.py`, non-blocking `ruff` lint), Sentry error monitoring (`sentry-sdk[flask]`, no-op without `SENTRY_DSN`), request-id structured logging, an input-validation audit of `POST /fields`/`POST /feedback` (real gaps found and fixed — see `src/agro_mirai/api/validation.py`), `tools/backup_supabase.py` + `docs/BACKUPS.md`, and per-API-key rate limiting (Flask-Limiter, 60/min default).

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
new code path.

Module 18 (Crop model localization — Karnataka/Bellary sanity layer)
landed 2026-08-29, the second of two model-realism modules run ahead of
multi-tenant/Admin (now Module 19) and the CNN disease model (now
Module 20) per the same sequencing rationale as Module 17. A real
dataset investigation (web search across Kaggle, ICAR/data.gov.in-style
sources — see `decisions/0016-regional-crop-suitability.md`'s
"Investigation" section for the exact queries and what was found and
rejected) turned up no usable India/Karnataka-specific dataset with
both a matching N/P/K/temp/humidity/pH/rainfall feature schema and
real overlap with the 22-crop label set — every Kaggle "crop
recommendation" hit was a re-upload of the same generic dataset already
in use, and the genuinely Karnataka-specific datasets found are
district/season yield-area statistics, a different schema entirely, not
retrainable into the existing model without building a new pipeline
from scratch (out of scope). This was the module's honestly-expected
outcome, so **Option B (regional-suitability sanity layer)** was built
instead of forcing a retrain: `src/agro_mirai/models/regional_suitability.py`
holds `BELLARY_REGIONAL_CROPS`, a small set (`cotton`, `rice`, `maize`,
`chickpea`, `pigeonpeas`) intersecting the 22-crop enum against three
independently cross-checked, cited sources on what's actually grown in
Bellary/Ballari district (ICAR-CRIDA's official district Agriculture
Contingency Plan, Wikipedia's "Ballari district" citing Karnataka
government statistics, and AgriFarming.in's district-wise Karnataka crop
list — full URLs in the ADR). `CropRecommendationModel.predict` now
calls `check_regional_fit` after ranking predictions; when the top pick
falls outside that set it does **not** override the ML output — it adds
two new additive `CropRecommendation` fields, `out_of_region: bool` and
`regional_alternative: str | None` (the highest-confidence in-region
crop from `alternatives`, or `None` if none of them are regional
either), documented in `specs/core/schema.yaml` and
`specs/core/openapi.yaml`. `ExplanationService.explain_crop` appends a
plain-language caveat sentence to `summary_en` when the flag is raised,
which `DecisionEngine.recommend` picks up automatically since
`Advisory.body` concatenates `summary_en` unmodified (ADR 0011) — both
real fixtures (`farm-001`'s cotton field predicts `grapes`, `farm-002`'s
maize field predicts `muskmelon`) are actually flagged `out_of_region`
today, confirming this isn't dead code but a genuinely load-bearing
honesty check on a model whose top-1 pick for both current fixtures is
already agronomically implausible for the region. `decisions/0016-regional-crop-suitability.md`
has the full investigation writeup, source list, and — importantly —
honest known limitations: most of Bellary's actual dominant crops
(jowar, groundnut, sunflower, millet, soybean) have no label at all in
the 22-crop enum so can never be surfaced as the "right" answer, the
table is hardcoded to one district (not yet field-location-aware for
Module 19's eventual multi-tenant/multi-region reality), and `maize`'s
inclusion in the regional set is weaker-evidenced than the other four.
25 new/updated tests: `tests/models/test_regional_suitability.py` (new,
unit coverage of `check_regional_fit`'s in-region/out-of-region/
no-alternative/empty-alternatives cases), extended
`tests/models/test_crop_recommendation_model.py` and
`tests/models/test_explanation_service.py` (caveat text present/absent/
no-alternative-available cases), and extended
`tests/models/test_crop_model_integration.py` /
`test_decision_engine_integration.py` (real fixtures, real artifact,
confirming the flag and caveat propagate end to end through
`DecisionEngine`). Module 20 (CNN disease model on PlantVillage) is next — see
`docs/ROADMAP_PRODUCTION.md` and `PROGRESS.md`'s Module 19 entry for the
full handoff. See
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

Module 19 (multi-tenant data model + real login/session auth +
read-only Admin dashboard) landed 2026-08-29 — the biggest single
module in this project, explicitly superseding ADR 0003
(`decisions/0017-multi-tenant-v2.md`). `Farmer`
(`src/agro_mirai/persistence/models.py`) gained three additive fields —
`email`, `password_hash`, `role` (new `user_role` enum: `farmer` |
`admin`, `specs/core/enums.md`) — implemented in both
`SQLiteDataStore` and `SupabaseDataStore`, with a hand-written
`migrations/{sqlite,postgres}/002_auth_fields.sql` migration path for
databases created before this module (verified directly against a
synthetic pre-Module-19 SQLite file, not just against a fresh one).
`DataStore` gained three new, deliberately unscoped admin-only read
methods (`list_all_farmers`, `list_all_fields`,
`list_all_feedback_with_advisories`) — the one documented exception to
`repository-interface.md`'s "every method takes a `farmer_id`" rule,
gated by role checks at the caller, never inside the store.

Auth is a real login/session system, not per-farmer API keys (Ritesh's
explicit call, understanding it's more work than the alternative): new
`agro_mirai.auth` package hashes passwords via **bcrypt**
(`auth/password.py`, an established KDF, not hand-rolled) and validates
registration input (`auth/validation.py` — real password-strength
requirements: 8+ chars, upper/lower/digit, rejects `"a"`). Sessions are
Flask's own signed cookie (no new session-store dependency — see ADR
0017 for why), issued/read via `src/agro_mirai/api/session_auth.py`'s
`issue_session`/`require_session_auth`/`require_admin`; expiry is
enforced both by the cookie's own `PERMANENT_SESSION_LIFETIME` (24h)
and a pure, unit-testable `is_expired(issued_at)` check on every
request. `POST /v2/auth/login` (`src/agro_mirai/api/routes/auth_v2.py`)
carries its own Flask-Limiter instance
(`src/agro_mirai/api/login_rate_limit.py`, default 5/min, keyed by
remote address) layered on top of Module 16's general per-key
`RATE_LIMIT` — it had to live in its own module and decorate the view
at import time, because this project's installed Flask-Limiter version
silently no-ops `.limit(...)` applied to an already-registered
`app.view_functions[...]` entry (discovered and fixed while writing the
rate-limit test, not assumed). `farmer_to_public_json`
(`api/serializers.py`) strips `password_hash` from every `Farmer`
response, applied everywhere a `Farmer` is serialized, including the
pre-existing `/v1 GET /farmers/me`.

The new `/v2` surface (`/v2/auth/*`, `/v2/farmers/me`, `/v2/fields*`,
`/v2/admin/*`) is additive alongside the unchanged `/v1` shared-`API_KEY`
routes — **`/v1` stays alive, unmodified, for demo/backward-compat
continuity, a deliberate decision documented in ADR 0017**, not an
accident; `MANUAL_TEST_GUIDE.md`/`docs/DEMO_SCRIPT.md` were updated to
say so explicitly rather than go stale. Cross-tenant isolation
(ADR 0003's ownership rule, now enforced per-farmer for real instead of
via the single-shared-identity shortcut) is proven by
`tests/api/test_v2_auth_integration.py`'s full register->login->
access-own-data->CANNOT-access-another-farmer's-field(404,
not-leaked)->logout->session-invalidated flow against a real Flask test
client and real `SQLiteDataStore` — no mocked auth.

The read-only Admin dashboard (list all farmers/fields, system-wide
feedback aggregates via Module 13's `FeedbackAggregator` reused
unmodified) ships as both a JSON API (`src/agro_mirai/api/routes/admin.py`,
`/v2/admin/{farmers,fields,feedback}`) and a server-rendered page
(`src/agro_mirai/api/routes/admin_ui.py`, `/admin`, same Jinja2/Flask
stack as the Module 14 frontend per ADR 0013, minimally styled and
labeled "functional, not yet polished" on the page itself). Genuinely
no write route exists anywhere on this surface —
`tests/api/test_admin_routes.py` asserts this directly by inspecting
`app.url_map` rather than trusting the blueprint's docstring. There is
no self-service admin-signup endpoint; provisioning an admin account is
an out-of-band step (register normally, then flip `role` via the
`DataStore` directly), documented in `MANUAL_TEST_GUIDE.md`'s new step 8
and in ADR 0017's known limitations.

61 new tests across `tests/auth/` (password hashing/verification/
salting, registration validation, session issuance/expiry — all pure-
function, no Flask context needed for the expiry check) and
`tests/api/` (`test_v2_auth_integration.py`,
`test_admin_routes.py`, `test_admin_ui.py`, `test_login_rate_limit.py`).
Full regression (`pytest --ignore=tests/voice`): 284 passed, 0 failed,
25 skipped. `check_specs.py`: OK. `tools/seed_fixture.py` and the
existing farm-001/farm-002 golden fixtures verified unaffected.

Module 20 (CNN disease model on PlantVillage) landed 2026-08-30.
`ImageDiseaseRiskModel.predict(image, field_id) -> DiseaseRiskAlert`
(`src/agro_mirai/models/image_disease_risk_model.py`) is the additive
CNN upgrade path ADR 0009 sketched out: a MobileNetV2 (torchvision,
ImageNet-pretrained, last 3 feature blocks fine-tuned) trained on Kaggle
`abdallahalidev/plantvillage-dataset`'s `color/` split (38 classes,
~54k images) — best held-out val accuracy 0.9924
(`docs/eval/disease_cnn_eval.json`). Training ran on a live Google Colab
T4 GPU session, driven entirely through the `colab` CLI (installed and
authenticated inside WSL — the CLI's own `termios` import makes it
Windows-incompatible outside WSL/Linux) rather than the notebook UI:
`colab new`/`colab exec`/`colab download` end to end, no manual
notebook interaction. `tools/train_disease_cnn.py` documents the exact
reproduction steps; it is not runnable locally (Colab `/content/...`
paths, and torch/torchvision are deliberately excluded from the main
venv, same policy as Module 12's voice stack — decisions/0014). Trained
artifacts (`models/disease_cnn_mobilenetv2.pt`,
`models/disease_cnn_class_names.json`) are gitignored, same convention
as `crop_rf.joblib`/`irrigation_rf.joblib`.

Two honest, documented gaps, not hidden behind the accuracy number (full
writeup in `decisions/0018-disease-cnn.md`): only 4 of PlantVillage's 38
classes' crops (apple, corn/maize, grape, orange) are in AGRO MIRAI's
22-value `crop_type` enum — the other 34 (pepper, potato, tomato,
etc.) are real trained classes with no `crop_type` label anywhere else
in this codebase; and the 99.24% validation accuracy is against a
random hold-out from PlantVillage's own lab-condition images, not real
field photos, which published research suggests generalizes
substantially worse. `src/agro_mirai/models/disease_cnn_labels.py`
holds the class-name parsing, the crop-enum overlap check, and the
risk-level heuristic (no per-disease severity ground truth exists, so
healthy -> `low`, any disease call floors at `moderate` and scales to
`high`/`severe` off the model's own softmax confidence — a
classification-certainty signal, not a severity signal, documented as
such). `disease_risk_scoring.py`'s `RISK_ACTION`/`RISK_WINDOW_DAYS`
lookups were exported as public aliases so both the rule-based and CNN
paths share one risk-level -> action/window mapping.

**Not yet wired into `DecisionEngine` or the API** — no `Field`/API
contract anywhere in this codebase carries an image upload today (the
same gap ADR 0009 identified as the real blocker, not the model itself);
adding an upload endpoint/storage and the `DecisionEngine`-side
image-vs-environmental choice is real follow-on scope, deliberately left
for later rather than forced in here. `tests/vision/` (new, mirrors
`tests/voice/`'s exclusion — both run separately under `.venv/`, both
excluded from the default `pytest`/CI run) has 2 tests: a missing-weights
`FileNotFoundError` check and a real end-to-end prediction against the
trained artifact confirming a schema-valid `DiseaseRiskAlert`. Full main
suite unaffected: 294 passed, 0 failed, 25 skipped.

Module 21 (Deployment architecture) landed 2026-09-01 — closes Module
20's real gap (no image-upload path anywhere) and answers where the
project's heavy inference (CNN + AI4Bharat voice) actually runs in
production, without touching any real Oracle infra (blocked on Ritesh
creating an Oracle account, entering payment card details, per this
module's explicit scope note). Two new standalone Flask services live
under `services/`, each with its own `Dockerfile`/`requirements.txt`/
`README.md`, deliberately separate processes from the main
`agro_mirai` app because torch/torchvision stay out of the main
`requirements.txt` (same isolation policy as the Module 12 voice
stack, `decisions/0014`): `services/cnn-inference` wraps Module 20's
`ImageDiseaseRiskModel` (`POST /predict`, `GET /health`, lazy model
load so health responds before weights are mounted); `services/voice`
wraps Module 12's `AI4BharatVoiceService` (`POST /translate`,
`/speech-to-text`, `/text-to-speech`, `GET /health`). Both Dockerfiles
pin CPU-only torch wheels and explicitly flag an unverified ARM64/
aarch64 wheel-availability risk for Oracle's Ampere A1 target — a real
open question, not silently assumed to work.

`POST /fields/{field_id}/disease-risk/image`
(`src/agro_mirai/api/routes/disease_image.py`, additive path in
`specs/core/openapi.yaml`) closes ADR 0018's "additive, not integrated
yet" gap: real upload validation (10MB cap + Pillow
`Image.verify()` content-sniffing, not filename/Content-Type trust —
`src/agro_mirai/api/image_validation.py`), then calls
`services/cnn-inference` over HTTP via a configurable `CNN_SERVICE_URL`
+ timeout (`src/agro_mirai/api/cnn_client.py`, using `requests` like
the Module 03 acquisition adapters). Per Ritesh's hard fallback
requirement, any CNN-service failure (unreachable, timeout, error)
falls back to the existing rule-based `DiseaseRiskModel` and still
returns a valid 200 `DiseaseRiskAlert` — never a 500. The choice logic
lives in exactly one place,
`src/agro_mirai/models/image_or_environmental_disease.py`, shared by
both this route and `DecisionEngine.recommend`'s new optional
`image_bytes` parameter (non-breaking — existing callers without an
image see identical behavior to before). `DiseaseRiskAlert` gained an
additive `source` field (`"cnn"` | `"environmental"` |
`"environmental_fallback"`, new `disease_alert_source` enum in
`specs/core/enums.md`) so a response records which path actually
produced it; `migrations/{sqlite,postgres}/003_disease_alert_source.sql`
is the upgrade path for pre-Module-21 databases, same ADD-COLUMN-
tolerant pattern Module 19's `002_auth_fields.sql` established.

The voice-stack question (keep AI4Bharat vs. switch to faster-whisper +
Kokoro) was resolved with a real web search, not assumed: Kokoro TTS
does not support Kannada (8 languages in its set, none of them `kn`) —
a hard blocker given `specs/core/voice-interface.md`'s
`V1_LANGUAGES = {en, kn}` — and faster-whisper adds nothing for this
project's actual ASR gap (it has the same language coverage as the
`whisper-tiny.en` Module 12 already uses for English; Kannada ASR
already comes from IndicConformer, which faster-whisper doesn't
replace). Decision: kept AI4Bharat, and solved the real problem a
lighter stack would have solved anyway — the `transformers==4.49.0`
`.venv/` isolation workaround from Module 15 — by containerizing it
instead (`services/voice`), a genuine production improvement over a
local dev workaround. `src/agro_mirai/voice/remote_voice.py`'s new
`RemoteVoiceService` implements the existing `VoiceService` Protocol by
calling this container, a third adapter alongside
`AI4BharatVoiceService`/`BhashiniVoiceAdapter` requiring zero caller
changes to swap in.

`docker-compose.yml` runs both services on one Oracle Ampere A1 VM with
explicit `mem_limit`/`cpus` and a worked resource budget in its own
comment block, grounded in a web-search-verified fact that matters:
Oracle silently cut the Always Free A1 allocation from 4 OCPU/24GB to
**2 OCPU/12GB** effective June 2026 — the budget targets that smaller
number, not the old one, and honestly flags itself as an estimate, not
a `docker stats` measurement, since no VM exists yet to measure against.
`docs/deploy/oracle-vm-setup.md` is the full runbook Ritesh follows
himself once his Oracle account exists — provisioning, a security list
that opens only the two service ports (not a blanket rule), Docker/
Compose install for Ubuntu ARM64, a recommended swap file given the
tight memory budget, and an explicit "verified vs. needs Ritesh to
confirm" closing section rather than blurring the two.
`decisions/0019-deployment-architecture.md` has the full reasoning for
all of the above plus honest limitations: Oracle's free tier could
shrink again, no autoscaling, a single Oracle VM is a real SPOF for the
CNN/voice paths specifically — but the core API, crop/irrigation
recommendations, the rule-based disease path, and all `/v1`/`/v2`
auth/admin routes have zero dependency on that VM and keep working
independently on Render/Supabase if it's ever down, a deliberate split
rather than an accident. The two Oracle-hosted services currently have
no authentication of their own — flagged as a real, not-yet-closed gap,
not hidden.

27 new tests: 7 in `services/cnn-inference/tests` and 7 in
`services/voice/tests` (both stub-model route tests, no torch needed,
run as their own CI steps), 6 in `tests/voice_remote/test_remote_voice.py`
(HTTP boundary mocked, runs in the main suite), and 7 in
`tests/api/test_disease_image_route.py` (upload validation, the CNN-
success path, and the CNN-unreachable-falls-back-to-200-not-500 path,
all with the CNN HTTP call mocked). Full main regression
(`pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice`):
301 passed, 25 skipped, plus 4 pre-existing failures confirmed
unrelated to this module (reproduce identically on a clean stash of
this module's diff — an existing ET0 water-balance seed-data gap in
`tests/api/test_integration.py`/`tests/frontend/test_frontend_integration.py`,
untouched by Module 21). `check_specs.py`: OK. Nothing in this module
required live Oracle infra, a live CNN service, or a live voice service
to pass — every HTTP boundary is mocked, verified by grepping for any
outbound call to a non-localhost, non-mocked host in the new test
files (none found).

Module 22 (bug fix: advisory endpoints 500ing on stale fixture weather)
landed 2026-09-04, closing the "4 pre-existing failures ... an existing
ET0 water-balance seed-data gap" Module 21 flagged above as unrelated
and deferred. Found by a real live-server repro, not a test run:
`GET /fields/{id}/advisories` against a correctly-seeded `farm-001`
500'd. Root cause, traced through the live traceback:
`feature_builder.py`'s weather-window aggregates are computed relative
to the real current date (`api/features.py`'s `as_of` default), but
`specs/domains/fixtures/farm-001.json`'s weather readings carry fixed
calendar dates (2026-08-18 to 24) — as real time moved past that
window, `temp_c_mean_7d` correctly (per its own documented "skip and
return None" policy) came back `None`, but
`irrigation_prediction_model.py`'s `_water_balance` (Module 17) raised
an uncaught `ValueError` on that `None` instead of degrading, and
nothing at the route boundary caught it. Two independent fixes, not
one: (1) `_water_balance` now falls back `temp_c_mean_7d` ->
`temp_c_mean_14d` -> `temp_c_mean_30d` before raising — degrade-not-
fail, the same philosophy already used for the tmin/tmax diurnal-range
fallback in the same function and for GEE/CNN elsewhere in this
project — and `advisory.py`'s three affected routes
(`/irrigation`, `/disease-risk`, `/advisories`) now wrap their
`predict`/`recommend` calls in a `_predict_or_422` helper, turning any
remaining genuine-data-exhaustion `ValueError` into a handled 422
(`INSUFFICIENT_DATA`) instead of a bare 500; (2) `tools/seed_fixture.py`
now shifts every timestamp in a loaded fixture by an anchor computed
from that fixture's own latest weather reading landing on today
(`_fixture_time_shift`), so `farm-001`/`farm-002` never age out of the
7-day window again, on this run or any future one — done by shadowing
`_pdt`/`_pdate` inside `load_fixture` rather than editing the fixture
JSON's absolute dates, so the fixture stays human-readable and every
other timestamp's relative offset (soil sample ~2 months before the
weather week, NDVI reading mid-week, advisories same-day) stays intact.

7 new/updated tests: `tests/models/test_irrigation_prediction_model.py`
gained two unit tests (7d->14d fallback succeeds; every window `None`
still raises, so the route-level 422 has something real to catch) and
`tests/api/test_integration.py` gained four (`/irrigation` and
`/disease-risk` end-to-end alongside the existing `/advisories` and
`/recommendation` coverage, a `test_advisories_endpoint_live_against_real_current_date`
regression test that exercises the exact live-repro path — real
current date, no frozen `as_of` — and a 422-not-500 test that forces
every temperature window empty via a monkeypatched `FeatureBuilder.build`
rather than fragile date arithmetic). Full main regression
(`pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice`):
312 passed, 25 skipped, 0 failed — the 4 pre-existing failures are
gone. `check_specs.py`: OK. Verified live, not just in pytest: a fresh
`tools/seed_fixture.py` seed plus a real `create_app()` + Flask
`test_client()` call (the same code path `app.run()` uses) against
today's real date returns 200 on `/recommendation`, `/irrigation`,
`/disease-risk`, and `/advisories` — the exact repro that originally
found this bug.

Module 23 (`/v2` value endpoints + a client-facing voice API — the last
backend module before the frontend phase) landed 2026-09-04, closing two
blockers confirmed by inspecting the actual route registrations before
any React Native/Antigravity work started, not taken on trust from the
module brief. **Blocker A**: `/v2` (Module 19's session-authenticated
surface) had real per-farmer auth but no product — every endpoint
carrying actual value (recommendation/irrigation/disease-risk/
disease-risk-image/advisories/feedback) existed only under `/v1`'s
single shared `FARMER_ID`, so a farmer registered via `/v2` had no
authenticated path to their own advisory. Not a Module 19 defect (`/v1`
staying alive was deliberate, ADR 0017) — an unnoticed gap between
modules, invisible to `test_full_cross_tenant_isolation_flow` because
that test only ever exercised `/v2/fields`. **Blocker B**: `grep -rn
"voice\|tts\|speech" src/agro_mirai/api/` returned nothing — the voice
stack (Module 12, containerized in Module 21) had no client-facing HTTP
route at all, making the decided mobile design (pre-cached TTS audio +
Android on-device TTS fallback) unbuildable with nothing to cache from.

Part A: the six `/v1` handler bodies
(`src/agro_mirai/api/routes/advisory.py`/`feedback.py`/
`disease_image.py`) moved into
`src/agro_mirai/api/value_endpoints.py` — auth-agnostic functions taking
an explicit `farmer_id` — so `/v1` (`@require_auth`) and the new
`routes/value_v2.py` (`/v2`, `@require_session_auth`) are both thin
wrappers around the same code, never duplicated, closing off the exact
drift risk that made Module 22's bug possible in the first place;
Module 22's degrade-not-fail contracts (422 on data-exhaustion,
`environmental_fallback` on an unreachable CNN service) now live in
`value_endpoints.py` itself, verified intact on both surfaces in
`tests/api/test_v2_value_endpoints.py`. Ownership reuses the store's
existing farmer-scoped `get_field`/`get_advisory` (Module 19), so every
new route gets 404-not-403-not-leaked cross-tenant isolation for free —
tested individually per endpoint (`test_v2_value_endpoints.py`), the
specific blind spot Blocker A exposed. `PATCH /v2/fields/{field_id}`
(A5, `routes/farms_v2.py`) was added in this module rather than deferred
— a partial update, `/v2`-only, since `/v1` stays frozen per ADR 0017.

Part B: `src/agro_mirai/api/voice_client.py` (mirrors `cnn_client.py`'s
never-raise contract over `RemoteVoiceService`) backs two new `/v2`
routes (`src/agro_mirai/api/routes/voice_v2.py`) — `GET
/v2/advisories/{advisory_id}/audio` (per-advisory, not generic TTS: a
stable, ETag-cacheable URL that matches the decided pre-cache design;
translates via the voice service first when `?language=` differs from
the advisory's own language) and `POST /v2/stt`
(`agro_mirai/api/stt_validation.py` does real magic-byte content
sniffing on the upload, mirroring — with a documented, smaller-scope
gap than — `image_validation.py`'s full Pillow decode-verify). Both
return a specific 503 `VOICE_UNAVAILABLE` on any voice-service failure —
never a 500, never a silent empty body — so the mobile client can
reliably fall back to on-device TTS/STT; both have their own
Flask-Limiter instance (`voice_rate_limit.py`, same "decorate at
blueprint-import-time" pattern `login_rate_limit.py` established in
Module 19) since these calls are far more expensive than a JSON read.
`services/voice/app.py`'s `/text-to-speech` now transcodes Piper's
native WAV to OGG/Vorbis via a real `ffmpeg` subprocess call (chosen
over MP3 — no extra codec install needed for `libvorbis`), with `ffmpeg`
added to that container's own Dockerfile — the main API process still
never imports AI4Bharat/torch (ADR 0019 unchanged). This transcode step
is unverified locally in this session (the Windows dev machine has no
system `ffmpeg`) but is expected to pass in CI, which already runs
`services/voice/tests` on `ubuntu-latest` (ships `ffmpeg` preinstalled)
— an honest, documented gap, the same class Module 21 already flagged
for its own Dockerfiles' ARM64 risk, not a silently-assumed pass.

`specs/core/openapi.yaml` gained 9 new paths and is treated as the
frozen frontend contract from this commit forward, the same way ADR
0017 froze `/v1`. `decisions/0020-v2-value-endpoints-and-voice-api.md`
has the full reasoning for every decision above. 46 new/updated tests
across `tests/api/test_v2_value_endpoints.py` (19 — per-endpoint
cross-tenant isolation, session-required 401s, success paths, Module 22
behavior preserved), `tests/api/test_field_update.py` (7),
`tests/api/test_voice_routes.py` (16), and
`tests/api/test_voice_rate_limit.py` (4); `services/voice/tests` gained
a real-ffmpeg-transcode assertion and an ffmpeg-missing-returns-422
case. Full main regression
(`pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice`):
358 passed, 25 skipped, 0 failed (up from 312 — no regressions);
`services/cnn-inference/tests`: 7 passed;
`services/voice/tests`: 7 passed, 1 failed locally (the ffmpeg-dependent
transcode test, expected — see above). `check_specs.py`: OK. Live
curl-verified end to end against a real seeded SQLite DB and a real
`create_app()` server (not just pytest): register two farmers -> login A
-> real 200 recommendation/irrigation/advisories with genuine content ->
farmer B gets 404 (not leaked) on A's field advisories *and* A's advisory
audio -> A's own audio request correctly 503s (no local voice service
running) -> logout -> session genuinely dead (401) on the next request.
Next: frontend phase — PRD, then Antigravity (React Native + Expo).
