# ADR Index

One entry per architectural decision record.

- `0002-id-format.md` — Entity IDs are UUIDv4 strings.
- `0003-single-farmer-tenancy.md` — One `Farmer` per user account; no
  multi-tenant sharing in `v1`. **Superseded by 0017** for the new `/v2`
  surface; `/v1` itself is unchanged and still governed by this ADR.
- `0004-gee-timeout-and-fallback.md` — Earth Engine call timeout, cloud
  cover ceiling, lookback window, and buffer radius for the NDVI
  live/cache fallback.
- `0005-migration-generation.md` — SQLite/Postgres migrations are
  generated from `schema.yaml`, not hand-written.
- `0006-missing-data-policy.md` — Weather is required (hard error if
  absent); soil and NDVI are optional with explicit `*_data_available`
  flags and `None`-propagation, never a silent `0.0`.
- `0007-crop-model-feature-mapping.md` — Crop model trains on the Kaggle
  dataset's native 7 columns; `FeatureVector` → model-input mapping is a
  documented prediction-time transform, not a training-data reshape.
- `0008-irrigation-model-feature-mapping.md` — Irrigation `urgency` is a
  trained classifier on a 3-class Kaggle label; `recommended_depth_mm`
  and the advisory window are a documented rule-based lookup, not
  fabricated regression targets.
- `0009-disease-risk-model.md` — Disease risk is a documented threshold
  scoring system over humidity/rainfall/temperature/NDVI-trend, not a
  trained classifier or image CNN; the CNN upgrade path is additive
  behind the same `DiseaseRiskAlert` shape.
- `0010-explainability.md` — SHAP (`shap.TreeExplainer`) explains Modules
  06/07's trained RandomForest classifiers; Module 08's rule-based score
  gets direct weight×signal attribution, explicitly labeled
  `rule_weight`, never presented as SHAP.
- `0011-decision-engine.md` — `DecisionEngine` always calls all three
  models and surfaces their outputs unmodified in `Advisory.body` rather
  than synthesizing across them; `Advisory.severity` (max of irrigation
  urgency / disease risk_level) doubles as the immediate-action alert
  signal, no new schema field added.
- `0013-frontend-platform-sequencing.md` — Platform build order is web
  now, mobile next, WhatsApp/messaging after; Module 14's web frontend
  is server-rendered Flask templates in the same process as Module 11's
  API (not a separate SPA service), calling the JSON API in-process with
  a server-held `API_KEY` rather than exposing it client-side.
- `0015-et0-water-balance.md` — `recommended_depth_mm` is now derived
  from an ET0 (Hargreaves-Samani) x Kc (FAO-56 Table 12) water balance
  against 7-day rainfall, replacing ADR 0008's fixed urgency-keyed depth
  lookup (which it partially supersedes); `urgency` still gates the
  advisory window length.
- `0016-regional-crop-suitability.md` — No usable India/Karnataka-specific
  crop-recommendation dataset was found, so `CropRecommendationModel` is
  not retrained; a small, cited Bellary/Karnataka regional-suitability
  table flags (never overrides) a top prediction outside the known
  regionally-grown crop set via two new additive `CropRecommendation`
  fields, `out_of_region`/`regional_alternative`.
- `0017-multi-tenant-v2.md` — Supersedes 0003 for the new `/v2` surface:
  real multi-farmer accounts (`Farmer.role`, not a separate `AdminUser`),
  bcrypt-hashed passwords, Flask signed-session login (not JWT/OAuth), a
  read-only Admin dashboard. `/v1` stays alive unmodified for demo/
  backward-compat, a deliberate decision, not an accident.
- `0018-disease-cnn.md` — MobileNetV2 transfer-learned on PlantVillage
  (`color/` split, 38 classes) via `ImageDiseaseRiskModel`, additive
  alongside ADR 0009's rule-based `DiseaseRiskModel` behind the same
  `DiseaseRiskAlert` shape. Only 4 of 38 PlantVillage crops are in the
  22-value `crop_type` enum; not yet wired into `DecisionEngine` since no
  image-upload path exists anywhere in the API/schema yet.
- `0019-deployment-architecture.md` — Render keeps the main API; a
  single Oracle Ampere A1 VM (2 OCPU/12GB, the shrunken 2026 Always Free
  allocation) hosts two new standalone containers,
  `services/cnn-inference` and `services/voice`, closing Module 20's CNN
  wiring gap with a hard fallback-to-rule-based requirement on any CNN
  service failure. Voice stack decision: kept AI4Bharat over
  faster-whisper/Kokoro (Kokoro has no Kannada support), containerized
  instead of switched.
- `0020-v2-value-endpoints-and-voice-api.md` — Closes two blockers found
  before frontend work started: `/v2` had auth but no product
  (recommendation/irrigation/disease-risk/advisories/feedback existed
  only under `/v1`), and the voice stack had no client-facing API at all.
  Six `/v1` handlers moved into `value_endpoints.py`, shared by both auth
  surfaces rather than duplicated; `PATCH /v2/fields/{id}` added; a
  per-advisory `GET /v2/advisories/{id}/audio` (OGG, ETag-cached,
  transcoded in `services/voice` via ffmpeg) and `POST /v2/stt` added,
  both returning a distinguishable 503 `VOICE_UNAVAILABLE` — never a
  500 — so the mobile client can fall back to on-device TTS/STT.
- `0021-language-expansion-te-hi.md` — Widens `V1_LANGUAGES` from
  `{en, kn}` to `{en, kn, te, hi}` for the mobile app's new language
  picker options. Translation (IndicTrans2) and STT (IndicConformer)
  verified to already cover `te`/`hi` with no new downloads; TTS splits
  across two real backends per language (`kn`/`te` -> `vits_rasa_13`,
  `en`/`hi` -> Piper — `vits_rasa_13` has no Hindi voice, Piper has no
  Kannada/Telugu voice), with the Hindi Piper voice file a real,
  not-yet-downloaded step (documented command, not faked). Fixed a
  second hardcoded `{en, kn}` allowlist in `farms_v2.py` that had
  drifted from `V1_LANGUAGES`, and added registration-time
  `preferred_language` validation that never existed before.
- `0024-user-entered-content-i18n.md` — Fixed-enum fields
  (`current_crop`/`soil_type`) were already stored as stable
  language-independent keys; the real bug was the mobile app displaying
  the raw English key on every UI language, fixed with display-only
  label maps in `App.tsx`. Genuinely free-text fields (`Field.name`)
  are shown as the farmer entered them regardless of UI language,
  deliberately not auto-translated (a considered, reversible default,
  not an oversight).
