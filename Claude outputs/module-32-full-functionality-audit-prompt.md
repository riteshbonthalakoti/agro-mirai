# MODULE 32 — Full system functionality audit: prove every documented feature actually works end-to-end, production-readiness only (no UI/UX work in this module)

Continuing AGRO MIRAI. Explicit instruction from Ritesh: **stop touching UI/visual work entirely for this module.** Before any redesign, onboarding, or landing page work resumes, he wants hard proof that every documented feature — backend and mobile — actually works, end to end, on real data, with real evidence. Treat this as the pre-production gate. Nothing in this module is "looks right" — everything is "ran it, here's the log/screenshot/response body."

Do not write or edit any styling, layout, icon, theme, or onboarding code in this module. If you find a genuine functional bug while doing this audit, fix it (that's in scope); do not fix or improve anything cosmetic.

## 0. Establish the actual feature list first

- Read `CLAUDE.md`, every file under `decisions/` (all ADRs), `specs/core/openapi.yaml`, and every `MODULE_*`/handoff doc still on disk, and build a single flat checklist of every feature that has been claimed as "done" across Modules 01–31. Include backend endpoints, mobile screens/flows, the voice/audio pipeline, i18n, and auth.
- This checklist is the actual deliverable structure for this module — every item below must map to one or more rows in it, each row ending in pass/fail/blocked with real evidence, not a description.

## 1. Backend — prove every documented endpoint against the real spec

- Cross-check `specs/core/openapi.yaml` against the actual FastAPI/Flask routes in `src/agro_mirai/api/` — every documented endpoint must exist in code, and every real endpoint must be documented (flag any drift either direction).
- For every endpoint, run a real request against a real running server (not a unit-test mock) and paste the actual request + real response body: auth (`/v2/auth/request-otp`, `/v2/auth/verify-otp`, `/admin` login), farmer profile (`GET/PATCH /v2/farmers/me`), fields (`create/list/get`), irrigation, disease-risk (both the JSON and the image-upload path), advisories (list + audio), and anything else in the spec.
- Run the full existing automated test suite (`pytest` or whatever the project uses) and paste real pass/fail counts, not a summary claim. If anything is skipped or xfail, name it and why.
- Confirm the DataStore repository abstraction genuinely works against both backends it claims to support (SQLite-dev, Supabase-prod per `CLAUDE.md`'s doctrine) — at minimum, confirm the interface is actually backend-agnostic in code (no SQLite-only assumptions leaking into shared logic), and note if only one backend has actually been exercised.
- Confirm the GEE-live-with-NDVI-cache fallback described in `CLAUDE.md` actually triggers correctly in both the live and cache-fallback case — force both paths if possible, show real evidence for each.

## 2. Mobile — prove every documented screen/flow against a real running app

For each item, real device or emulator, real screenshots/logs — no "should work":

- Full auth flow: name+phone+OTP request → verify → session persists across app restart.
- Field creation (Add-Field flow) and field listing — confirm real backend round-trip, not local-only state.
- Disease scan: real photo → real upload → real model response rendered — this was the subject of three prior modules' "fixed" claims that didn't hold up under retest, so this is the single most important item in this module to re-verify with a completely fresh Metro bundle (`npx expo start -c`) and a fully closed-and-reopened Expo Go session. Paste the actual log.
- Irrigation advisory flow: real field → real advisory data → real values, cross-checked against what the backend actually returned (no client-side placeholder numbers).
- Advisory audio playback: both the real-backend-audio path (`_remote: true` advisories) and the on-device `Speech.speak()` path — confirm both actually produce audio, and confirm which path was used matches the advisory's actual origin.
- Language switching: real device, cycle through all four languages, confirm visible text changes on every screen the app has (not just Home + one other) — and confirm `preferred_language` is actually persisted server-side after the switch (`GET /v2/farmers/me` should reflect it).
- History/Records: confirm what's real vs. session-only — if this is still client-only with no backend persistence (a gap flagged in Module 31), state that plainly here as a real, current limitation, don't reclassify it as fixed.
- Full navigation pass: every tab, every card, every button actually leads where it claims to, nothing dead-ends or errors silently.

## 3. Cross-cutting: no fabricated data anywhere in the live path

- Re-run the hardcoded/mock-data audit from Module 31 (this was explicitly not completed last time) — grep both `mobile/App.tsx` (and any other `.tsx`/`.ts` under `mobile/`) and all of `src/agro_mirai/` for `mock`, `fake`, `dummy`, `hardcod`, `TODO`, `FIXME`, `placeholder`, and any suspiciously-fixed literal (a specific lat/long, crop name, percentage) not clearly a test fixture or documented fallback.
- Classify every hit: (a) genuinely fine — a documented degrade-not-fail fallback, cite the doctrine; (b) test/fixture code, out of the live path; (c) a real problem — fix it.
- Confirm no screen renders a number that didn't come from a real `/v2` response body.

## 4. Known gaps — confirm status honestly, don't re-claim fixed

Explicitly re-check and report current true status (not the status from an old report) on:
- Hindi Piper TTS voice file (flagged in `CLAUDE.md` as needing download).
- OTP delivery (currently server-log-only, no SMS provider wired) — confirm this is still accurately documented as a known limitation, not silently assumed fixed.
- Any other item currently listed as a known limitation anywhere in `CLAUDE.md` or prior module handoffs — go through that list one by one and confirm current real status.

## What NOT to do in this module

- No theme/color/typography changes.
- No new UI components, icons, or screens.
- No onboarding work.
- No landing page work.
All of that resumes only after this module is reviewed.

## Definition of done

- [ ] Full feature checklist built from CLAUDE.md/ADRs/openapi.yaml/prior handoffs, every row resolved to pass/fail/blocked
- [ ] Every backend endpoint proven live against the real server, real request/response pasted
- [ ] Full automated test suite run, real pass/fail counts pasted
- [ ] Every mobile flow proven on a real device/emulator with real screenshots/logs, disease-scan re-verified on a genuinely fresh bundle
- [ ] Hardcoded/mock-data audit fully re-run and completed (not deferred again), every hit classified
- [ ] Every previously-flagged known limitation re-checked for current true status, not assumed fixed
- [ ] Zero UI/UX/onboarding/landing-page work performed in this module

## Handoff format

```
Module: 32 — Full functionality audit (production-readiness gate)
Status: complete | blocked | needs-decision

Feature checklist: <link/path to the full checklist with pass/fail/blocked per row>

Backend:
  Endpoint coverage vs openapi.yaml: <drift found, if any>
  Live endpoint proof: <summary, full detail in checklist>
  Test suite: <real pass/fail counts>
  DataStore backend-agnosticism: <confirmed how>
  GEE live/cache fallback: <both paths proven>

Mobile:
  Auth flow: <pass/fail, evidence>
  Field creation: <pass/fail, evidence>
  Disease scan (fresh bundle): <real log, pass/fail>
  Irrigation advisory: <pass/fail, evidence>
  Advisory audio (both paths): <pass/fail, evidence>
  Language switching (all screens + persisted server-side): <pass/fail, evidence>
  History/Records real-vs-session-only: <current true status>
  Navigation pass: <any dead ends found>

Hardcoded/mock-data audit: <full list, each classified, fixes made>

Known limitations re-checked: <current true status of each, one by one>

Overall production-readiness verdict: ready | not ready, and exactly why
Next recommended step:
```
