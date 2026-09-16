# MODULE 31 — Build the v2 redesign for real, add onboarding, finish the i18n sweep, full hardcoded-data audit

Continuing AGRO MIRAI's mobile app (`mobile/App.tsx`). Context: a live
read of the current `App.tsx` (done independently, not from a report)
found that most of the "fake/hardcoded data" problem is already solved —
no fake demo field, no demo-login backdoor, real session-only scan
history, a real Add-Field flow, real OTP auth. That work is good and
should not be redone. What's still outstanding is real: the app's visual
design was only ever mocked up, not built; there's no real onboarding
sequence beyond language/location; and the i18n and voice work from
Modules 28-30 need to be genuinely finished and confirmed, not assumed.

Read the published redesign mockup first — the artifact from the "Field
& Grain, Reforged" design pass (light-only, one shared SVG icon set, the
field/crop switcher moved to Settings). Ritesh has this link; ask him for
it if it's not already in your context. Build against its actual
component specs below, not a fresh interpretation.

## 1. Build the redesign for real (not a fresh design — implement the mockup)

- **Light theme only.** Remove any dark-mode styling in the current app.
  This is a deliberate call, not an oversight: a field tool read outdoors
  in direct sun is actively hurt by a dark UI. Base palette: grain-cream
  ground (`#FBF7EC`/`#F2EBDA`), deep field-green structure
  (`#16301F`/`#21492E`/`#3E7A50`), a wheat accent (`#C99A3E`) held to one
  interactive gold moment per screen, severity colors kept strictly
  separate from brand color (`good #2F7D4F`, `caution #B9791F`,
  `urgent #B23A2E`).
- **Replace every emoji with a real SVG icon.** Build one shared icon
  component/set (leaf, drop, blight, sprout, home, camera, list, play,
  chevrons, bolt, gallery, globe, user, field, mic, thermometer — the
  full set is in the mockup's inline `<defs>`) at 1.6px stroke weight,
  used everywhere: tab bar, signal cards, camera controls, settings rows.
  Zero emoji characters should remain anywhere in rendered UI text.
- **Move the field/crop switcher off Home into Settings.** Home no longer
  shows a field-picker pill in the header. Add a Settings tab (4th tab:
  Home / Scan / Records / Settings) with a "Fields" group showing the
  active field and an "Add a field" row (reuse the existing Add-Field
  modal/flow already built — don't rebuild it, just relink its entry
  point). Most growers here run one field; multi-field growers reach the
  switcher in one tap instead of it occupying permanent header space for
  everyone.
- **Merge History and Advisories into one "Records" tab.** Same card
  shape for both — a severity stripe down the left edge, icon, title,
  timestamp, one line of body text, a play button, a confidence/method
  tag — filterable by chip (All / Irrigation / Disease). Reduces the tab
  count growth from adding Settings back to a net-neutral four tabs.
- **Home's fact-panels become inline expandable, not modals.** Tapping
  the Irrigation/Disease/Crop signal card expands a panel in place
  (chevron flips) showing the real label/value rows already computed by
  the backend, plus a 7-point sparkline if the backend has that history
  available (check `GET /v2/fields/{id}/irrigation` and similar for
  whether historical soil-moisture/depth values are already returned; if
  not, that's a real backend gap to report, not something to fake client-
  side with placeholder trend data).
- **Camera stays full-bleed** (this part may already be correct from
  Module 29 — verify, don't redo): no modal border, no "Close" header,
  corner-bracket reticle instead of a dashed box, one translucent control
  bar (gallery / shutter / flash as SVG icons, not emoji).

## 2. Build a real first-run onboarding sequence

Today the app goes roughly: language/location detection → OTP auth →
Home. That's functional but not an onboarding experience. Add:

- A brief (2-3 screen max — this is a utility app, not a consumer social
  app, don't over-build this) first-run sequence after language/location
  confirm and before the auth screen: what the app does in one sentence
  per screen (e.g. "Get today's irrigation and disease advice for your
  field, spoken in your language"), shown once (track with local
  storage/AsyncStorage, not shown again after first launch).
- After first successful login with zero fields, the empty state should
  clearly walk the farmer into the Add-Field flow rather than just
  showing an empty Home screen — confirm this exists or add it.
- Keep every string in this new flow routed through the `t.*` translation
  table from the start — don't add a fifth place where English gets
  hardcoded (see Section 3).

## 3. Finish the i18n sweep — hard requirement, not a spot-check

Module 28 partially migrated hardcoded strings to `t.*`. This module
finishes it, verifiably:

- Grep the entire `App.tsx` (and any other `.tsx`/`.ts` file under
  `mobile/`) for JSX text content and string literals passed to `Text`,
  `Alert.alert`, placeholder props, etc. that are NOT `t.something` —
  every match is either a real remaining gap to fix, or a deliberate
  exception (a proper-noun brand name, a raw number/unit) that you name
  explicitly in your report.
- Cover the new onboarding and Settings screens from this module in the
  same pass — don't let new hardcoded strings get added while fixing old
  ones.
- Confirm `preferred_language` is actually sent to the backend
  (`PATCH /v2/farmers/me`) when the language picker changes post-login —
  this was flagged as an open gap in Module 28's own report and never
  confirmed closed.
- **Live proof, not a claim**: real device, switch to each of the four
  languages in turn, screenshot Home + Records + Settings for each one.
  Four languages × three screens = 12 screenshots, or a clear equivalent
  video. This is the actual bar — a previous "fixed" report on this exact
  issue did not hold up on retest, so don't report done without the
  evidence attached.

## 4. Full hardcoded/mock-data audit — backend and mobile, evidence required

Confirm nothing fabricated remains anywhere in the live request path:

- Grep both `mobile/App.tsx` and `src/agro_mirai/` for `mock`, `fake`,
  `dummy`, `hardcod`, `TODO`, `FIXME`, `placeholder` (excluding genuine
  UI placeholder-text props), and any suspiciously-fixed literal (a
  specific lat/long, a specific crop name, a specific percentage) that
  isn't clearly a test fixture or a documented fallback constant.
- For every hit, classify it in your report as: (a) genuinely fine — a
  documented fallback/default per this project's degrade-not-fail
  doctrine, cite the doctrine; (b) test/fixture code, out of the live
  path; or (c) a real problem, and fix it.
- Confirm every screen's data genuinely round-trips through a real `/v2`
  API call by cross-checking against `specs/core/openapi.yaml` — no
  screen should render a number that didn't come from a real response
  body.

## Definition of done

- [ ] Redesign implemented against the mockup's real component specs —
      light-only, full SVG icon set, field switcher in Settings, Records
      merged, inline expandable fact panels, camera confirmed full-bleed
- [ ] Onboarding sequence built, shown once, fully localized from the start
- [ ] i18n sweep complete with a real grep result reported (not "looks
      done"), `preferred_language` PATCH confirmed wired, 12-screenshot
      (or equivalent) live proof across all four languages
- [ ] Hardcoded/mock-data audit complete across both `mobile/` and
      `src/agro_mirai/`, every finding classified and reported

## Handoff format

```
Module: 31 — Redesign build, onboarding, i18n completion, hardcoded-data audit
Status: complete | blocked | needs-decision
Redesign: <screens changed, screenshots>
Onboarding: <screens added, screenshots>
i18n sweep: <grep results, fixes made, preferred_language PATCH status, 12-screenshot proof>
Hardcoded-data audit: <full list of hits found, each classified, fixes made>
Known limitations:
Next recommended step:
```
