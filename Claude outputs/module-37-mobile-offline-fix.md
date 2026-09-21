# MODULE 37 — Mobile app: fix the offline blank-screen failure, add real local persistence

Continuing AGRO MIRAI. This module is mobile-app-only. Don't touch the
backend, notebooks, admin dashboard, or landing page here — those are
separate modules (36 closed, 38 is the admin dashboard).

Confirmed real, reported directly by Ritesh: with the backend laptop
fully off, opening the installed app on a real phone shows a totally
blank white screen — no login screen, no cached data, nothing at all.
For a real product this is disqualifying, and it's also an easy tell to
anyone reviewing the app that nothing was engineered defensively. Fix it
properly, not with a patch that just avoids the crash.

## 1. Root-cause the blank screen first

- Find the exact failing call. This is very likely an unhandled promise
  rejection or a render-blocking `await` at app startup (a session
  check, an initial data fetch, a config/health call) that throws with no
  try/catch/fallback and takes the whole render tree down with it.
- Confirm precisely which startup call(s) do this — read the actual
  startup/bootstrap sequence in `App.tsx`, don't guess.
- Reproduce it locally first (kill the backend, cold-launch the app,
  confirm you see the same blank screen) before fixing anything, so the
  fix can be verified against a real repro, not assumed to work.

## 2. Fix the crash — app must always render something

- Wrap every startup network call in proper error handling with a real
  fallback path. The app should never silently hang or crash on launch
  regardless of network state.
- If there's no cached session/data yet (a genuinely fresh install with
  no prior successful launch), the honest fallback is the login screen
  with a clear "can't reach server" state if a request fails — not a
  blank screen, not a fake "everything's fine" look either.

## 3. Build real local persistence (the actual fix, not just crash-proofing)

- Cache the farmer's session/auth state locally so a returning user
  doesn't need to re-login every time the app opens with no network.
- Cache the farmer's fields, and their most recent advisories/scan
  results/records, locally on the device — use `AsyncStorage` for small
  key-value state (session, preferences) and `expo-sqlite` (or an
  equivalent structured store) for the actual records if the data shape
  warrants it. State clearly which you used for what and why.
- When opening offline, the app should show this real, previously-synced
  data — clearly labeled with a "last updated <time>" indicator so the
  farmer knows it might be stale, never presented as if it were live.
- Define and implement the offline contract precisely and consistently
  across the app:
  - **Works fully offline**: viewing cached fields, cached
    advisories/records, cached scan history, browsing anything already
    fetched before.
  - **Requires connection, must fail honestly**: submitting a new disease
    scan, adding a field, requesting an OTP, any write that needs the
    server. These should show a clear, specific "you're offline, connect
    to do this" state — never a silent no-op, never an infinite spinner,
    never a crash.
- Sync behavior: when the app regains connectivity, it should refresh
  cached data in the background (reuse the tab-switch/pull-to-refresh
  refetch logic already built in Module 34, don't build a second sync
  mechanism) rather than requiring a manual action every time.

## 4. Prove it live

- Real device, real farmer account with real prior data already synced.
- Turn off the laptop/backend entirely (not just disconnect Wi-Fi —
  actually stop the process, to rule out any silent localhost fallback).
- Force-close and reopen the app.
- Confirm it opens straight into a real, useful offline view — showing
  real cached fields/records, not a blank screen and not a stuck spinner.
  Screenshot it.
- Try a write action (e.g. tap "Add a field" or attempt a scan) while
  still offline and confirm it shows the honest offline-blocked state,
  not a crash or a silent failure.
- Turn the backend back on, confirm the app picks up connectivity and
  syncs/refreshes without needing a reinstall or manual cache clear.

## What NOT to do

- No backend changes.
- No admin dashboard work (Module 38).
- No landing page or notebook changes.
- No UI redesign beyond what's needed to show the "offline"/"last
  updated" states honestly — reuse existing components and the toast/
  notification system already built, don't restyle anything.

## Handoff format

```
Module: 37 — Mobile offline fix
Status: complete | blocked | needs-decision

Root cause: <exact failing call, confirmed by reproducing it>
Crash fix: <what changed, files>
Local persistence: <AsyncStorage vs SQLite, what's cached, why>
Offline contract: <works offline vs. requires connection, per feature>
Sync-on-reconnect: <confirmed reuses existing refetch logic>

Live proof:
  Offline open with real cached data: <real device, real screenshot>
  Offline write attempt (honest blocked state): <real screenshot>
  Reconnect + resync: <confirmed>

Known limitations:
Next recommended step:
```
