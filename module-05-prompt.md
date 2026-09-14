# MODULE 05 — Processing & Feature Engineering

Continuing the AGRO MIRAI build in the existing `agro-mirai` repo. Modules
01–04 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first —
that's your complete required context.

This module turns raw `WeatherReading`/`SoilSample`/`NDVIReading` records
(from Module 03's adapters, persisted via Module 04's `DataStore`) into the
feature vectors Modules 06–08's models will train and predict against.
Get the feature contract wrong here and every model module inherits the
mistake — take the same care Module 02 took with the entity schema.

## Before any code
Confirm `git config user.name`/`user.email` still resolve correctly in
this repo (should already be set from Module 04 — just confirm, don't
re-set blindly). Same commit discipline as Module 04: one commit per real
checkpoint, not one giant commit, not padded.

## Tasks

### 1. `specs/core/features.md` — the feature contract, written before code
Same discipline as `docs/conventions.md` in Module 02: decide and document
before implementing. For each feature: name, source entity/entities it's
derived from, computation, units, valid range, and what happens when an
input is missing (this matters — a farmer might have soil data but no NDVI
reading yet; decide the default/imputation policy explicitly, don't let
each model module invent its own).

Minimum feature set, derived from what Modules 06–08 will need:
- Weather aggregates: rolling averages/sums over configurable windows
  (e.g. 7/14/30-day rainfall sum, mean temp, mean humidity) — Open-Meteo
  gives you both forecast and historical, use both where relevant.
- Soil features: pass-through with unit/range validation, plus derived
  ones if useful (e.g. N-P-K ratio).
- NDVI features: latest value, trend (change vs. previous reading), and
  a flag for whether the value came from `gee_live` or `cache` (Module
  06-08 may want to weight confidence differently — decide now whether
  that's in scope for v1 or explicitly deferred).
- Season/derived context: map `sown_on` + calendar date to a season label
  using the `season` enum from Module 02.

### 2. Feature pipeline implementation
A `FeatureBuilder` (or similar) that takes a `Field` + its associated
readings (fetched via the `DataStore` from Module 04) and returns a
feature vector matching `features.md` exactly. Keep it a pure function of
its inputs where possible — no hidden state, no silent network calls (all
data acquisition already happened in Module 03; this module only
transforms what's already persisted).

### 3. Missing-data handling — test this explicitly
Per the imputation policy from step 1, write tests for: a field with full
data, a field missing NDVI entirely, a field missing soil data entirely,
and a field with only the bare minimum (just weather). This is exactly the
kind of edge case that's cheap to handle correctly now and expensive to
patch after three model modules depend on the current behavior.

### 4. Golden fixture extension
Extend `farm-001.json` (or add a `farm-002.json` if that's cleaner — your
call, but document which and why) so there's a fixture that deliberately
has a gap (e.g. no NDVI reading yet), so the missing-data tests in step 3
have something real to run against, not just synthetic in-test data.

### 5. Update doctrine
- `modules/05-processing/STATUS`
- `CLAUDE.md` current phase → Module 05 complete, Module 06 next
- ADR for the imputation policy if it's non-obvious (it probably is —
  this is a real design decision, not a formality)
- `python tools/update_state.py`, `python tools/check_specs.py`, commit

## Definition of done
- [ ] `specs/core/features.md` exists and is what the code actually
      implements (not aspirational — if you deviate while building, update
      the doc, don't let them drift)
- [ ] `FeatureBuilder` (or equivalent) produces vectors matching the
      contract, proven by tests against both a complete and an
      incomplete fixture
- [ ] Missing-data policy is explicit, documented, and tested — not just
      "whatever the code happens to do"
- [ ] `check_specs.py` still passes
- [ ] Commit history shows real, distinct checkpoints
- [ ] Doctrine updated, pushed to `origin/main`

## Handoff format
```
Module: 05 — Processing & Feature Engineering
Status: complete | blocked (say on what)
Implemented:
Files changed:
Commits made: <list with one-line summary each>
Tests created: <+pass/fail>
Known limitations:
Remaining risks:
Next recommended module: 06 — Crop Recommendation Model
```
