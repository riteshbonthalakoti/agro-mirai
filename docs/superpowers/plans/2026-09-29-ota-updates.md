# OTA Updates (EAS Update) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let most future JS/asset-only mobile app changes reach installed apps without a new APK, via EAS Update, with a real manual checkpoint (Ritesh tests on his own phone) before anything reaches the publicly-distributed build.

**Architecture:** Install `expo-updates`, configure `runtimeVersion: {policy: "appVersion"}` so an update only reaches binaries whose version matches. Two EAS Update branches/channels — `staging` (Ritesh's test installs) and `production` (the public APK) — with `production` populated by *repointing* it at an already-tested `staging` update (`eas channel:edit`), never by a separate publish, so what ships is byte-identical to what was verified.

**Tech Stack:** Expo SDK 57, `expo-updates`, EAS CLI, GitHub Actions (`workflow_dispatch`).

**Spec:** [docs/superpowers/specs/2026-09-29-ota-updates-design.md](../specs/2026-09-29-ota-updates-design.md)

## Global Constraints

- Update-check failures must be silent and non-blocking — no farmer-facing error, no retry loop, no crash (matches this project's "degrade, never fail" doctrine).
- The `production` channel is only ever updated via `eas channel:edit production --branch staging` (repointing, not republishing) — this is the manual safety gate and must never be automated.
- v1.6.0 (already released, no `expo-updates`) cannot receive OTA updates. This plan does not attempt to retrofit it.
- No code-signing for updates in this pass (spec §7, deliberate scope cut).
- Since APKs in this project are built locally (`expo prebuild` + `gradlew`, not `eas build` cloud), the EAS Update channel must be set via the `EXPO_UPDATES_CHANNEL` environment variable at `expo prebuild` time — `eas.json`'s `channel` field alone only binds for cloud (`eas build`) builds, and does not affect a local prebuild.

## Review Focus

- **First launch after publishing an update**: the update is downloading in the background: the app must show the *previous* bundle correctly, not a half-loaded blank screen — this is default `expo-updates` behavior, but the task's manual test must confirm it, not assume it.
- **Airplane mode / EAS service unreachable during the launch check**: must be indistinguishable from "no update available" to the farmer — no error banner, no delay to normal app usage (this is Module 51's own offline doctrine extended to a new subsystem).
- **A `staging` update published against a native module the current binary doesn't have**: `runtimeVersion` mismatch must mean the update is silently not offered, not a downloaded-then-crashes bundle — worth a deliberate note in the task, not just trusting Expo's default.
- **Running the app with `expo-updates` installed but in Expo Go / a dev-client session** (not a real standalone build): `Updates.checkForUpdateAsync()` throws in this environment by design (Expo Go doesn't support custom update servers) — the check function must not let that throw crash the app during normal local development.
- **A stale `staging` channel with an old test update sitting on it**: `eas channel:edit production --branch staging` promotes *whatever is currently on staging*, not necessarily the last thing Ritesh consciously tested — the task's own docs must say to verify what's actually on staging right before promoting, not trust memory.

---

### Task 1: Install and configure `expo-updates`

**Files:**
- Modify: `mobile/package.json` (new dependency)
- Modify: `mobile/app.json` (add `runtimeVersion`, `updates.url`)

**Interfaces:**
- Produces: the `expo-updates` native module and JS API (`Updates.checkForUpdateAsync()`, `Updates.fetchUpdateAsync()`, `Updates.reloadAsync()`), consumed by Task 2.

- [ ] **Step 1: Install the package**

Run: `cd mobile && npx expo install expo-updates`

This picks the SDK-57-compatible version automatically and adds it to `package.json`.

- [ ] **Step 2: Add runtime version policy and update URL to app.json**

Read `mobile/app.json` first to find the exact current `expo.extra.eas.projectId` value (confirmed present from an earlier EAS build: `68847f91-ef3a-429b-b3cb-d8398450af47` as of this writing — verify it's still that value before using it, project config can change). Add these two top-level keys inside the `"expo"` object, alongside the existing `"plugins"`/`"extra"` keys (not nested inside them):

```json
"runtimeVersion": { "policy": "appVersion" },
"updates": {
  "url": "https://u.expo.dev/68847f91-ef3a-429b-b3cb-d8398450af47"
}
```

- [ ] **Step 3: Verify the config is valid**

Run: `cd mobile && npx expo config --json | grep -A3 runtimeVersion`
Expected: prints the `runtimeVersion` object you just added, confirming `app.json` parses correctly and Expo's config resolver sees it.

- [ ] **Step 4: Commit**

```bash
git add mobile/package.json mobile/package-lock.json mobile/app.json
git commit -m "install and configure expo-updates for OTA update support"
```

---

### Task 2: Silent update-check on launch

**Files:**
- Create: `mobile/src/updates.ts`
- Modify: `mobile/App.tsx` (wire the check into the `App()` component)

**Interfaces:**
- Consumes: `expo-updates`'s `Updates` export (from Task 1).
- Produces: `checkForAppUpdate(): Promise<void>` — exported from `mobile/src/updates.ts`, called once from `App.tsx`.

- [ ] **Step 1: Create `mobile/src/updates.ts`**

```ts
import * as Updates from 'expo-updates';

/** Silent, non-blocking OTA update check -- called once on app launch.
 *  Never throws into the caller: a failed check (offline, EAS unreachable,
 *  or running in Expo Go / a dev-client session where custom update
 *  servers aren't supported) is exactly as unremarkable as "no update
 *  available" -- the app just keeps running on its current bundle,
 *  matching this project's degrade-never-fail doctrine. The downloaded
 *  update applies on the *next* app launch, per expo-updates' own
 *  default behavior -- this function never force-reloads mid-session. */
export async function checkForAppUpdate(): Promise<void> {
  if (!Updates.isEnabled) return; // Expo Go / dev-client / no update server configured
  try {
    const result = await Updates.checkForUpdateAsync();
    if (result.isAvailable) {
      await Updates.fetchUpdateAsync();
    }
  } catch {
    // Silent by design -- see doc comment above.
  }
}
```

- [ ] **Step 2: Wire it into `App.tsx`**

Read `mobile/App.tsx` lines 130-146 (the `export default function App()` component) in full first —
its exact current structure before editing. Add the import near the other `./src/*` imports
(alongside `logError` from `./src/errorLog`, line 53):

```ts
import { checkForAppUpdate } from './src/updates';
```

Add a `useEffect` inside `App()` that fires once on mount:

```tsx
export default function App() {
  useEffect(() => { checkForAppUpdate(); }, []);
  return (
    <ErrorBoundary>
      ...
```

(`useEffect` is already imported at the top of `App.tsx` per its existing import line 1 — confirm
before adding a duplicate import.)

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Verify it doesn't crash in the current dev workflow**

Run: `cd mobile && npx expo start` and open the app via the existing dev-client (per the project's
established Metro-dev-server workflow). Confirm the app launches normally and no error appears —
`Updates.isEnabled` will be `false` in this context (no production update server bundled into a
dev-client build), so `checkForAppUpdate()` should return immediately without attempting a check.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/updates.ts mobile/App.tsx
git commit -m "add silent, non-blocking OTA update check on app launch"
```

---

### Task 3: Channel configuration for staging and production builds

**Files:**
- Modify: `mobile/eas.json`
- Modify: `docs/TOOLING.md` (document the local-build channel-binding mechanism)

**Interfaces:**
- Consumes: nothing new.
- Produces: the `EXPO_UPDATES_CHANNEL` environment-variable convention that Task 5's live-proof
  and all future local production builds must follow — documented here so it isn't rediscovered
  or guessed at build time.

- [ ] **Step 1: Add channel fields to `eas.json`'s build profiles**

Edit `mobile/eas.json`, adding a `"channel"` key inside each of the `preview` and `production`
build profile objects (these fields matter if `eas build` cloud builds are ever used again, and
document intent even for local builds):

```json
{
  "cli": {
    "version": ">= 13.0.0",
    "appVersionSource": "local"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "preview": {
      "distribution": "internal",
      "channel": "staging",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "autoIncrement": true,
      "channel": "production"
    }
  },
  "submit": {
    "production": {}
  }
}
```

- [ ] **Step 2: Document the local-build channel mechanism in `docs/TOOLING.md`**

This project's actual release APKs are built locally (`expo prebuild` + `gradlew assembleRelease`
in a short-path worktree, established during Module 51's APK-size work), not via `eas build`
cloud. `eas.json`'s `channel` field above only takes effect for cloud builds — a local prebuild
needs the channel set via an environment variable instead. Read `docs/TOOLING.md` first to find
its existing structure/section conventions, then add a new section (e.g. after any existing
"Mobile app build" section, or as a new one if none exists) with this exact content:

```markdown
## OTA updates (EAS Update) -- local build channel binding

Release APKs are built locally, not via `eas build` cloud -- see the Module 51 APK-size work for
why (Windows path-length limits made cloud builds worth avoiding in favor of a short-path local
worktree). `eas.json`'s per-profile `"channel"` field only binds a channel for cloud builds. For
a local build to receive updates from the right EAS Update channel, set `EXPO_UPDATES_CHANNEL`
as an environment variable *before* running `expo prebuild` (it gets baked into the generated
native Android manifest at prebuild time -- setting it after prebuild has no effect):

```bash
# Personal test build (receives `staging` channel updates):
EXPO_UPDATES_CHANNEL=staging npx expo prebuild --platform android --clean

# Real public release build (receives `production` channel updates):
EXPO_UPDATES_CHANNEL=production npx expo prebuild --platform android --clean
```

Publishing an update:
```bash
eas update --branch staging --message "<what changed>"
```

Promoting an already-tested staging update to production (this is the manual safety gate --
never script this step):
```bash
# First, confirm what's actually on staging right now -- don't rely on memory:
eas channel:view staging

# Then, only if that's genuinely the update you just tested:
eas channel:edit production --branch staging
```
```

- [ ] **Step 3: Commit**

```bash
git add mobile/eas.json docs/TOOLING.md
git commit -m "configure staging/production EAS Update channels, document local-build channel binding"
```

---

### Task 4: `workflow_dispatch` GitHub Action to publish to staging

**Files:**
- Create: `.github/workflows/publish-update.yml`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (a standalone CI trigger), but only meaningful
  once Task 1-3 are in place (an `expo-updates`-less app has nothing for this to update).

- [ ] **Step 1: Check what EAS auth secret convention (if any) already exists in this repo's Actions secrets**

Run: `gh secret list --repo riteshbonthalakoti/agro-mirai` and check for an existing
`EXPO_TOKEN`-named secret. If none exists, this task cannot fully run until Ritesh generates one
at https://expo.dev/accounts/[account]/settings/access-tokens and runs
`gh secret set EXPO_TOKEN --repo riteshbonthalakoti/agro-mirai` himself (a human-auth step,
per this project's "nothing is hand-faked" rule -- do not attempt to generate this token
programmatically). Note this in the task's completion report regardless of whether the secret
already exists.

- [ ] **Step 2: Create the workflow**

```yaml
name: Publish OTA Update (staging)

on:
  workflow_dispatch:
    inputs:
      message:
        description: 'Update message (leave blank to auto-derive from the latest commit)'
        required: false

jobs:
  publish:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mobile
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - uses: expo/expo-github-action@v8
        with:
          eas-version: latest
          token: ${{ secrets.EXPO_TOKEN }}
      - name: Publish to staging channel
        run: |
          if [ -n "${{ github.event.inputs.message }}" ]; then
            eas update --branch staging --message "${{ github.event.inputs.message }}" --non-interactive
          else
            eas update --branch staging --auto --non-interactive
          fi
```

This is deliberately `workflow_dispatch`-only (manually triggered from the Actions tab or
`gh workflow run "Publish OTA Update (staging)"`) -- never `on: push`, matching the spec's
manual-gate requirement. It only ever publishes to `staging`; promoting to `production` stays
a local CLI command Ritesh runs himself (Task 3's documented `eas channel:edit`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish-update.yml
git commit -m "add manually-triggered GitHub Action to publish OTA updates to the staging channel"
```

---

### Task 5: Live-device verification (manual, no code changes)

**Files:** none modified -- this task is the spec's §6 proof, run against a real build and a
real EAS Update publish.

**Interfaces:** none.

- [ ] **Step 1: Build a `staging`-channel APK**

Following Task 3's documented convention, in a short-path worktree (per Module 51's established
pattern for local Android builds):
```bash
EXPO_UPDATES_CHANNEL=staging npx expo prebuild --platform android --clean
cd android && ./gradlew assembleRelease --no-daemon
```
Install the resulting APK on Ritesh's own phone.

- [ ] **Step 2: Publish a trivial, visually-confirmable test change to staging**

Make a small, obviously-visible temporary change (e.g., append " (OTA TEST)" to a screen title
in `mobile/src/screens/HomeTab.tsx`), commit it, then:
```bash
cd mobile && eas update --branch staging --message "OTA test: visible marker"
```

- [ ] **Step 3: Confirm the update applies on the second launch, not the first**

Force-close and reopen the app: confirm it still shows the *original* title (the update is
downloading in the background, per `expo-updates`' documented behavior). Force-close and reopen
a second time: confirm the "(OTA TEST)" marker now appears. This proves the real
download-then-apply-on-next-launch behavior, not a false positive from a fresh Metro/JS reload.

- [ ] **Step 4: Revert the test change and confirm it clears the same way**

Revert the temporary title change, commit, `eas update --branch staging --message "revert OTA
test marker"`, and repeat Step 3's two-launches check to confirm the marker disappears.

- [ ] **Step 5: Promote a real change to production (only once Steps 1-4 all pass)**

```bash
eas channel:view staging   # confirm what's actually on staging right now
eas channel:edit production --branch staging
```
Build and install a `production`-channel APK (`EXPO_UPDATES_CHANNEL=production npx expo
prebuild ...`) separately from the `staging` one used for testing, and confirm it receives the
same promoted update via the same two-launches check.

- [ ] **Step 6: Record results in `PROGRESS.md`**

Add a short section documenting: the real EAS Update branch/channel names, confirmation that the
two-launches update behavior was verified live (not assumed), and the exact commands from Task 3
as the permanent reference for future publishes. Commit:
```bash
git add PROGRESS.md
git commit -m "record OTA updates (EAS Update) setup and live-proof results"
```
