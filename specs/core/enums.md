# Enums

Closed vocabularies referenced by `specs/core/schema.yaml` and
`specs/core/openapi.yaml`. Values are `snake_case`. Additions are
non-breaking; removals or renames require a new schema version and an ADR.

The enforcement script (`tools/check_specs.py`) requires that every enum
value used anywhere in the golden fixture or OpenAPI spec appears here.

## `crop_type`

Sourced from the Kaggle crop-recommendation dataset label set
(<https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset>).

- `rice`
- `maize`
- `chickpea`
- `kidneybeans`
- `pigeonpeas`
- `mothbeans`
- `mungbean`
- `blackgram`
- `lentil`
- `pomegranate`
- `banana`
- `mango`
- `grapes`
- `watermelon`
- `muskmelon`
- `apple`
- `orange`
- `papaya`
- `coconut`
- `cotton`
- `jute`
- `coffee`

## `soil_type`

Common Indian soil classes; kept coarse for v1.

- `alluvial`
- `black`
- `red`
- `laterite`
- `mountain`
- `desert`
- `saline`
- `peaty`
- `unknown`

## `risk_level`

Used for irrigation urgency, disease risk, and advisory severity — same
ladder everywhere so the UI can render it uniformly.

- `low`
- `moderate`
- `high`
- `severe`

## `language_code`

ISO 639-1 two-letter codes. Full set this project may eventually reach;
not all of these are voice-operational today. As of Module 25,
`V1_LANGUAGES` (`src/agro_mirai/voice/interface.py`) — the subset the
AI4Bharat voice stack (translation/STT/TTS) actually covers and that
registration/`preferred_language` validation enforces — is
`{en, kn, te, hi}`. `ta`/`mr`/`bn`/`gu` remain listed here as future
scope, not yet wired to any voice adapter.

- `en` — English
- `hi` — Hindi
- `kn` — Kannada
- `ta` — Tamil
- `te` — Telugu
- `mr` — Marathi
- `bn` — Bengali
- `gu` — Gujarati

## `season`

Indian agricultural seasons.

- `kharif` — monsoon-sown, autumn-harvested
- `rabi` — winter-sown, spring-harvested
- `zaid` — summer

## `weather_source`

- `open_meteo`
- `manual`
- `cache`

## `soil_source`

- `lab_report`
- `manual`
- `synthesised`
- `soilgrids` — ISRIC SoilGrids REST API point query (Module 03)

## `ndvi_source`

- `gee_live` — live Google Earth Engine query
- `cache` — local NDVI cache fallback (per CLAUDE.md hard rule #4)
- `manual`

## `user_role`

Module 19. Distinguishes a regular farmer account from an Admin account
on the same `Farmer` entity (see `decisions/0017-multi-tenant-v2.md` for
why a `role` field was chosen over a separate `AdminUser` entity).

- `farmer`
- `admin`

## `health_status`

- `ok` — data store reachable, service healthy
- `degraded` — data store ping failed; service is up but persistence is unavailable

## `disease_alert_source`

Module 21. Which path produced a given `DiseaseRiskAlert`.

- `cnn` — `ImageDiseaseRiskModel` via `POST /fields/{field_id}/disease-risk/image`
- `environmental` — the rule-based `DiseaseRiskModel`, called directly
- `environmental_fallback` — an image was submitted but the CNN inference
  service was unreachable/timed out/errored, so the rule-based model was
  used instead (the hard fallback requirement — never a 500)

## `field_data_acquisition_status`

Module 34 follow-up 2. Per-source status returned by `POST /v2/fields`
and `POST /v2/fields/{field_id}/refresh-data` describing whether each
Module 03 acquisition adapter's data is available for the field.

- `ready` — the adapter ran synchronously and its data was persisted
- `unavailable` — the adapter failed (degrade-not-fail); field creation
  still succeeded, this source's data simply isn't there yet
- `gathering` — NDVI only; fetched in a background thread (GEE latency
  measured close to its own 20s timeout), never known synchronously at
  response time

## `bug_report_category`

Mobile bug-report flow (`BugReport`, `POST /v2/bug-reports`). Preset
reason the farmer tapped in the app; `other` covers anything not listed.
A report is valid with only a category (no typed message) or only a
message (no category), but not neither.

- `crash` — "App crashed"
- `wrong_info` — "Wrong information shown"
- `unclear_advice` — "Couldn't understand the advice"
- `photo_scan_failed` — AI Scan-specific: the leaf photo scan failed or gave a nonsensical result
- `login_failed` — OTP/login couldn't be completed
- `other` — anything else, typically paired with a typed `message`
