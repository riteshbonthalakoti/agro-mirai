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

ISO 639-1 two-letter codes. Bundled set tracks what the AI4Bharat stack
covers when Module 12 wires it up.

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
