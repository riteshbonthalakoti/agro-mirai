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

**Module 05 complete. Module 06 next.** The feature-engineering layer
(`src/agro_mirai/processing/feature_builder.py`) turns raw
`WeatherReading`/`SoilSample`/`NDVIReading` history plus a `Field_`
into a `FeatureVector`, per `specs/core/features.md`: rolling weather
aggregates (7/14/30-day rainfall sum, temp mean, humidity mean), soil
pass-through plus a derived NPK balance index, NDVI latest/trend/source,
and a season/days-since-sowing heuristic from `sown_on`. It is a pure
function — no `DataStore` calls, no network, no `datetime.now()`.
Weather is required (raises if absent); soil and NDVI are optional with
explicit `*_data_available` flags and `None`-propagation, documented and
enforced per ADR 0006. 15 tests in `tests/processing/` cover full data,
missing NDVI/soil, weather-only, and the zero-weather error, including
one loaded from a new second golden fixture,
`specs/domains/fixtures/farm-002.json` (weather + soil, no NDVI). Module
06 (Crop Recommendation Model) can start now. See `PROGRESS.md` for the
full 15-module plan and status.
