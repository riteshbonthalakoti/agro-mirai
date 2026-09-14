# MODULE 02 — Data Contracts & Conventions

You are continuing the AGRO MIRAI build in the existing `agro-mirai` repo
(GitHub: riteshbonthalakoti/agro-mirai). Module 01 is done and committed —
read `CLAUDE.md` and `PROGRESS.md` first, they are your only required
context. Do not re-derive project history from anything else.

This module produces zero application code. It produces the contracts every
later module is required to build against — per `CLAUDE.md` rule 2
(additive-only data contracts) and rule 3 (repository interface, no module
talks to a DB engine directly).

## Housekeeping first (from Module 01's verification)
1. Add a `.gitattributes` with `* text=auto eol=lf` so line-ending diffs
   stop appearing across OS/editor combinations. Re-save `PROGRESS.md` under
   it and commit — this should be the only content of that commit.
2. Confirm the two PDFs (`AGRO_MIRAI2.1.pdf`, `week schedule.pdf`) and
   `module-01-prompt.md` are deliberately untracked reference material, not
   an oversight. If you agree they're reference-only, leave them untracked
   (don't add) but note the decision in this module's handoff so it's not
   re-flagged next time.

## Tasks

### 1. `docs/conventions.md` — write before anything else in this module
The boring platform-wide rules that get expensive to change once code
depends on them:
- ID format (e.g. UUIDv4 for all entity IDs; document why).
- Timestamp rules (UTC, ISO 8601, field naming e.g. `created_at`).
- Error envelope shape — one consistent JSON error shape every endpoint
  returns, decided now.
- Ownership/tenancy model — this is a single-farmer-account-per-user model
  for this project (not multi-tenant SaaS); say so explicitly so no later
  module invents multi-tenancy nobody asked for.
- Units convention (metric throughout — mm for rainfall, °C, etc.) since
  the PPT and Open-Meteo both default metric.

### 2. `specs/core/schema.md` (or `.yaml`, your call — pick one and be
consistent) — the core entities
Define, with fields and types, at minimum: `Farmer`, `Field`,
`WeatherReading`, `SoilSample`, `NDVIReading`, `CropRecommendation`,
`IrrigationAdvice`, `DiseaseRiskAlert`, `Advisory`, `FeedbackEntry`. These
map directly to the class diagram in the original PPT (`AGRO_MIRAI2.1.pdf`,
slide 23) — reuse those names, don't invent parallel ones.

### 3. `specs/core/enums.md` — closed vocabularies
Crop types (from the Kaggle crop-recommendation dataset's label set), soil
types, risk levels (e.g. low/moderate/high, matching the PPT's disease-risk
mockup), supported language codes (ISO 639-1, starting with `en` + whichever
Indian languages the AI4Bharat stack covers first), season labels.

### 4. `specs/core/openapi.yaml` — the API contract skeleton
Stub every endpoint the 15-module plan will eventually need (crop
recommendation, irrigation advice, disease risk, feedback submission,
field/farmer CRUD) with request/response shapes referencing the schema from
step 2. No implementation yet — this is what Module 11 (API layer) builds
against, and what the frontend (Module 14) can start typing against even
before the backend exists.

### 5. Repository interface contract — `specs/core/repository-interface.md`
Written spec (not yet an implementation — that's Module 04) for the
`DataStore` abstraction every module must go through: methods like
`save_field`, `get_field`, `save_reading`, `list_advisories_for_field`,
etc. This is the seam that makes the SQLite-dev/Supabase-prod swap (locked
decision #3) actually work — be concrete about method signatures now so
Module 04 isn't guessing.

### 6. Golden fixture — `specs/domains/fixtures/farm-001.json`
One coherent story: a single real-shaped farm, one farmer, one field, a
week of weather readings, one soil sample, one NDVI reading, a crop
recommendation, an irrigation advisory, and one feedback entry — all
cross-referencing the same IDs. Every later module's tests should be able
to load this fixture and exercise their logic against it, so make it
complete enough to actually be useful, not a token stub.

### 7. `tools/check_specs.py` — the enforcement script, thin but real
Start with exactly three checks, per the doctrine's "generated/enforced,
never just agreed" rule:
1. The golden fixture parses and validates against the schema from step 2.
2. Every enum value used anywhere in the fixture or OpenAPI spec is
   documented in `enums.md`.
3. Every `$ref` in `openapi.yaml` resolves to something that actually
   exists in the schema.
Exit non-zero on any failure. Wire it into the Module 02 test suite (a
passing pytest test that shells out to it, or a native Python check —
your call), and write ONE deliberately broken fixture in a test-only
location to prove check_specs.py actually catches a violation, not just
passes by default.

### 8. Update doctrine files
- `CLAUDE.md`: current phase → Module 02 complete, Module 03 next; add a
  short "Contract layer" pointer under the repo map.
- `decisions/0001-index.md`: add an entry (and a full ADR file if the
  choice is non-obvious) for the ID format and the ownership/tenancy call
  from step 1 — these are the kind of decisions that get re-litigated later
  if not written down now.
- Run `python tools/update_state.py`, review the regenerated state block,
  commit.

## Definition of done
- [ ] `.gitattributes` committed, no more line-ending noise
- [ ] `docs/conventions.md`, `specs/core/schema.md`, `specs/core/enums.md`,
      `specs/core/openapi.yaml`, `specs/core/repository-interface.md` all
      exist and are internally consistent with each other
- [ ] Golden fixture exists and validates
- [ ] `tools/check_specs.py` runs clean on the real fixture and correctly
      fails on the deliberately broken one (test proves this, don't just
      assert it in prose)
- [ ] `CLAUDE.md` and `PROGRESS.md` updated, decisions logged
- [ ] Clean commit(s), pushed to `origin/main`

## Handoff format
Same as Module 01's:
```
Module: 02 — Data Contracts & Conventions
Status: complete | blocked (say on what)
Implemented:
Files changed:
Tests created: <+pass/fail>
Known limitations:
Remaining risks:
Next recommended module: 03 — Data Acquisition (weather, GEE+cache, soil)
```
