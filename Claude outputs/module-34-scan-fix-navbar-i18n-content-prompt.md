# MODULE 34 — Fix the disease-scan bug, make the nav bar adaptive, and fix language switching for real (including user-entered content)

Continuing AGRO MIRAI. Module 33 closed out with a precise, confirmed root
cause on the one real remaining functional bug, plus two UX problems Ritesh
flagged directly: the bottom nav bar overlapping content on some screen
sizes, and language switching not actually being complete — both in the
sense that not every screen was swept, and in a deeper sense Ritesh just
raised: a farmer's own typed-in data (a custom field name, crop name, notes)
doesn't change when the app's language is switched, because it was typed in
one language and stored as-is. This module fixes all three, in priority
order. This is still functionality work, not a visual redesign — don't touch
theme/icons/onboarding here.

## 1. Fix the disease-scan upload bug (top priority — do this first)

Module 33's root cause, confirmed via a live backend debug trace: the
"image" field's actual multipart content was the literal 14-byte string
`"File not found"` — `analyzeLeafImage`'s `fetch(imageUri).then(r => r.blob())`
call against the local `file://` URI is failing, and instead of throwing,
something downstream is packaging the failure's error text as if it were
the image blob.

- Find the exact `fetch(imageUri)` call in `analyzeLeafImage` (or wherever
  it now lives) and add real error handling: check `response.ok` before
  calling `.blob()`, and if the local file read fails, throw a real,
  specific error immediately — do not let a failed fetch's response body
  silently become the multipart payload.
- Root-cause *why* the local `file://` fetch is failing at all in the first
  place (this is the actual bug, not just the missing error handling) —
  check the exact URI shape `expo-camera`/`expo-image-picker` returns in
  the SDK 57 version confirmed live in Module 33, whether a `file://`
  prefix is present/duplicated, and whether Expo's Winter-fetch has a known
  quirk reading local URIs directly (it may need `expo-file-system`'s
  `readAsStringAsync`+base64, or a different local-read API, instead of
  `fetch()` against a `file://` URI at all — check Expo's current docs for
  this SDK version rather than assuming the old approach still applies).
- Fix the app's own error message too — Module 33 found it says "couldn't
  reach the server" even when the server was reached and returned a real
  400/422. Make the error state accurately reflect what actually failed
  (local read vs. network vs. server-side validation).
- Prove the fix with the exact same sequence Module 33 used: `npx expo
  start -c`, force-stop and cold-reopen Expo Go, real photo, real upload,
  paste the real Metro log and the real backend log showing a genuine
  model response — not a repeat of the same silent failure.

## 2. Make the bottom nav bar genuinely adaptive across phone sizes

Module 33 found real visual overlap (the nav bar covering content like
"Irrigation Details" on at least one real device/screen size).

- Find the nav bar component and confirm what's actually causing the
  overlap — almost certainly missing safe-area-inset handling (notch/home-
  indicator devices) and/or a fixed-height bar with content that doesn't
  reserve space for it (`paddingBottom`/`contentInset` missing on the
  scrollable content behind it).
- Fix using `react-native-safe-area-context`'s `useSafeAreaInsets()` (or
  confirm it's already a dependency and just not wired to this component)
  so the bar's height and the scrollable content's bottom padding both
  account for the real device inset, not a hardcoded pixel value.
- Test on at least two different real screen sizes/aspect ratios if more
  than one device is available (or the iOS/Android simulator's various
  device presets at minimum) — a fix that only works on one phone's exact
  dimensions isn't actually fixed. Screenshot each.
- Confirm no other screen has the same hardcoded-bottom-offset pattern
  (grep for magic-number `paddingBottom`/`marginBottom`/`bottom:` values
  near the tab bar area across screens) — fix any others found, don't
  leave a second instance of the same bug.

## 3. Language switching — finish the per-screen sweep, then fix the real architectural gap on user-entered content

### 3a. Finish what Module 33 didn't get to

Module 33 proved language switching works correctly for the Home screen
across all four languages, server-confirmed, but did not sweep every
remaining screen given time. Do that now: switch to each of `en`/`kn`/
`te`/`hi` and screenshot every real screen in the app (Records, Settings,
Add Field, Farmer Login/OTP, AI Scan, Irrigation Details, Crop Health,
Regional Language Confirmation, and anything else that exists) — fix any
remaining hardcoded strings found, the same hard-grep-plus-live-proof bar
prior i18n modules used.

### 3b. The real architectural gap — user-entered content doesn't translate

This is the important new finding: when a farmer types a custom field name
(or crop notes, or anything else they enter themselves) in whatever
language they're using at the time, that text is stored as-is. Switching
the app's language later correctly re-translates the app's own UI chrome
(labels, buttons, static advisory templates) but obviously cannot magically
translate a *farmer's own words* that were never run through the i18n
table in the first place — because they were never a `t.*` key, they're
data.

