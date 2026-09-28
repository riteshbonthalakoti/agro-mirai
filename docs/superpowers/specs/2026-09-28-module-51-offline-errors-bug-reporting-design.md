# Module 51 — Offline-First Mode, Error Handling, Bug Reporting (Design)

Date: 2026-09-28
Status: approved for planning

## 1. Context and what already exists

Module 37 built the offline foundation the mobile app still runs on:

- `mobile/src/storage.ts` — `cacheGet`/`cacheSet` (namespaced, try/catch-wrapped so a
  corrupt/unavailable store degrades to "no cache", never throws), `clearFarmerCache`,
  `formatTime`.
- `mobile/src/hooks.ts` — `useLoad(cacheKey, fetchFn, deps)`: paints cached data
  immediately if present, then fetches fresh data; on success it replaces the data and
  re-caches it; on failure the cached copy is kept on screen and `error`/`fromCache` are
  both set so a screen can show "saved data" plus the real reason it's stale. This is
  already the right shape for the offline contract — it is not being replaced.
- `mobile/src/api.ts` — `ApiError` (`isNetwork` on any status-0/timeout failure),
  module-level `online` flag + `subscribeNet`/`isOnline`, derived from real request
  outcomes (no separate ping).
- `App.tsx` renders a single global `offlineBanner` when `isOnline()` is false.
- `POST /v2/bug-reports` (`sendBugReport` in `api.ts`) already exists and is wired to a
  working `MeTab.tsx` form: category (5 fixed values) + free-text message +
  `app_version` + `platform`, persisted to production's `bug_reports` table.

**The actual gap, confirmed by reading the code (not assumed):**

| Screen | Uses `useLoad` (cache-first) today? | Gap |
|---|---|---|
| Home (`HomeTab.tsx`) | Yes — crop/irrigation/disease all keyed `rec:`/`irr:`/`dis:` | No "last updated" label rendered anywhere; `formatTime` is defined but never called in any screen |
| Data (`DataTab.tsx`) | Yes | Same missing "last updated" label |
| Advice (`AdviceTab.tsx`) | **No** — imports `useLoad` but advisories are fetched with a bare `useEffect`/`getAdvisories` call, no cache key, no offline fallback | Advisory history and previously-played voice audio are not cached at all — a real Module 46/47 regression, exactly what the module brief predicted |
| Scan (`ScanTab.tsx`) | No — hand-rolled `cacheGet('scans')`/`cacheSet('scans')` for history + a separate `scanPhotos` cache | Works, but bypasses the shared pattern, has no "last updated" label, and the scan *action* itself (an image upload) needs its own explicit offline handling |
| Me (`MeTab.tsx`) | N/A (profile/fields come from `ctx.tsx`, not a screen-local `useLoad`) | Out of scope for data caching; the bug-report form here is the write-action surface |

Write actions that must fail honestly offline (add field, submit scan, request/verify
OTP, feedback, voice ask, bug report, admin writes) already throw a typed `ApiError`
with `isNetwork` true on network failure — the piece missing is a **single, consistently
worded** message shown for that case, not five different ad-hoc copies.

## 2. Design

### 2.1 Offline data contract — extend `useLoad`, don't replace it

`useLoad` already implements the correct cache-first/stale-while-erroring behavior.
Two additive changes, no rewrite:

1. Add a `lastUpdatedAt: number | null` field to `useLoad`'s return value, sourced from
   a stored `{ value, cachedAt }` envelope instead of the raw value (`cacheSet` wraps,
   `cacheGet` unwraps transparently — a one-time, backward-compatible format change
   inside `storage.ts`, since keys are versioned `agro:v2:` already and old un-enveloped
   entries simply miss-parse to `null` and refetch once).
2. Add one shared `<LastUpdated at={lastUpdatedAt} stale={!!error} />` component (new,
   small, in `ui.tsx`) that every screen using `useLoad` renders next to its cached
   content, using the existing `formatTime`.

Then, per-screen:

