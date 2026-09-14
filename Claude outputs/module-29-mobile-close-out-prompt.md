# MODULE 29 — Close the mobile app's last known gaps before real device-automation testing (Artemis)

Continuing AGRO MIRAI's mobile app (`mobile/`, Expo/React Native). This is
a short, closing module — four specific, verified-real items, not a new
feature tier. Once these are done and proven on a real device, testing
moves to Artemis (autonomous on-device test automation); running Artemis
before these are closed would just waste runs rediscovering known bugs.

Read `decisions/0023-name-phone-otp-auth.md` and the current
`mobile/App.tsx`/`mobile/src/config.ts` first — both were recently fixed
(disease-image upload via Blob conversion for Expo's Winter fetch, dynamic
`API_BASE_URL` from Metro's `hostUri`, Supabase service-role key removed).
Confirm you understand what's already correct before changing anything —
don't re-touch working code in this module.

## 1. Prove the disease-scan fix on a genuinely fresh bundle

The upload fix (fetching the local `file://` URI into a real `Blob` before
appending to `FormData`, instead of RN's classic `{uri,name,type}` shape)
is already in the code, but the last live test showed the *old* broken
behavior — almost certainly a stale Metro bundle, not a code regression.

- Run `npx expo start -c` (clears the bundler cache — a plain reload can
  serve stale JS).
- Fully close and reopen Expo Go on the phone, not just shake-to-reload.
- Take a real photo, submit it, and capture the actual Metro log output:
  either a genuine `200` with a real model response body, or — if it
  still fails — the exact new error, which would mean the Blob fix itself
  has a bug and needs real debugging, not another cache-clear guess.
- Do not report this step "done" without pasting that real log. If it's
  still broken after a clean cache clear, that's a real finding — report
  it precisely (exact error text, exact line), don't paper over it.

## 2. Close the advisory-audio 404

The dev server log showed:
```
GET /v2/advisories/adv-001/audio?language=en HTTP/1.1" 404
```
repeated five times in a row (the app was clearly retrying).

- Confirm whether `adv-001` genuinely doesn't exist for the authenticated
  farmer/session in question (likely — Module 27's auth revert changed
  who owns what data, and/or the seed fixture's advisory ids don't match
  whatever the mobile app is requesting), or whether this is a real route
  bug.
- If it's a seed/data mismatch: confirm `tools/seed_fixture.py` seeds an
  advisory the currently-logged-in test farmer actually owns, and that
  the mobile app is requesting an advisory id it actually received from a
  real `GET /v2/fields/{id}/advisories` call rather than a hardcoded or
  stale id anywhere in `App.tsx`. Grep for `adv-001` and any other
  hardcoded advisory/field id literal in `mobile/` — if one exists outside
  of test/seed code, that's the bug.
- If it's a genuine route bug: fix it, and add a test if the existing
  `tests/api/test_voice_routes.py` doesn't already cover "advisory exists
  but belongs to a different farmer" vs. "advisory id doesn't exist at
  all" as distinct 404 cases.
- Prove it live: real device, real advisory, real audio request, real
  200 (or a genuine, correctly-labeled 503 if the voice service itself
  is down — never a 404 for an advisory that actually exists and is
  actually owned by the logged-in farmer).

## 3. Rebuild the leaf-scan camera as full-bleed, not a boxed modal

Current camera UI is a bordered modal sheet: dark background, a header
row ("Camera View" / "Close"), a dashed guide-box, console warnings
rendering as an in-app toast. This reads as a bolted-on sub-screen, not
an integrated capture experience — confirmed by comparing directly
against ChatGPT's in-app camera mode, which is full-bleed with only a
thin translucent control bar floating over the live feed.

- Use `expo-camera`'s `CameraView` at `StyleSheet.absoluteFill` (full
  screen, no border, no boxed container) instead of the current modal
  sheet component.
- Remove the dashed rectangle guide entirely. If a capture-target hint is
  wanted, use small corner brackets (like a QR-scanner reticle) instead
  of a full dashed box — subtler, and doesn't read as a form field.
- Bottom controls: one translucent bar (use `expo-blur`'s `BlurView` if
  available, otherwise a semi-transparent dark `rgba` background) floating
  over the live camera feed near the bottom, containing: a small
  gallery-thumbnail/pick-from-library icon (left), a large white circular
  shutter button (center), a flash-toggle icon (right).
- Top: remove the "Camera View" title bar entirely. Replace with just a
  small transparent back-chevron in the top-left corner, no header
  background.
- This closes the earlier-flagged deprecated `ImagePicker.MediaTypeOptions`
  console-warning-as-toast issue too if it hasn't already been fixed —
  confirm no console output renders as in-app UI anywhere in the new
  component.
- Wire it to the existing (already-fixed) `analyzeLeafImage` function —
  do not touch that function's upload logic in this step, only the
  camera UI shell around it.

## 4. One pass: remove dead/duplicate navigation

- Confirm the Home grid no longer has a "History" card duplicating the
  bottom History tab (should already be fixed in Module 28 — verify, and
  finish if it wasn't).
- Grep for any other screen/card/button that navigates to a destination
  already reachable via the bottom tab bar, and collapse to one path.
- Confirm the static-fact modals (Irrigation Advisory Details, Crop
  Health Summary) are still just informational read-outs, not broken
  links or dead taps — no scope increase here, just confirm nothing
  regressed from Module 28.

## Definition of done

- [ ] Real, fresh-bundle proof the disease-scan upload genuinely works
      (or, if not, an honest precise report of what's still broken)
- [ ] `adv-001`-style 404 root-caused and fixed, proven live with a real
      advisory belonging to the logged-in farmer
- [ ] Camera rebuilt full-bleed per the spec above, no boxed modal chrome,
      no console warnings rendering as UI
- [ ] Dead/duplicate navigation entries removed, confirmed via a full
      screen-by-screen pass
- [ ] Full regression suite still passing (backend unaffected by this
      module — confirm nothing here touched `src/agro_mirai/`)
- [ ] Real device screenshots/logs for items 1-3, not descriptions

## Handoff format

```
Module: 29 — Close mobile gaps before Artemis testing
Status: complete | blocked | needs-decision
Item 1 (disease-scan fresh-bundle proof): <real log pasted, result>
Item 2 (adv-001 404 root cause + fix): <what was actually wrong, fix, live proof>
Item 3 (full-bleed camera): <before/after screenshots>
Item 4 (dead navigation removed): <list of what was removed>
Known limitations:
Ready for Artemis testing: yes/no, and why
```
