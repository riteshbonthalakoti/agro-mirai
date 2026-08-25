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

## `ndvi_source`

- `gee_live` — live Google Earth Engine query
- `cache` — local NDVI cache fallback (per CLAUDE.md hard rule #4)
- `manual`