- **Advice tab**: replace the manual `getAdvisories` `useEffect` with
  `useLoad(id ? \`adv:${id}\` : null, () => getAdvisories(id!, false), [id])` for the
  history list (the `generate=true` "get today's advice" button stays a direct call —
  it's a write-shaped action, not a cached read, and already requires connectivity).
  Previously-played voice audio: cache the last-played advisory's audio blob URI per
  advisory id so "play again" works offline; recording a *new* voice answer stays
  online-only (already true).
- **Scan tab**: keep the existing `cacheGet('scans')`/`cacheSet('scans')` (it already
  works and predates `useLoad` for a reason — history is an accumulating list, not a
  single cached resource) but add the same enveloped-timestamp format and render
  `<LastUpdated>` next to it. The scan *submission* action gets the shared offline
  message (2.2) instead of whatever it currently shows on network failure.
- **Home/Data tabs**: no fetch-logic change — add the `<LastUpdated>` render only.
- **Me tab**: no data-caching change (profile/fields already load once via `ctx.tsx`
  at session start and don't need a staleness indicator for this module's scope).

Sync-on-reconnect: already exists — `subscribeNet` fires when a request succeeds after
being offline; screens that call `reload()` (from `useLoad`) on that transition get a
real refetch. This module wires that listener once, centrally (see 2.3), instead of
duplicating it per screen.

### 2.2 Shared error classification

New `mobile/src/errors.ts`:

```ts
export type ErrorKind = 'offline' | 'server' | 'validation' | 'unknown';

export function classifyError(e: unknown): { kind: ErrorKind; e: ApiError | null } {
  if (!(e instanceof ApiError)) return { kind: 'unknown', e: null };
  if (e.isNetwork) return { kind: 'offline', e };
  if (e.status === 422 || e.status === 400) return { kind: 'validation', e };
  if (e.status >= 500) return { kind: 'server', e };
  return { kind: 'unknown', e };
}
```

`hooks.ts`'s existing `errorText(t, e)` becomes the single place that turns a
classification into copy — it already handles most of this (network → `cantReachServer`,
5xx → `serverBusy`, 401 → `sessionExpired`); it gets one more branch: offline **write
attempts** (not reads) get a distinct, explicit string — Ritesh's own wording, `"You
have no internet. Connect to the internet and try again."` — added as a new i18n key
(`noInternetWrite`) in all four languages, and used at every write call site (`FieldForm`,
`ScanTab` submit, `Onboarding` OTP request/verify, `AdviceTab` feedback, `MeTab` bug
report and profile edits). Reads (the `useLoad` cache-first paths) keep showing cached
data with the existing `fromCache`/`error` combination — they should never show a blank
"no internet" screen when a cache hit exists.

Audit scope: every `catch` block across `mobile/src/screens/*.tsx` and
`mobile/src/components/*.tsx` that touches an `ApiError` is checked to confirm it routes
through `errorText`/`classifyError` rather than inlining its own message — this is a
mechanical audit-and-fix pass, not new architecture.

### 2.3 Crash/unexpected-error logging — local log, not Sentry

Decision: **do not add `sentry-react-native`** for this project. Reasoning: this is a
single-developer capstone running on a handful of demo/personal devices, not a
production app with a user base that needs remote, real-time crash triage — the value
Sentry adds (aggregation across many users' devices, release health, alerting) doesn't
apply here, and it's a new native dependency with its own build/config surface
(`app.json` plugin, native module linking) to maintain for a capstone timeline. Instead:

- New `mobile/src/errorLog.ts`: `logError(context: string, error: unknown)` appends a
  capped rolling log (last 50 entries: timestamp, context string, message, stack if
  present) to AsyncStorage via the existing `cacheGet`/`cacheSet` pattern — same
  never-throw guarantee.
- A top-level React error boundary (new, wraps the app's screen stack in `App.tsx`) calls
  `logError('boundary', error)` on any unexpected render crash and shows a "Something
  went wrong — restart the app" fallback instead of a blank white screen, which is the
  one unexpected-error case nothing currently handles.
- Every `catch` that falls through to `classifyError`'s `'unknown'` bucket also calls
  `logError(screenName, error)` before showing the generic fallback message.
- This log's last N entries are attached automatically to bug reports (2.4) — the actual
  payoff of logging locally instead of just swallowing errors: a farmer's bug report
  carries real diagnostic context without any third-party service.

### 2.4 Bug reporting — complete the existing flow, don't rebuild it

`POST /v2/bug-reports` and `MeTab.tsx`'s form already work end to end. Additions:

- **Context capture**: when the bug-report sheet is opened from a specific screen (e.g.
  a "Report a problem" affordance added to Home/Advice/Scan, not just buried in Me),
  pass the screen name and last action through as a new optional field in the existing
  submit payload (`category`, `message`, `app_version`, `platform` already sent) — e.g.
  `screen_context: string`. This is additive to the existing request shape, no backend
  schema change needed since `submit_bug_report`'s handler and the `bug_reports` table
  already store the payload as recorded (confirm exact column set before implementing —
  if `screen_context` has no column, this needs a one-line additive migration matching
  Module 50's `010_*.sql` pattern, decided at implementation time, not guessed here).
- **Recent error log attached**: the last 5 entries from `errorLog.ts`'s rolling log are
  serialized into the bug report's message/context automatically when present — gives
  "someone to act on it later" real signal beyond free text, per the module brief.
- **Screenshot**: out of scope for this pass — Module 51's brief says "if practical";
  React Native screenshot capture of the *current* screen from within a modal sheet is
  non-trivial (needs `react-native-view-shot` or similar, another native dependency) and
  the context + error log already covers the "enough to act on" bar without it. Recorded
  as a known limitation, not silently dropped.
- **Offline behavior: ask-to-retry, not queue-and-send.** Consistent with every other
  write action in this app's existing offline contract (OTP, add field, feedback are all
  ask-to-retry today, not queued) — a local queue adds real complexity (persistence
  format, dedup on flush, partial-failure UI, a second sync path parallel to `useLoad`'s
  reconnect-refetch) that this capstone's scale doesn't justify for a form a farmer can
  reasonably resubmit once back online. The bug-report submit button, when offline,
  shows the same `noInternetWrite` message as every other write action rather than a
  bespoke queued-submission flow.

## 3. Testing / live-proof plan

Per the module brief's required handoff format:

1. **Offline read proof**: real device, real farmer account with prior synced data.
   Airplane mode on (mobile data confirmed off, not just Wi-Fi). Force-close, reopen.
   Screenshot every tab showing cached data + a real "last updated" timestamp, no blank
   screens, no infinite spinners.
2. **Offline write proof**: attempt add-field, scan submit, OTP request, feedback, bug
   report while offline. Screenshot at least two showing the exact `noInternetWrite`
   message, not a crash or silent no-op.
3. **Reconnect proof**: network back on, confirm affected screens refresh without a
   reinstall or manual cache clear (via the existing `subscribeNet` → `reload()` wiring).
4. **Error pipeline proof**: force one server error (e.g. malformed request) and confirm
   consistent copy via `errorText`; force one unexpected error path and confirm the error
   boundary's fallback screen appears and `errorLog.ts` captured it.
5. **Bug report live proof**: submit one real bug report through the app (not burning
   Sarvam voice quota, per the module's "what not to do"), confirm it lands in the real
   production `bug_reports` table with `screen_context` and the attached recent-error
   context populated.

## 4. Known limitations (stated up front, not discovered later)

- No screenshot attachment on bug reports (see 2.4).
- Error log is local-only, capped at 50 entries, cleared on `clearFarmerCache` (sign-out)
  by the same "belongs to that farmer" logic already governing other cached data —
  acceptable since bug reports carry the relevant slice at submit time.
- Ask-to-retry (not queue-and-send) means a bug report attempted offline is lost if the
  farmer doesn't manually resubmit — an explicit, justified trade-off, not an oversight.
- This spec does not touch the three backend blockers (voice/Sarvam 503s, OTP/SMS,
  Supabase migration-ledger drift) noted in `PROGRESS.md`'s Module 51 starting-state
  audit — they are not part of this module's brief (`module-51-offline-errors-bug-reporting.md`
  only scopes offline/errors/bug-reporting) and are explicitly out of scope here.

## 5. Files touched (expected)

- `mobile/src/storage.ts` — enveloped cache format (value + cachedAt), backward-compatible
- `mobile/src/hooks.ts` — `useLoad` gains `lastUpdatedAt`
- `mobile/src/errors.ts` — new, `classifyError`
- `mobile/src/errorLog.ts` — new, rolling local error log
- `mobile/src/ui.tsx` — new `<LastUpdated>` component
- `mobile/src/i18n.ts` — new `noInternetWrite` key, 4 languages
- `mobile/App.tsx` — top-level error boundary
- `mobile/src/screens/AdviceTab.tsx` — advisories through `useLoad`, cached voice replay
- `mobile/src/screens/ScanTab.tsx` — enveloped timestamps, `<LastUpdated>`, offline submit message
- `mobile/src/screens/HomeTab.tsx`, `DataTab.tsx` — `<LastUpdated>` render only
- `mobile/src/screens/MeTab.tsx`, `FieldForm.tsx`, `Onboarding.tsx` — route through `classifyError`/`errorText`, bug-report context + error-log attachment
- Possible additive backend migration for `screen_context` on `bug_reports` (decided at implementation time per confirmed current schema)
