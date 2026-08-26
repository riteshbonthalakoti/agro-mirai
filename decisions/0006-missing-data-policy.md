# ADR 0006 — Missing-data policy for feature extraction

**Status:** accepted
**Date:** 2026-08-26
**Module:** 05 — Processing & Feature Engineering

## Context

`FeatureBuilder` (`src/agro_mirai/processing/feature_builder.py`) turns
raw `WeatherReading`/`SoilSample`/`NDVIReading` history into a
`FeatureVector` consumed by Modules 06-08. In practice, not every
`Field` has every kind of data at every point in time: a farmer may
never have entered a lab soil report, and NDVI depends on GEE
availability + cloud cover per CLAUDE.md hard rule #4 — a field can go
weeks without a usable satellite pass. Weather, by contrast, is
asserted always-available by Module 03's acquisition design (it falls
back through Open-Meteo → cache, never comes back empty for an active
field).

Two bad defaults were considered and rejected up front:

- **Silently defaulting a missing value to `0.0`.** Wrong for NDVI in
  particular — `0.0` is a real, meaningful NDVI reading (bare
  soil/no vegetation), not an absence marker. Using it as a stand-in for
  "we don't know" would make a field with no satellite coverage
  indistinguishable from a field that is genuinely bare, which is a
  silent correctness bug waiting for Module 08 (disease risk) to trip
  over.
- **Emitting a mostly-`None` vector for a field with zero weather
  history.** Weather is the one input Module 03 guarantees; a field
  with literally no weather readings indicates an upstream acquisition
  failure, not a normal missing-data case, so `FeatureBuilder` should
  fail loudly rather than hand Module 06 a vector that looks valid but
  isn't.

## Decision

1. **Weather is required.** If a `Field` has zero `WeatherReading`
   records (relative to the `as_of` anchor), `FeatureBuilder.build()`
   raises `ValueError`. No feature vector is emitted.
2. **Soil and NDVI are optional, all-or-nothing per source.** Each gets
   its own `*_data_available: bool` flag on `FeatureVector`
   (`soil_data_available`, `ndvi_data_available`). When the source has
   zero records, every derived feature from that source is `None` — not
   `0.0`, not omitted from the dataclass.
3. **`ndvi_confidence_source` (gee_live/cache/manual) is passed through
   unweighted.** Module 05 does not discount `ndvi_latest`/`ndvi_trend`
   based on source reliability; that judgment is deferred to Modules
   06-08, which have the domain context (e.g. how much a crop
   recommendation should trust a stale cache reading) that feature
   extraction does not.
4. **`season`/`days_since_sowing` follow `Field_.sown_on`'s own
   optionality directly** — no separate availability flag, since
   `sown_on` is already optional in `schema.yaml`.

Full per-feature detail lives in `specs/core/features.md`, which this
ADR backs.

## Consequences

- Downstream modules (06-08) must branch on the `*_data_available`
  flags rather than assuming every feature is populated — this is a
  contract, not a suggestion, and should be covered by their own tests.
- A field with only weather data still produces a usable (if sparser)
  feature vector — degrade, don't fail, for anything Module 03 doesn't
  guarantee.
- A regression that makes weather "usually available" (matching NDVI's
  optional treatment) is a breaking change to this ADR's contract and
  needs a superseding ADR, not a silent code change.
- `specs/domains/fixtures/farm-002.json` exists specifically to exercise
  the missing-NDVI path against real fixture data, alongside farm-001's
  full-data case.
