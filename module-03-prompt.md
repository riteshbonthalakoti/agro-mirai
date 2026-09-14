# MODULE 03 — Data Acquisition

Continuing the AGRO MIRAI build in the existing `agro-mirai` repo. Modules
01 and 02 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first —
that's your complete required context, don't re-derive project history from
anything else.

This module builds the three external data adapters — weather, soil,
satellite/NDVI — that everything from Module 05 onward consumes. Nothing
downstream should ever import a requests/API client directly; it goes
through what you build here.

## Scope

Three adapters, each returning objects that conform exactly to the
corresponding entity in `specs/core/schema.yaml` (field names, types,
units, timestamp format — per `docs/conventions.md`, not your own judgment):

1. **Weather** → `WeatherReading`. Source: Open-Meteo (no key required).
   Both current/forecast and historical archive endpoints, since Module 05+
   will want both.
2. **Soil** → `SoilSample`. Source: SoilGrids REST API (ISRIC, no key).
3. **NDVI** → `NDVIReading`. Source: Google Earth Engine (Sentinel-2),
   using the service account at the path in `EE_SERVICE_ACCOUNT_KEY` (see
   `docs/TOOLING.md` — the key itself stays outside the repo, already
   gitignored). **This is the one with a required fallback**: per
   `CLAUDE.md` hard rule #4, every NDVI read attempts the live GEE query
   first and falls back to a local NDVI cache on timeout, quota exhaustion,
   or any GEE exception — never a hard failure. Log which path served the
   result.

## Tasks

### 1. `docs/architecture.md` — fill in the real content
It's currently a placeholder. Add a short "Data Acquisition" section
describing the three adapters, the common interface they implement, and
the GEE live/cache fallback specifically (this is a locked decision, make
it visible in the architecture doc, not just in code).

### 2. Common adapter interface
Define one shared shape (e.g. an `Adapter` protocol/ABC in a new
`src/agro_mirai/acquisition/` package — pick your own module layout, but
be consistent) with a method per source that takes a `Field`-shaped input
(lat/long at minimum) and returns schema-conformant objects. All three
adapters implement it. This interface is what Module 05 depends on, not
the individual clients.

### 3. Weather adapter (`open_meteo.py` or similar)
- Current + short-range forecast call.
- Historical archive call (date range).
- Map response fields to `WeatherReading` exactly — units already metric
  in both conventions and Open-Meteo's defaults, don't add conversion bugs.
- Timeout + one retry on transient failure; a clear, typed exception (not
  a silent empty result) if it still fails.

### 4. Soil adapter (`soilgrids.py` or similar)
- Point query by lat/long, map to `SoilSample`.
- SoilGrids returns depth-interval data — document (in a code comment and
  in `docs/architecture.md`) which depth interval you're using as the
  representative sample and why (topsoil, matching what a farmer would
  actually test).

### 5. NDVI adapter with live+cache fallback (`earth_engine.py` or similar)
- Live path: authenticate via the service account (env var, never
  hardcoded — reuse the same pattern documented in `docs/TOOLING.md`),
  query Sentinel-2 NDVI for the field's location, most recent
  low-cloud-cover scene.
- Cache path: a local cache file (e.g.
  `specs/domains/fixtures/ndvi_cache.json`) keyed by field id or lat/long,
  seeded with at least one real precomputed value for the golden fixture
  farm (`farm-001`) — pull this once via a live GEE call and save it, don't
  fabricate a plausible-looking number.
- Fallback trigger: GEE exception, timeout (set an explicit timeout — don't
  rely on a default), or quota-exceeded response. On fallback, the returned
  `NDVIReading.source` field must say so (see `enums.md`'s `ndvi_source`
  values — add a `cached` value there if it's not already present).

### 6. Config
- `.env.example` listing every env var these adapters read (no real
  values), including `EE_SERVICE_ACCOUNT_KEY`.
- Confirm nothing secret is written anywhere under version control — check
  this explicitly as part of your own review before committing.

### 7. Tests — deterministic by default, live calls opt-in
- Unit tests for each adapter's response-to-schema mapping using **recorded
  sample responses** saved as test fixtures (so the suite doesn't need
  network access to pass reliably) — validate the mapped output against
  `schema.yaml` using the same validation logic `check_specs.py` already
  has (import and reuse it, don't duplicate it).
- One test that specifically forces the GEE fallback path (mock/monkeypatch
  the live call to raise) and asserts the cache value is returned with
  `source == cached`.
- A small number of tests marked to actually hit the live APIs (Open-Meteo,
  SoilGrids, and GEE), skipped automatically if network/credentials aren't
  available, so you get one real end-to-end confidence check without making
  the suite flaky for future sessions.
- Run `python tools/check_specs.py` afterward too — confirm this module
  didn't quietly introduce an enum or schema drift.

### 8. Update doctrine
- `modules/03-data-acquisition/STATUS`
- `CLAUDE.md` current phase → Module 03 complete, Module 04 next
- `decisions/`: add an ADR for the GEE timeout/fallback thresholds you
  chose (the specific numbers matter later if they need tuning)
- `python tools/update_state.py`, review, commit

## Definition of done
- [ ] All three adapters exist, implement the shared interface, and return
      only schema-valid objects (proven by tests, not just asserted)
- [ ] GEE fallback is real and tested — not just present in an if/else that
      never actually gets exercised
- [ ] No secrets anywhere in the diff (check before committing)
- [ ] Full test suite passes, including from-scratch on a machine with no
      network (the mocked/recorded tests must not silently depend on live
      access)
- [ ] `check_specs.py` still passes
- [ ] Doctrine updated, clean commit(s), pushed to `origin/main`

## Handoff format
```
Module: 03 — Data Acquisition
Status: complete | blocked (say on what)
Implemented:
Files changed:
Tests created: <+pass/fail, note how many require live network vs. fully offline>
Known limitations:
Remaining risks:
Next recommended module: 04 — Storage Layer (SQLite/Supabase, repository interface)
```
