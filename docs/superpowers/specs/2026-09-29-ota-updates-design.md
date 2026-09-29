# OTA Updates (EAS Update) — Design

Date: 2026-09-29
Status: approved for planning

## 1. Context

The mobile app currently ships only as a full native APK, distributed via GitHub Releases and
linked from the landing page (v1.6.0 as of this writing). Any JS-only fix or content change
requires a full native rebuild and a fresh install by every user — slow, and a real burden for
a project whose whole recent history (Module 51, the APK-size pass) has been about shipping
small, iterative fixes quickly.

`expo-updates` is not currently installed. No `runtimeVersion` or `updates` config exists in
`mobile/app.json`. This is genuinely new infrastructure, not an extension of an existing flow.

## 2. Goal

Let most future JS/asset-only changes reach installed apps without a new APK, while keeping a
real human checkpoint before anything reaches actual users — not full auto-deploy like the web
side, because a bad OTA update reaches real devices silently in the background, unlike a website
refresh a developer can immediately see and revert.

## 3. Architecture

**Two EAS Update branches, mapped to two channels of the same name:**
- `staging` — for Ritesh's own test installs (the `preview` eas.json build profile points here)
- `production` — what the publicly-distributed APK (the `production` build profile) points to

**Runtime version policy:** `{"policy": "appVersion"}` — an update is only offered to installs
whose native binary's `app.json` version string matches. This is the safety mechanism that
prevents a JS update written against a newer native module from silently reaching an old binary
that doesn't have it; Expo Updates simply won't offer an incompatible update rather than crashing.

**Publish flow (the manual gate):**
1. `eas update --branch staging --message "<what changed>"` — publishes a new JS/asset bundle to
   the staging branch. Can be scripted/automated up to this point.
2. Ritesh installs/opens the `preview`-channel build on his own phone, force-closes and reopens
   it twice (first launch downloads the update in the background; Expo Updates applies it on the
   *next* launch after that — this is documented, expected behavior, not a bug to work around).
   Confirms the change is real before it goes further.
3. `eas channel:edit production --branch staging` — repoints the `production` channel at the
   exact same, already-verified update. Not a rebuild, not a re-publish: the literal bits Ritesh
   just tested go live. This command is the actual safety gate and stays manual, run by Ritesh
   himself, never automated.

**One hard constraint:** this only works for app installs that already have `expo-updates`
compiled in. The already-released v1.6.0 APK does not. This spec requires one more native
rebuild (v1.7.0) before OTA capability exists at all; v1.6.0 installs will need one more manual
APK update, same as today, to gain OTA capability going forward.

## 4. Components

- `mobile/package.json` — add `expo-updates` dependency (via `npx expo install expo-updates`,
  which also picks the SDK-compatible version automatically).
- `mobile/app.json` — add `"runtimeVersion": {"policy": "appVersion"}` and
  `"updates": {"url": "https://u.expo.dev/<projectId>"}` (projectId already exists in
  `expo.extra.eas.projectId`, confirmed present from an earlier EAS build attempt).
- `mobile/eas.json` — add `"channel": "staging"` under the `preview` build profile's config,
  `"channel": "production"` under the `production` profile's config.
- `mobile/src/updates.ts` (new) — a single function, called once from `App.tsx` on launch:
  checks for an update via `Updates.checkForUpdateAsync()`, and if one exists, calls
  `Updates.fetchUpdateAsync()` in the background. Never blocks rendering, never shows a
  farmer-facing error on failure (offline, EAS down) — matches this project's existing
  "degrade, never fail" doctrine exactly (GEE→NDVI cache, CNN service→rule-based fallback,
  voice down→503, all the same shape: an external dependency being unavailable is an expected,
  silently-handled case, not an error state).
- `.github/workflows/publish-update.yml` (new) — `workflow_dispatch` only (manually triggered
  from the GitHub Actions tab or `gh workflow run`), runs `eas update --branch staging --auto`
  (`--auto` derives the message from the latest commit). This automates step 1 of the publish
  flow; steps 2 and 3 stay manual CLI commands Ritesh runs himself, documented in
  `docs/TOOLING.md`.

## 5. Error handling

Update-check failures are silent and non-blocking, matching the project-wide doctrine already
established for every other external dependency. No retry loop, no farmer-facing error, no
crash — the app simply continues running on its current bundle, identical to today's behavior
for every user until a fix genuinely reaches them.

## 6. Testing / live-proof plan

1. Build and install the new `preview`-profile APK (with `expo-updates` configured) on Ritesh's
   phone.
2. Publish a trivial, visually-confirmable change (e.g., a temporary version-label tweak
   somewhere in the UI) to the `staging` branch.
3. Force-close and reopen the app twice; confirm the change appears on the second reopen, not
   the first (proves the real Expo Updates download-then-apply-on-next-launch behavior, not a
   false positive from a fresh JS reload).
4. Revert the test change, publish that too, confirm it disappears the same way.
5. Only then: promote a real change to `production` via `eas channel:edit`, and confirm on the
   publicly-distributed APK.

## 7. Known limitations

- v1.6.0 (already released) has no OTA capability; this is a one-time, unavoidable gap closed
  by the next native release (v1.7.0).
- No code-signing configured for updates (EAS Update supports this as an option). Skipped
  deliberately for now — genuine extra security, but real setup overhead for a capstone-scale
  project with a single publisher (Ritesh) and no adversarial threat model that signing would
  meaningfully defend against. Documented here as a real, considered trade-off, not an oversight.
- The manual promotion step (`eas channel:edit production --branch staging`) has no audit trail
  beyond EAS's own dashboard history — acceptable at this project's scale (single publisher),
  not something a `PROGRESS.md`-style commit-message record covers today.
