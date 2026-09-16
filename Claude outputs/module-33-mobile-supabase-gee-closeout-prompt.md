# MODULE 33 — Close the three gaps Module 32 left open: mobile live testing, Supabase live round-trip, GEE-live path

Continuing AGRO MIRAI. Module 32 proved the backend is genuinely solid — every
`/v1`/`/v2`/admin endpoint live-tested with real request/response evidence,
413/0/26 main suite, cross-tenant isolation confirmed, the disease-image
degrade-not-fail path proven live. That module was explicit and honest about
what it did NOT reach in the time it had: mobile flows, a live Supabase
round-trip, forcing the real GEE path, and the separate-venv `tests/voice`/
`tests/vision`. This module closes exactly those four gaps — nothing else.
Do not re-do Module 32's backend/grep work; it's done and verified, build on
it, don't repeat it. Do not touch UI/theme/onboarding/landing-page work —
that is still explicitly out of scope until this module and Ritesh's review
of it are both done.

## 1. Mobile — the highest-priority gap

This is the single most important item, because three prior modules'
"disease-scan fixed" claims did not hold up on retest.

- `npx expo start -c` (clears bundler cache), fully close and reopen Expo Go
  on a real device (not just reload) — this exact sequence, every time, no
  shortcuts.
- Real photo → real upload → paste the actual Metro log showing a genuine
  `200` with a real model response body, or the exact new error if it's
  still broken. If it's still broken, that is the headline finding of this
  module — report it precisely, don't soften it.
- Full auth flow live: name+phone+OTP request → verify → session persists
  across a real app restart (not just a reload).
- Field creation (Add-Field) — confirm the created field round-trips through
  the real backend (check it via a direct `GET /v2/fields` call too, not
  just what the app shows).
- Irrigation advisory screen — real field, real values, cross-checked
  against the same field's real `GET /v2/fields/{id}/irrigation` response.
- Advisory audio — confirm both paths fire correctly: the real-backend-audio
  path for `_remote: true` advisories, and on-device `Speech.speak()` for
  local-only ones.
- Language switching — real device, cycle all four languages, screenshot
  every screen the app has (not just Home + one other), and confirm
  `preferred_language` is reflected in a real `GET /v2/farmers/me` call
  after the switch.
- History/Records — confirm and report plainly whether this is still
  client/session-only or has real backend persistence; Module 32 flagged
  this as unconfirmed, don't let it default to "looks fine."
- Full navigation pass — every tab, card, button, confirm nothing dead-ends.
- Also worth checking: `src/agro_mirai/api/gemini_client.py` — Module 32
  found this uncommitted, real code with a proper degrade-not-fail contract,
  but `GEMINI_API_KEY` unset. Confirm whether the mobile app has any UI path
  that calls it; if so, confirm it degrades honestly with the key unset
  (no silent fake answer), and report its current real status — don't wire
  a live key or build anything new here, just confirm current behavior.

## 2. Supabase — a deliberate, confirmed-first live round-trip

Module 32 found real `SUPABASE_URL`/`SUPABASE_KEY` values in `.env` but
correctly did not mutate a possibly-real hosted project without asking
first. This module has that go-ahead, with guardrails:

- Before writing anything, confirm with a read-only call (e.g. list tables
  or a trivial read) that this is a dev/test Supabase project, not anything
  connected to real farmer data — paste what you find and state your
  conclusion before proceeding to a write.
- Once confirmed safe, run the same repository-interface contract tests
  (`tests/persistence/contract/test_contract.py` or equivalent) against
  `SupabaseDataStore` for real — create a field, read it back, update it,
  confirm delete/cleanup afterward so no test data is left behind.
- Report exactly what was created and confirm it was cleaned up, with real
  before/after evidence (row counts or ids), not a summary claim.
- If anything about the target project looks ambiguous or not clearly a
  throwaway/dev instance, stop and ask before writing — this is the one
  place in this module where a pause-and-ask is correct over guessing.

## 3. Force the real GEE-live path

- `EE_SERVICE_ACCOUNT_KEY` is unset in `.env`, so today everything silently
  degrades to the NDVI cache path. Confirm whether Ritesh has a real GEE
  service account available; if not, report that plainly as a still-open
  gap rather than fabricating a key or skipping the check silently.
- If a real key becomes available, wire it (locally only, don't commit it),
  force a real NDVI/GEE call, and paste real evidence of the live path
  firing — then confirm the fallback-to-cache path still also works
  correctly when the key is removed again (both directions proven, not
  just one).
- If no key is available this session, that's an acceptable, honestly
  reported outcome — don't block the rest of the module on it.

## 4. Finish the separate-venv test suites

- Activate whatever `.venv/` (or equivalent) the project uses for
  `transformers==4.49.0`, and run `tests/voice` and `tests/vision` for
  real. Paste real pass/fail/skip counts, matching how CI actually runs
  them (check `.github/workflows/ci.yml` again if unsure of the invocation,
  the same way Module 32 confirmed the three-way split for the other
  suites).

## What NOT to do in this module

- No UI, theme, icon, onboarding, or landing-page work.
- No re-running Module 32's already-completed backend endpoint proof or
  mock-data grep — cite Module 32's results, don't repeat the work.
- No committing/pushing decisions to make here — Module 32's commit
  (`7d072a5`) is already sitting locally on `main`, not pushed; leave that
  exactly as Ritesh left it unless he says otherwise in this session.

## Definition of done

- [ ] Disease-scan retested on a genuinely fresh bundle + reopened Expo Go,
      real log pasted, honest pass/fail
- [ ] Full mobile flow list above proven live with real evidence
      (auth, field creation, irrigation, advisory audio both paths,
      language switch across all screens + server-persisted, History/Records
      status stated plainly, full navigation pass)
- [ ] gemini_client.py's current real wiring/behavior confirmed, not built on
- [ ] Supabase live round-trip proven with a confirmed-safe target project,
      real before/after evidence, test data cleaned up
- [ ] GEE-live path forced and proven if a key is available, or plainly
      reported as still-open if not
- [ ] tests/voice and tests/vision run for real in their own venv, real
      counts pasted

## Handoff format

```
Module: 33 — Mobile live testing, Supabase live round-trip, GEE-live path
Status: complete | blocked | needs-decision

Mobile:
  Disease-scan (fresh bundle): <real log, pass/fail — headline finding>
  Auth flow: <evidence>
  Field creation (+ backend cross-check): <evidence>
  Irrigation advisory (+ backend cross-check): <evidence>
  Advisory audio (both paths): <evidence>
  Language switch (all screens + server-persisted): <evidence>
  History/Records real status: <client-only vs backend-persisted, stated plainly>
  Navigation pass: <any dead ends>
  gemini_client.py current status: <wired/not wired, degrade behavior confirmed>

Supabase live round-trip:
  Target project safety confirmation: <what was checked, conclusion>
  Contract test results against SupabaseDataStore: <real evidence>
  Cleanup confirmation: <evidence>

GEE-live path:
  Key available: yes/no
  If yes: <live path proof, fallback-path re-proof>
  If no: <stated as open gap>

Separate-venv suites:
  tests/voice: <real counts>
  tests/vision: <real counts>

Known limitations carried forward:
Overall production-readiness verdict: ready | not ready, and exactly why
Next recommended step:
```
