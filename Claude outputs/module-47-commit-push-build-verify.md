# MODULE 47 — Commit, push, build, and verify the Module 46/47 redesign for real

Continuing AGRO MIRAI. The mobile redesign session (on-device voice
fallback, background notifications, full visual redesign, voice-mode
rebuild, Telugu audio re-record) is functionally described in the prior
handoff, but a direct check of the repo found **none of it is committed
or pushed** — `git status` shows every file from that session as
uncommitted local changes, and `origin/main` on GitHub is still at the
pre-redesign commit. Nothing from this work exists anywhere except this
one laptop right now. This module closes that gap and then does the one
verification step that's genuinely still missing: a real installed build,
tested manually via ADB, confirming notifications actually fire when the
app is closed.

## 1. Commit the work, in logical groups, human-style

Following the standing rules (short, plain, human commit messages, no
conventional-commits formatting, no AI-attribution anywhere): split the
current uncommitted changes into a few logical commits rather than one
giant one. Reasonable groupings based on what's uncommitted:
- the on-device voice fallback (`audio.ts`, the `EXPO_PUBLIC_FORCE_VOICE_503`
  dev switch, `VoiceMode.tsx`, `app.json`'s `expo-background-task` plugin
  addition)
- background notifications (`backgroundAlerts.ts`)
- the visual redesign (`AuthBackdrop.tsx`, `PickGrid.tsx`, `FirstField.tsx`,
  `pickImages.ts`, the screen files under `mobile/src/screens/`, the new
  `mobile/assets/pick/` images, `mobile/assets/field-hero.jpg`)
- the re-recorded Telugu audio files
- doc/progress updates (`PROGRESS.md`, `README.md`, `docs/PPT_VS_CODE_AUDIT.md`)

Use your own judgment on the exact split — the point is each commit's
message honestly describes what it changed, not that the split matches
this list exactly. Confirm nothing in `.env`/secrets is accidentally
staged before committing.

## 2. Push to `main`

- Push all commits to `origin/main`.
- Confirm afterward, by actually re-fetching, that `origin/main`'s latest
  commit matches what you just pushed — don't assume the push succeeded
  from the command's exit code alone.

## 3. Build a real installable APK from what's now on `main`

- Build a release or dev-client APK (your call on which is faster/more
  appropriate to iterate with right now) from the just-pushed code —
  not from a stale local state.
- Confirm the build actually completes and produces a real `.apk` file.

## 4. Install via ADB and verify, with Ritesh watching

- Walk Ritesh through installing it via `adb install` on his real device
  (he said he wants to do this manually himself — guide him through the
  exact commands rather than doing it for him if that's his preference,
  or do it yourself if he hands you the device access — confirm which).
- The one thing that has never been verified and cannot be verified in
  Expo Go: **background notifications when the app is fully closed.**
  Confirm this for real: force-close the app, trigger conditions for a
  high/severe advisory (or use test data that already qualifies), wait
  for Android's own scheduling window, and confirm a real system
  notification appears — screenshot it.
- Also spot-check a few of the redesigned screens render correctly in
  this real build (not just Expo Go) — Sign-in, Field/Data tab, Advice
  tab's new voice mode UI (states only — don't trigger a real Sarvam call
  per the standing quota-protection instruction), Scan tab.
- Confirm the on-device voice fallback still works in this real build via
  the `EXPO_PUBLIC_FORCE_VOICE_503` dev switch (not a real Sarvam call).

## What NOT to do

- Don't make new functional changes in this module — commit, push, build,
  and verify what already exists. If something breaks during verification,
  fix that specific regression and note it, but don't scope-creep into new
  features (landing page, admin dashboard — those are Module 48).
- Don't trigger a real Sarvam call anywhere in this verification —
  continue protecting demo quota.
- Don't tag a new release/APK download link on the landing page yet if
  Module 48 is about to touch the landing page anyway — check with
  Ritesh before publishing this as a public release.

## Handoff format

```
Module: 47 — Commit, push, build, verify the redesign
Status: complete | blocked

Commits made: <list, short messages as committed>
Pushed to origin/main: <confirmed via re-fetch, commit SHA>

APK built from: <confirmed commit SHA, dev-client or release>
ADB install: <confirmed on Ritesh's device>

Background notifications (first-ever real verification):
  <confirmed working / not working, real screenshot>

Redesigned screens spot-check in real build: <what was checked, results>
On-device voice fallback in real build: <confirmed via forced-503>

Known limitations:
Next recommended step:
```