Do this properly, not with a shortcut:

- First, confirm precisely which fields are farmer-entered free text
  (field name, any notes field, anything else — check both the mobile
  forms and the backend schema) versus farmer-selected from a fixed set
  (crop type is likely a dropdown/enum already covered by `t.*` — confirm
  this either way, don't assume).
- For fields that are a fixed enum/dropdown (e.g. crop type selected from
  a list): confirm these are already stored as a stable key (not the
  currently-displayed-language string) and rendered through `t.*` at
  display time in whatever language is active. If they're currently being
  stored as the literal display string in whichever language was active at
  entry time, that's a real bug — fix it so the stored value is a
  language-independent key.
- For genuinely free-text fields (a custom field name a farmer typed): a
  stored string cannot be retroactively known to be "in" a source
  language reliably, and there is no free lossless way to keep it
  correct in 4 languages without either (a) real machine translation at
  write-time (store the original plus MT'd versions in the other 3
  languages, refreshed if edited) or (b) simply always displaying the
  farmer's own entered text as-is regardless of UI language, which is
  actually the more honest and lower-risk choice for a proper noun like a
  field's own name (most apps don't translate a user's own chosen name for
  something — e.g. a farmer's own field nickname stays as they typed it,
  the same way a person's name doesn't get translated). Investigate
  whether the backend already has any MT capability available (check
  `IndicTrans2`/`indic-conformer` or whatever this project's existing
  translation stack — from `CLAUDE.md`/Module 12/25 — could realistically
  be reused for short-string MT, since that's genuinely free and already
  proven, versus reaching for a new paid API) and report the honest
  tradeoffs of both options with a recommendation, but do not silently
  pick one and build it without stating the choice clearly in the
  handoff — this is a real product decision (translate farmer's own words
  automatically vs. never translate them) and Ritesh should see the
  tradeoff explicitly, though you may implement your recommended default
  if it's clearly the safer/simpler one (leave user text as-is, always
  translate only the app's own chrome) since that's reversible later.
- Whatever you land on, document it as an explicit decision (a short note
  in `decisions/` following this project's existing ADR pattern) so this
  doesn't get re-litigated as a "bug" in a future module.

## 4. Advisory-audio staleness (from Module 33, small, do if time allows)

Module 33 found the Home screen's advisory data doesn't refresh in-app
after new backend data appears — pull-to-refresh and tab navigation both
left it stale. Find why (missing query invalidation / stale cache / no
refetch-on-focus) and fix it so a real backend advisory becomes visible
without a full app restart. Prove it live: seed a new advisory server-side,
confirm it appears in-app via pull-to-refresh or navigation alone.

## What NOT to do in this module

- No theme/icon/onboarding/landing-page work.
- No re-running Module 32/33's already-completed backend proof, Supabase
  round-trip, or GEE-live path checks — those are done, cite them.
- No pushing `main` — the Module 32 commit stays local/unpushed exactly as
  Ritesh left it unless he says otherwise this session.

## Definition of done

- [ ] Disease-scan upload genuinely fixed and proven on a fresh bundle,
      real backend log showing a real model response, root cause of the
      local-file fetch failure named precisely
- [ ] App's own error message accurately reflects the real failure type
- [ ] Nav bar fixed with real safe-area-inset handling, proven on 2+ real
      screen sizes/presets, no other hardcoded-offset instances left
- [ ] Full per-screen language sweep completed across all 4 languages,
      any remaining hardcoded strings fixed
- [ ] User-entered-content translation question investigated and resolved
      with an explicit, documented decision (new ADR), not silently picked
- [ ] Advisory staleness fixed and proven, if time allows

## Handoff format

```
Module: 34 — Disease-scan fix, adaptive nav bar, complete language switching
Status: complete | blocked | needs-decision

Disease-scan fix:
  Root cause of local-file fetch failure: <exact finding>
  Fix applied: <what changed, files>
  Error-message fix: <before/after>
  Live proof (fresh bundle): <real Metro + backend log>

Nav bar fix:
  Root cause: <safe-area / hardcoded offset, exact finding>
  Fix applied: <files>
  Proof across screen sizes: <screenshots, which devices/presets>
  Other instances found/fixed: <list or "none found">

Language switching:
  Per-screen sweep: <screens covered, any fixes made>
  User-entered-content decision: <the tradeoff as presented, which option
    was chosen and why, ADR file path>
  Implementation: <what was actually built, if anything>

Advisory staleness: <fixed/not reached, evidence if fixed>

Known limitations:
Overall status: ready for UI/redesign phase to resume: yes/no, why
Next recommended step:
```
