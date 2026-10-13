# Testing Strategy

Referenced by every module prompt from Module 06 onward — this replaces
restating test expectations ad hoc in each prompt.

## The four layers every module's test suite must cover

1. **Unit** — pure logic, no I/O. Every function/class with a decision
   branch gets at least one test per branch, not just the happy path.
2. **Contract** — anything crossing a module boundary (a `DataStore` call,
   an adapter, a feature vector) gets validated against the relevant
   `specs/core/*` definition, reusing `check_specs.py`'s validation logic
   where applicable rather than duplicating it.
3. **Edge case** — explicitly enumerate what "wrong" input looks like for
   this module (missing data, out-of-range values, unknown foreign keys,
   empty collections, duplicate saves) and write a test for each one you
   can name. If a module works with external data (weather, soil, NDVI),
   this includes at least one deliberately-malformed-response test.
4. **Live/offline split** — anything hitting a real external service
   (API, DB, cloud auth) gets both a fully offline test against a recorded
   fixture (always runs, no network) and a live-gated test that
   auto-skips without credentials/network (never fails the suite for
   their absence). This is the pattern Module 03 and Module 04 already
   established — keep using it exactly as-is.

## What "done" testing looks like per module (add to every DoD checklist)

- [ ] All four layers above are represented, not just unit tests
- [ ] At least one test proves a failure mode is actually caught (a
      negative test), not just that the happy path works
- [ ] Full suite passes offline, with zero hangs and zero silent skips
      that should have been failures
- [ ] `check_specs.py` still passes if this module touches anything under
      `specs/`

## What this is not

Not a coverage-percentage target. A module with 40 tests that never
actually asserts a failure path is weaker than one with 10 tests that
does. Depth over count — the same principle behind not padding commits.
