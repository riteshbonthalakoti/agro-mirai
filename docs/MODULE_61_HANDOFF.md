# Module 61 — Integration + proof: handoff (paused)

Status: **blocked on Module 52 merge to main**. Do not build the APK from this
branch yet — see "Why paused" below.

## What this branch is

`mod-61-integration`, created from `main` (worktree at `../agro-mod-61`), merging:
worktree-module-52-accounts → mod-53-notifications → mod-59-charts → mod-60-map.

This was done *before* Module 52's token-lifetime fix landed. Module 52 has since
been reworked on its own branch (7 TDD items: bearer token split, sign-out token
plumbing, AI-process file cleanup, comment-style cleanup, lockfile check, dialog
queueing) and pushed as PR riteshbonthalakoti/agro-mirai#1 — **still OPEN**, not
merged, as of this handoff.

## Why paused

This branch's Module 52 merge predates that fix, so it still carries the known
24-hour-token bug plus noisy plan docs. Building or proving an APK from it now
would ship the bug. Confirmed PR #1 state directly via `gh pr view 1`:
`state: OPEN, baseRefName: main, mergeable: MERGEABLE`.

## Next session: do this once PR #1 merges to main

1. Delete this worktree/branch (or just abandon it — nothing here needs to survive).
2. `git worktree add ../agro-mod-61-v2 -b mod-61-integration main` from updated `main`.
3. Merge in order: 53 → 59 → 60 (52 is already in `main` once the PR lands).
4. Re-apply the fixes below — they were real bugs independent of the token issue,
   not artifacts of the stale merge, and will very likely be needed again:
   - `mobile/babel.config.js` added by mod-53 breaks jest-expo's babel resolution
     (`Cannot find module 'babel-preset-expo'` — it's nested under
     `expo/node_modules`, not resolvable by a project-root `babel.config.js`).
     Delete the file; jest-expo + Expo's bundler supply the preset without it.
   - mod-59's `Charts.test.tsx` never declared `@testing-library/react-native` as
     a dependency. Add it — must be `~14.0.1`, not v13: React 19 dropped
     `react-test-renderer`, which v13 requires as a peer and therefore can't
     install at all. v14's `render()` is async under this React version;
     `Charts.test.tsx` needs every `it(...)` made `async` and every
     `render(...)` call `await`ed. One genuine test bug surfaced once that's
     fixed: `LabeledBar`'s null-value test asserted a single `getByText('—')`,
     but the nested `BarMeter(value={null})` it renders also shows `—`, making
     the query ambiguous — use `getAllByText('—').length > 0` instead.
   - mod-60's "zoom to field" button on `FieldMapScreen.tsx` was a stub
     (`// would need camera ref to update`) — but the bigger find: the `Map`
     component in `@maplibre/maplibre-react-native` has **no** `zoomLevel` or
     `centerCoordinate` props at all. The original code passed them via an
     `as any` cast, which silently no-ops — initial map centering was never
     actually working, button aside. Fix: render a `<Camera>` child with
     `initialViewState` for the initial position, hold a `cameraRef`, and call
     `cameraRef.current?.easeTo(...)` from the button. Added
     `mobile/src/mapCamera.ts` (`clampZoom`, `fieldCameraStop` — pure, tested)
     so the button's target coordinates aren't inline magic numbers.
5. Re-run `npx tsc --noEmit`, `npm test`, `pytest` after each merge step — all were
   clean on the stale branch (51/51 mobile tests, tsc clean, 582 passed/51 skipped
   in `pytest`, one pre-existing unrelated collection error in
   `services/cnn-onnx/tests/test_onnx_service.py` that also fails on plain `main`).
6. Then resume the original Module 61 brief: wire any remaining Module 60 gaps,
   measure APK size main vs. integrated, build via the local (non-EAS) process
   below, give the install command, hand Ritesh the device proof checklist.

## Real build steps (found this session — nothing like this existed in
root `CLAUDE.md`/`PROGRESS.md`, both stripped from `main` a while back)

No EAS cloud build is used for release — deliberately avoided for Windows
`MAX_PATH` reasons. From `docs/TOOLING.md`'s OTA section (historical, pre-strip)
and the ABI/size commits (`bd9bc4b`, `606db39`, `ad34902`):

```bash
# From a SHORT-PATH worktree (cloud build + long local paths both hit Windows MAX_PATH before)
EXPO_UPDATES_CHANNEL=production npx expo prebuild --platform android --clean
cd android && gradlew.bat assembleRelease
# APK lands at android/app/build/outputs/apk/release/app-release.apk
```

- `EXPO_UPDATES_CHANNEL` must be set *before* `prebuild` — it bakes into the
  generated native manifest; setting it after has no effect.
- ABI restriction (`armeabi-v7a`+`arm64-v8a` only, drops emulator-only
  `x86`/`x86_64`) and `minifyEnabled`/`shrinkResources` are both locked in via
  the `expo-build-properties` plugin in `mobile/app.json`, so they survive every
  `prebuild --clean` — no more hand-editing `gradle.properties`.
- No dedicated signing/keystore commit found in history — reads as Expo's
  default debug keystore, consistent with direct-sideload distribution rather
  than a Play Store submission.
- `mobile/eas.json` still exists but only matters for `eas update` (OTA
  publish/promote), not for building the release APK.

## Test/branch state reference

- `mod-61-integration` (this branch, stale — see "Why paused"): 6 commits past
  `main`, listed oldest-first above. Kept only as a reference for the conflict
  resolutions, not meant to be merged as-is.
- Branches confirmed to exist at session start: `mod-53-notifications`,
  `mod-56-sms-otp`, `mod-59-charts`, `mod-60-map`, `worktree-admin-dashboard-v2`,
  `worktree-module-51-offline-errors-bug-reporting`,
  `worktree-module-52-accounts`. No plain `mod-52-accounts` branch exists —
  `worktree-module-52-accounts` is module 52's actual branch, confirmed with you
  at the time.
