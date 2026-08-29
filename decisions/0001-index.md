# ADR Index

One entry per architectural decision record.

- `0002-id-format.md` — Entity IDs are UUIDv4 strings.
- `0003-single-farmer-tenancy.md` — One `Farmer` per user account; no
  multi-tenant sharing in `v1`.
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
