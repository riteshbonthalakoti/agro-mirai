# Module 51 — Offline-First Mode, Error Handling, Bug Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every screen in the AGRO MIRAI mobile app show its most recent cached data with an honest "last updated" timestamp when offline, give every write action a single consistently-worded "no internet" failure message, add a local rolling error log + top-level crash boundary instead of a third-party crash service, and complete the existing bug-report flow with screen context, recent-error attachment, and a photo.

**Architecture:** Extend the existing `useLoad` cache-first hook (Module 37) rather than replacing it; add one shared error-classification module consumed by every screen's catch block; add a local AsyncStorage-backed rolling error log instead of Sentry; fold bug-report context into the existing free-text `message` field (no backend schema change needed — `_MAX_BUG_MESSAGE_LEN` is 2000 chars, plenty of room).

**Tech Stack:** React Native 0.86 / Expo 57 / TypeScript 6, `@react-native-async-storage/async-storage`. No test framework exists in `mobile/` (no jest, no devDependency for it) — verification is `npx tsc --noEmit` (the project's only existing automated gate for this app) plus the live-device proof steps in Task 9, matching how this app has always been verified.

**Spec:** [`docs/superpowers/specs/2026-09-28-module-51-offline-errors-bug-reporting-design.md`](../specs/2026-09-28-module-51-offline-errors-bug-reporting-design.md)

**Deviations from the spec, decided during planning (both narrow the diff, not widen it):**
1. Spec section 2.4 left "screen_context needs an additive migration or not" undecided pending implementation. Confirmed: `_MAX_BUG_MESSAGE_LEN = 2000` in `src/agro_mirai/api/value_endpoints.py:48` — screen context and the recent-error-log excerpt are prepended into the existing `message` field with a `[Screen: X]` / `[Recent errors]` delimiter instead of adding a new column. Zero backend changes, no migration, no deploy.
2. Spec section 2.4 marked a bug-report screenshot "out of scope" assuming a new native dependency. Confirmed `expo-image-picker` is already installed and already used for the profile-photo picker in `MeTab.tsx:80-86`, and the backend already accepts `photo_url` (base64 data URI, capped at `_MAX_BUG_PHOTO_DATA_URI_LEN`). Task 8 adds a "attach a photo" button to the bug-report form reusing that exact pattern — genuinely cheap now that the infra is confirmed to exist, so it's included.

## Global Constraints

- No `Co-Authored-By: Claude` or any AI-attribution trailer in any commit (repo-wide locked rule).
- Additive-only: this plan makes zero backend/schema changes (see deviation 1 above) — if a task's implementer discovers one is genuinely required, stop and flag it rather than improvising a migration.
- `cacheGet`/`cacheSet` must never throw into the render tree — every new storage helper follows the same try/catch-degrade-to-null pattern already in `storage.ts`.
- All 4 languages (`en`, `kn`, `te`, `hi`) — any new i18n key must be added to all four dict blocks in `mobile/src/i18n.ts` or `Dict` won't compile (TypeScript enforces this: English is the source of truth type).
- Ask-to-retry, not queue-and-send, for offline bug reports (spec 2.4) — do not build a local submission queue.
- Do not add `sentry-react-native` or any other third-party crash-reporting dependency (spec 2.3).
- Never burn Sarvam voice quota while testing (module brief's explicit "what not to do").

## Review Focus

- A screen with **no cache entry yet** (first-ever launch, never been online) going offline — must show an honest empty/first-time state, not a crash from `formatTime(null)` or `<LastUpdated>` rendering garbage.
- **Rapid online/offline flapping** (a farmer walking in and out of signal) — `subscribeNet` listeners firing repeatedly must not cause duplicate in-flight fetches or stuck `loading` state in `useLoad`.
- **A cached value written under the old (pre-envelope) format** read by the new enveloped `cacheGet` — must miss cleanly and refetch, never throw or render `[object Object]`.
- **Bug report submitted with no category and no message, only a photo** — the existing backend rule (`category is None and not message` → 400) must still surface as a clear validation error in the UI, not a silent failure, once the photo/context fields are added to the payload.
- **The error boundary itself throwing** (e.g. `logError` failing inside the boundary's `componentDidCatch`) — must not produce a second crash; `logError` already degrades silently by the same try/catch pattern as `cacheSet`, so the boundary's fallback UI must render even if logging fails.

---

## File Structure

| File | Responsibility |
|---|---|
| `mobile/src/storage.ts` (modify) | Enveloped `{ value, cachedAt }` cache format, backward-compatible read |
| `mobile/src/hooks.ts` (modify) | `useLoad` exposes `lastUpdatedAt` |
| `mobile/src/ui.tsx` (modify) | New `<LastUpdated>` component |
| `mobile/src/i18n.ts` (modify) | New keys: `lastUpdated`, `neverSynced`, `noInternetWrite` (4 languages each) |
| `mobile/src/errors.ts` (create) | `classifyError(e)` — pure function, no UI |
| `mobile/src/hooks.ts` (modify) | `errorText` gains a `write` flag to select `noInternetWrite` vs `cantReachServer` |
| `mobile/src/errorLog.ts` (create) | `logError(context, error)`, `getRecentErrors(n)`, rolling cap at 50 |
| `mobile/App.tsx` (modify) | Top-level `ErrorBoundary` class component wraps the main-phase screen stack |
| `mobile/src/screens/AdviceTab.tsx` (modify) | Advisories list through `useLoad`; cached voice-replay URI |
| `mobile/src/screens/ScanTab.tsx` (modify) | Enveloped timestamp, `<LastUpdated>`, offline submit message |
| `mobile/src/screens/HomeTab.tsx`, `DataTab.tsx` (modify) | `<LastUpdated>` render only |
| `mobile/src/screens/MeTab.tsx` (modify) | Bug-report form: screen-context param, recent-error attachment, photo attach, offline ask-to-retry message |
| `mobile/src/screens/FieldForm.tsx`, `Onboarding.tsx` (modify) | Route write-action catches through `classifyError`/`errorText(t, e, {write:true})` |

---

### Task 1: Enveloped cache format + `useLoad.lastUpdatedAt`

**Files:**
- Modify: `mobile/src/storage.ts`
- Modify: `mobile/src/hooks.ts:11-54` (`useLoad`)

**Interfaces:**
- Produces: `cacheGet<T>(key): Promise<T | null>` (signature unchanged — callers don't know about the envelope), `cacheGetWithTime<T>(key): Promise<{ value: T; cachedAt: number } | null>` (new, used only by `useLoad`), `cacheSet(key, value): Promise<void>` (unchanged signature, now writes the envelope internally).
- Consumes: nothing new.

- [ ] **Step 1: Rewrite `cacheGet`/`cacheSet` to use an internal envelope, keep the public signatures**

Edit `mobile/src/storage.ts`:

```ts
import AsyncStorage from '@react-native-async-storage/async-storage';

const P = 'agro:v2:';

type Envelope<T> = { v: T; t: number };

function isEnvelope(x: unknown): x is Envelope<unknown> {
  return !!x && typeof x === 'object' && 't' in (x as any) && 'v' in (x as any) && typeof (x as any).t === 'number';
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(P + key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return isEnvelope(parsed) ? (parsed.v as T) : (parsed as T); // pre-envelope entries: return as-is once, next cacheSet re-wraps them
  } catch {
    return null;
  }
}

/** Same as cacheGet but also returns when it was written. Old (un-enveloped)
 *  entries have no timestamp, so they read as a cache miss here -- the
 *  screen refetches once and the entry is enveloped from then on. */
export async function cacheGetWithTime<T>(key: string): Promise<{ value: T; cachedAt: number } | null> {
  try {
    const raw = await AsyncStorage.getItem(P + key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!isEnvelope(parsed)) return null;
    return { value: parsed.v as T, cachedAt: parsed.t };
  } catch {
    return null;
  }
}

export async function cacheSet(key: string, value: unknown): Promise<void> {
  try {
    const envelope: Envelope<unknown> = { v: value, t: Date.now() };
    await AsyncStorage.setItem(P + key, JSON.stringify(envelope));
  } catch {
    // best effort
  }
}

export async function clearFarmerCache(): Promise<void> {
  try {
    const keys = await AsyncStorage.getAllKeys();
    const mine = keys.filter((k) => k.startsWith(P) && !['lang', 'permsAsked', 'tourSeen'].some((d) => k === P + d));
    if (mine.length) await AsyncStorage.multiRemove(mine);
  } catch {
    // ignore
  }
}

export function formatTime(ts: number | string | null | undefined): string {
  if (!ts) return '';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return String(ts);
  const now = new Date();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === now.toDateString()
    ? time
    : `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })}, ${time}`;
}
```

- [ ] **Step 2: Add `lastUpdatedAt` to `useLoad`**

Edit `mobile/src/hooks.ts`, replace the `useLoad` function (lines 11-54) with:

```ts
export type Load<T> = { data: T | null; error: ApiError | null; loading: boolean; fromCache: boolean; lastUpdatedAt: number | null; reload: () => void };

export function useLoad<T>(cacheKey: string | null, fn: () => Promise<T>, deps: unknown[]): Load<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [fromCache, setFromCache] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      setData(null);
      setFromCache(false);
      if (cacheKey) {
        const cached = await cacheGetWithTime<T>(cacheKey);
        if (alive && cached) {
          setData(cached.value);
          setFromCache(true);
          setLastUpdatedAt(cached.cachedAt);
        }
      }
      try {
        const fresh = await fnRef.current();
        if (!alive) return;
        setData(fresh);
        setFromCache(false);
        if (cacheKey) {
          await cacheSet(cacheKey, fresh);
          setLastUpdatedAt(Date.now());
        }
      } catch (e) {
        if (alive) setError(e instanceof ApiError ? e : new ApiError(0, String(e)));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((x) => x + 1), []);
  return { data, error, loading, fromCache, lastUpdatedAt, reload };
}
```

Also update the import line at the top of `hooks.ts` from `import { cacheGet, cacheSet } from './storage';` to `import { cacheGet, cacheGetWithTime, cacheSet } from './storage';`.

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no new errors (existing callers of `useLoad` destructure a subset of the returned object, which TypeScript allows — `lastUpdatedAt` being unused by them is not an error).

- [ ] **Step 4: Commit**

```bash
git add mobile/src/storage.ts mobile/src/hooks.ts
git commit -m "mobile: enveloped cache format with timestamps, useLoad exposes lastUpdatedAt"
```

---

### Task 2: `<LastUpdated>` component, wired into Home/Data tabs

**Files:**
- Modify: `mobile/src/ui.tsx`
- Modify: `mobile/src/i18n.ts` (add `lastUpdated`, `neverSynced` to all 4 language blocks)
- Modify: `mobile/src/screens/HomeTab.tsx`
- Modify: `mobile/src/screens/DataTab.tsx`

**Interfaces:**
- Consumes: `Load.lastUpdatedAt` from Task 1, `formatTime` from `storage.ts`.
- Produces: `<LastUpdated at={number|null} stale={boolean} t={(k:Key)=>string} />` — exported from `ui.tsx`, used by Tasks 2, 6, 7.

- [ ] **Step 1: Add the component to `ui.tsx`**

Append to `mobile/src/ui.tsx` (after the `Banner` function, same file, keep the existing `import { C, S } from './theme'`):

```ts
import { formatTime } from './storage';
import { Key } from './i18n';

/** Small, muted "last updated <time>" label for a useLoad-backed screen.
 *  `at === null` (never successfully cached) shows `neverSynced` instead
 *  of a blank/garbage time. `stale` (the last fetch attempt errored, so
 *  what's shown is not fresh) dims it further via the `warn` color. */
export function LastUpdated({ at, stale, t }: { at: number | null; stale: boolean; t: (k: Key) => string }) {
  return (
    <Text style={[st.muted, { fontSize: 11 }, stale ? { color: C.warn } : null]}>
      {at ? `${t('lastUpdated')} ${formatTime(at)}` : t('neverSynced')}
    </Text>
  );
}
```

- [ ] **Step 2: Add i18n keys**

Edit `mobile/src/i18n.ts`. Add to the `en` block (near `offlineBanner`, line 40):
```ts
  lastUpdated: 'Last updated',
  neverSynced: 'Not synced yet',
```
Add the matching pair to the `kn`, `te`, `hi` blocks (each dict block mirrors `en`'s keys at the corresponding position — find each block's `offlineBanner:` line and add the two keys directly after it, same as `en`):
```ts
  // kn
  lastUpdated: 'ಕೊನೆಯದಾಗಿ ನವೀಕರಿಸಲಾಗಿದೆ',
  neverSynced: 'ಇನ್ನೂ ಸಿಂಕ್ ಆಗಿಲ್ಲ',
  // te
  lastUpdated: 'చివరిగా నవీకరించబడింది',
  neverSynced: 'ఇంకా సింక్ కాలేదు',
  // hi
  lastUpdated: 'आखिरी बार अपडेट किया गया',
  neverSynced: 'अभी तक सिंक नहीं हुआ',
```

- [ ] **Step 3: Render in HomeTab**

In `mobile/src/screens/HomeTab.tsx`, the three `useLoad` calls are at lines 110-112 (`crop`, `irr`, `dis`). Add `import { LastUpdated } from '../ui';` (merge into the existing `ui` import if one exists — check the top of the file first) and render one `<LastUpdated at={crop.lastUpdatedAt} stale={!!crop.error} t={t} />` near the crop card's header, one for `irr` near the irrigation card, one for `dis` near the disease card — each placed directly under that card's title `Text`, matching how `Card`'s `right` slot or an inline `<View>` is already used elsewhere in the file (follow the existing card layout, don't restructure it).

- [ ] **Step 4: Render in DataTab**

Same pattern in `mobile/src/screens/DataTab.tsx`: find its `useLoad` call(s) (weather/soil/NDVI data-summary), render one `<LastUpdated>` near the top of the data card using that load's `lastUpdatedAt`/`error`.

- [ ] **Step 5: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add mobile/src/ui.tsx mobile/src/i18n.ts mobile/src/screens/HomeTab.tsx mobile/src/screens/DataTab.tsx
git commit -m "mobile: add LastUpdated label to Home and Data tabs"
```

---

### Task 3: Shared error classifier + offline-write message

**Files:**
- Create: `mobile/src/errors.ts`
- Modify: `mobile/src/hooks.ts` (`errorText`)
- Modify: `mobile/src/i18n.ts` (add `noInternetWrite` to all 4 language blocks)

**Interfaces:**
- Consumes: `ApiError` from `mobile/src/api.ts` (unchanged).
- Produces: `classifyError(e: unknown): { kind: 'offline'|'server'|'validation'|'unknown'; e: ApiError | null }` — used by Tasks 4, 6, 7, 8. `errorText(t, e, opts?: { write?: boolean }): string` — existing signature gains an optional third parameter, so every existing call site (`errorText(t, e)`) keeps compiling unchanged.

- [ ] **Step 1: Create `errors.ts`**

```ts
import { ApiError } from './api';

export type ErrorKind = 'offline' | 'server' | 'validation' | 'unknown';

/** One place that turns any caught value into a kind. Pure -- no i18n, no
 *  UI. `errorText` (hooks.ts) turns a kind into copy; `logError`
 *  (errorLog.ts) uses this to decide whether an error is worth logging
 *  (offline/validation are expected user-facing outcomes, not bugs). */
export function classifyError(err: unknown): { kind: ErrorKind; e: ApiError | null } {
  if (!(err instanceof ApiError)) return { kind: 'unknown', e: null };
  if (err.isNetwork) return { kind: 'offline', e: err };
  if (err.status === 400 || err.status === 422) return { kind: 'validation', e: err };
  if (err.status >= 500) return { kind: 'server', e: err };
  return { kind: 'unknown', e: err };
}
```

- [ ] **Step 2: Extend `errorText` in `hooks.ts`**

Replace the existing `errorText` function (`mobile/src/hooks.ts:56-67`) with:

```ts
/** Human message for an ApiError, localized where the backend gives a stable code.
 *  `opts.write: true` is for a write action (add field, submit scan, OTP, feedback,
 *  bug report) failing on a network error -- those get the explicit
 *  "you have no internet" instruction instead of the softer read-path copy,
 *  per the offline contract: reads fall back to cached data silently, writes
 *  must never fail silently. */
export function errorText(t: (k: Key) => string, e: ApiError | null, opts?: { write?: boolean }): string {
  if (!e) return '';
  if (e.isNetwork) return opts?.write ? t('noInternetWrite') : t('cantReachServer');
  if (e.code === 'NO_WEATHER_DATA') return t('noWeatherData');
  if (e.code === 'INSUFFICIENT_DATA') return t('insufficientData');
  if (e.status === 401) return t('sessionExpired');
  if (e.status === 429) return t('tooManyRequests');
  if (e.status >= 500) return t('serverBusy');
  return e.message || t('genericError');
}
```

- [ ] **Step 3: Add the i18n key**

Add to `en` block: `noInternetWrite: 'You have no internet. Connect to the internet and try again.',`
Add matching translations to `kn`/`te`/`hi` blocks:
```ts
  // kn
  noInternetWrite: 'ನಿಮಗೆ ಇಂಟರ್ನೆಟ್ ಇಲ್ಲ. ಇಂಟರ್ನೆಟ್‌ಗೆ ಸಂಪರ್ಕಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  // te
  noInternetWrite: 'మీకు ఇంటర్నెట్ లేదు. ఇంటర్నెట్‌కు కనెక్ట్ చేసి మళ్లీ ప్రయత్నించండి.',
  // hi
  noInternetWrite: 'आपके पास इंटरनेट नहीं है। इंटरनेट से जुड़ें और फिर से कोशिश करें।',
```

- [ ] **Step 4: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors — every existing `errorText(t, e)` call site still matches the (now 2-required/1-optional-parameter) signature.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/errors.ts mobile/src/hooks.ts mobile/src/i18n.ts
git commit -m "mobile: add classifyError and a distinct offline-write error message"
```

---

### Task 4: Local rolling error log + top-level error boundary

**Files:**
- Create: `mobile/src/errorLog.ts`
- Modify: `mobile/App.tsx`

**Interfaces:**
- Consumes: `cacheGet`/`cacheSet` from `storage.ts` (Task 1's envelope format is transparent to this — `errorLog.ts` stores a plain array as its `value`, same as any other cached value).
- Produces: `logError(context: string, error: unknown): Promise<void>`, `getRecentErrors(n?: number): Promise<LoggedError[]>` — `getRecentErrors` is consumed by Task 8 (bug report attachment). `LoggedError = { at: number; context: string; message: string; stack?: string }`.

- [ ] **Step 1: Create `errorLog.ts`**

```ts
import { cacheGet, cacheSet } from './storage';

export type LoggedError = { at: number; context: string; message: string; stack?: string };

const KEY = 'errorLog';
const CAP = 50;

/** Rolling local log of unexpected errors, capped at CAP entries (oldest
 *  dropped first). Never throws -- same degrade-silently contract as
 *  cacheSet, since a logging failure must never mask the original error
 *  or crash the error boundary that's calling this. Cleared on sign-out
 *  by clearFarmerCache (this key is not in its keep-list). */
export async function logError(context: string, error: unknown): Promise<void> {
  try {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;
    const existing = (await cacheGet<LoggedError[]>(KEY)) || [];
    const next = [{ at: Date.now(), context, message, stack }, ...existing].slice(0, CAP);
    await cacheSet(KEY, next);
  } catch {
    // logging must never throw
  }
}

export async function getRecentErrors(n = 5): Promise<LoggedError[]> {
  try {
    const all = (await cacheGet<LoggedError[]>(KEY)) || [];
    return all.slice(0, n);
  } catch {
    return [];
  }
}
```

- [ ] **Step 2: Add an error boundary to `App.tsx`**

Read `mobile/App.tsx` in full first to find its imports and the component that renders the main-phase screen stack (the `return (...)` block containing `<AppCtx.Provider>`, around line 351-370 per the file read during planning). Add near the top of the file, after the existing imports:

```tsx
import { logError } from './src/errorLog';

class ErrorBoundary extends React.Component<{ t: (k: Key) => string; children: React.ReactNode }, { crashed: boolean }> {
  constructor(props: { t: (k: Key) => string; children: React.ReactNode }) {
    super(props);
    this.state = { crashed: false };
  }
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  componentDidCatch(error: Error) {
    logError('boundary', error);
  }
  render() {
    if (this.state.crashed) {
      return (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: S.lg, backgroundColor: C.bg }}>
          <Text style={{ fontSize: 16, fontWeight: '700', color: C.text, textAlign: 'center' }}>{this.props.t('crashedTitle')}</Text>
          <Text style={{ fontSize: 13, color: C.muted, textAlign: 'center', marginTop: S.sm }}>{this.props.t('crashedBody')}</Text>
        </View>
      );
    }
    return this.props.children;
  }
}
```

(`Key`, `C`, `S`, `View`, `Text` are already imported in `App.tsx` — confirm each is present in the existing import list; add any missing one to the existing import statements rather than a new import line.)

Wrap the `<AppCtx.Provider>` block's children (the `View` starting at the line found during the read, currently `{!online ? <Banner .../> : null} {form ? (...) : ...}`) in `<ErrorBoundary t={t}>...</ErrorBoundary>`, keeping everything else inside unchanged.

- [ ] **Step 3: Add the two new i18n keys**

Add to `en`: `crashedTitle: 'Something went wrong', crashedBody: 'Please restart the app. If this keeps happening, use "Report a problem" in the Me tab.',`
Add matching `kn`/`te`/`hi` translations following the same pattern as Task 2/3's additions.

- [ ] **Step 4: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/errorLog.ts mobile/App.tsx mobile/src/i18n.ts
git commit -m "mobile: local rolling error log and top-level crash boundary"
```

---

### Task 5: Route every write-action catch through `classifyError`/`errorText`

**Files:**
- Modify: `mobile/src/screens/FieldForm.tsx`
- Modify: `mobile/src/screens/Onboarding.tsx`
- Modify: `mobile/src/screens/AdviceTab.tsx` (feedback submit only — advisory-list caching is Task 6)
- Modify: `mobile/src/screens/MeTab.tsx` (profile-edit and delete-field catches only — bug-report form is Task 8)

**Interfaces:**
- Consumes: `errorText(t, e, { write: true })` from Task 3, `classifyError` from Task 3, `logError` from Task 4.

- [ ] **Step 1: Audit every `catch` block in these four files**

For each `catch (e) { ... }` that currently sets an error-message state (e.g. the `setErr(errorText(t, e as ApiError))` pattern already visible in `MeTab.tsx:105`), change it to pass `{ write: true }`:

```ts
} catch (e) { setErr(errorText(t, e as ApiError, { write: true })); }
```

This applies to: `FieldForm.tsx`'s submit handler, `Onboarding.tsx`'s OTP request and verify handlers, `AdviceTab.tsx`'s `sendFeedback` catch, `MeTab.tsx`'s `deleteField`/`patchMe` catches. Grep each file for `errorText(t,` to find every call site before editing, so none are missed.

- [ ] **Step 2: Log unknown-kind errors**

For each of the same catch blocks, add a call to `classifyError`/`logError` when the kind is `'unknown'` (an error that isn't a recognized `ApiError` shape at all — genuinely unexpected), e.g.:

```ts
} catch (e) {
  const { kind } = classifyError(e);
  if (kind === 'unknown') logError('FieldForm.submit', e);
  setErr(errorText(t, e as ApiError, { write: true }));
}
```

Import `classifyError` from `../errors` and `logError` from `../errorLog` in each of the four files.

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/screens/FieldForm.tsx mobile/src/screens/Onboarding.tsx mobile/src/screens/AdviceTab.tsx mobile/src/screens/MeTab.tsx
git commit -m "mobile: route write-action errors through classifyError/errorText consistently"
```

---

### Task 6: AdviceTab advisories through `useLoad`; cached voice replay

**Files:**
- Modify: `mobile/src/screens/AdviceTab.tsx`

**Interfaces:**
- Consumes: `useLoad` (Task 1), `<LastUpdated>` (Task 2), `cacheGet`/`cacheSet` (Task 1).
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Read the current advisories-fetch code**

Read `mobile/src/screens/AdviceTab.tsx` lines 280-320 (the `getAdvisories(id, false)` call found during planning at line 291, and the `generate` call at line 309) in full before editing, to see the exact state variables involved (`advisories`, `loading`, etc.) and preserve every other behavior (pull-to-refresh, the "Get today's advice" button) unchanged.

- [ ] **Step 2: Replace the manual fetch with `useLoad` for the read path**

Replace the `useEffect`/manual-fetch block that calls `getAdvisories(id, false)` with:

```ts
const advList = useLoad(id ? `adv:${id}` : null, () => getAdvisories(id!, false), [id]);
```

Keep the existing `generate=true` button's direct `getAdvisories(id, true)` call as-is (it's a write-shaped action already correctly requiring connectivity per the spec) — after it succeeds, call `advList.reload()` so the newly generated advisory shows up in the now-`useLoad`-backed list without a full remount. Update the rendering code that previously read from the manual `advisories`/`loading` state to read from `advList.data`/`advList.loading`/`advList.fromCache` instead — keep the JSX structure, only change the data source.

- [ ] **Step 3: Render `<LastUpdated>`**

Add `<LastUpdated at={advList.lastUpdatedAt} stale={!!advList.error} t={t} />` near the top of the advisories list section.

- [ ] **Step 4: Cache the last-played voice audio per advisory**

Find where advisory audio playback is triggered (search the file for `advisoryAudioUrl` or the audio-play handler). When a play succeeds online, cache the advisory id → audio source under a `voice:${advisoryId}` key via `cacheSet`. When "play" is tapped and `isOnline()` (imported from `../api`) is false, check `cacheGet<string>(`voice:${advisoryId}`)` first — if present, play that cached reference; if not, show `errorText(t, new ApiError(0, 'offline'), { write: true })` via a toast/banner instead of attempting the network call.

- [ ] **Step 5: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add mobile/src/screens/AdviceTab.tsx
git commit -m "mobile: cache advisory history and last-played voice audio for offline use"
```

---

### Task 7: ScanTab — enveloped timestamp, `<LastUpdated>`, offline submit message

**Files:**
- Modify: `mobile/src/screens/ScanTab.tsx`

**Interfaces:**
- Consumes: `<LastUpdated>` (Task 2), `errorText(t, e, { write: true })` (Task 3), `isOnline` (existing, from `api.ts`).

- [ ] **Step 1: Read the current scan-history caching code**

Read `mobile/src/screens/ScanTab.tsx` lines 325-410 (the `cacheGet<HistoryItem[]>('scans')`/`cacheSet('scans', ...)` calls found during planning) in full. These already use `cacheGet`/`cacheSet` directly (not `useLoad`) — Task 1's envelope change is transparent to this code since the public `cacheGet`/`cacheSet` signatures didn't change, so **no functional change is needed here for the envelope itself**. What's added: a timestamp.

- [ ] **Step 2: Track and render the history's last-updated time**

Add a `const [historyUpdatedAt, setHistoryUpdatedAt] = useState<number | null>(null);` alongside the existing `history` state. After each successful `cacheSet('scans', ...)` call (both the "loaded from server" path at line 363 and the "new scan appended" path at line 408), also call `setHistoryUpdatedAt(Date.now())`. On initial load, use `cacheGetWithTime<HistoryItem[]>('scans')` (from Task 1, import from `../storage`) instead of `cacheGet` for the history's initial read, and seed `historyUpdatedAt` from its `cachedAt`.

Render `<LastUpdated at={historyUpdatedAt} stale={false} t={t} />` directly above the `{t('scanHistory').toUpperCase()}` header (around line 507).

- [ ] **Step 3: Offline submit message**

Find the scan-submission handler (the function that calls `scanLeaf` from `../api`). Wrap its network call so that if `isOnline()` is false before attempting the request, it short-circuits immediately and shows `errorText(t, new ApiError(0, 'offline'), { write: true })` (via whatever error-display mechanism the handler already uses — a state variable or a `Banner`) rather than attempting the upload and waiting for a timeout. On a genuine network failure from the request itself (not pre-checked), the existing `catch` block's error display is updated to pass `{ write: true }` to `errorText`, same as Task 5's pattern.

- [ ] **Step 4: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/screens/ScanTab.tsx
git commit -m "mobile: show scan history's last-updated time and fail scan submission honestly offline"
```

---

### Task 8: Complete the bug-report flow — screen context, recent-error attachment, photo

**Files:**
- Modify: `mobile/src/screens/MeTab.tsx`
- Modify: `mobile/src/screens/HomeTab.tsx`, `AdviceTab.tsx`, `ScanTab.tsx` (add a "Report a problem" entry point that passes a screen name)
- Modify: `mobile/src/i18n.ts` (add `attachPhoto`, `removePhoto` keys, 4 languages)

**Interfaces:**
- Consumes: `getRecentErrors` (Task 4), `errorText(t, e, { write: true })` (Task 3), `sendBugReport` (existing, `api.ts`).

- [ ] **Step 1: Read the existing bug-report form in `MeTab.tsx` in full**

Read `mobile/src/screens/MeTab.tsx` lines 1-130 (the `BUG_CATS` list and `sendBug` handler found during planning, lines 16-127) to see the exact current form state (`bugCat`, `bugMsg`, `bugBusy`, `bugNote`) before editing.

- [ ] **Step 2: Add a `screenContext` parameter threaded from the caller**

Change `MeTab`'s component signature (or however the bug-report sheet is currently opened — check whether it's a modal always mounted inside `MeTab` or opened via navigation state) to accept an optional `initialScreenContext?: string` prop. In `HomeTab.tsx`, `AdviceTab.tsx`, `ScanTab.tsx`, add a small "Report a problem" affordance (a `TouchableOpacity`/icon button, following the existing icon-button style already used elsewhere in those files) that navigates to the Me tab's bug-report section with that screen's name (`'Home'`, `'Advice'`, `'Scan'`) as context — use whatever the app's existing tab-navigation mechanism is (check `App.tsx`'s `tab`/`setTab` state, used already at lines 363-367) to pass this: e.g. a shared `bugReportContext` piece of state lifted to `App.tsx` alongside `tab`, set before switching to `'me'`, consumed once by `MeTab` and cleared.

- [ ] **Step 3: Attach photo using the existing `expo-image-picker` pattern**

In `MeTab.tsx`, add a `bugPhoto: string | null` state next to `bugCat`/`bugMsg`. Add an "Attach a photo" button that calls the same `ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: false, quality: 0.4, base64: true })` pattern already used for the avatar picker (`MeTab.tsx:82`), and on success sets `bugPhoto` to `` `data:${asset.mimeType || 'image/jpeg'};base64,${asset.base64}` ``. Show a thumbnail (reuse the existing `<Image>` sizing pattern from the avatar display) with a remove button that clears `bugPhoto`.

- [ ] **Step 4: Fold screen context and recent errors into `message`, attach `photo_url`**

Replace the `sendBug` function (`MeTab.tsx:111-127`) with:

```ts
const sendBug = async () => {
  setBugNote('');
  if (!bugCat && !bugMsg.trim()) return setBugNote(t('bugReportError'));
  setBugBusy(true);
  try {
    const recent = await getRecentErrors(5);
    const parts: string[] = [];
    if (bugScreenContext) parts.push(`[Screen: ${bugScreenContext}]`);
    if (bugMsg.trim()) parts.push(bugMsg.trim());
    if (recent.length) {
      parts.push('[Recent errors]');
      parts.push(...recent.map((r) => `${new Date(r.at).toISOString()} ${r.context}: ${r.message}`));
    }
    const message = parts.join('\n').slice(0, 2000); // matches backend _MAX_BUG_MESSAGE_LEN
    await sendBugReport({
      category: bugCat || undefined,
      message: message || undefined,
      photo_url: bugPhoto || undefined,
      app_version: Constants.expoConfig?.version,
      platform: Platform.OS,
    });
    setBugNote(t('bugReportSuccess'));
    setBugCat(null); setBugMsg(''); setBugPhoto(null);
  } catch (e) {
    const { kind } = classifyError(e);
    setBugNote(kind === 'offline' ? t('noInternetWrite') : t('bugReportError'));
    if (kind === 'unknown') logError('MeTab.sendBug', e);
  } finally {
    setBugBusy(false);
  }
};
```

Add the corresponding imports: `import { getRecentErrors, logError } from '../errorLog';`, `import { classifyError } from '../errors';`. `bugScreenContext` is the state/prop threaded in Step 2.

- [ ] **Step 5: Pre-flight offline check**

Before calling `sendBugReport` in the function above, add an early check: if `!isOnline()` (import `isOnline` from `../api`), skip the request entirely and set `setBugNote(t('noInternetWrite'))` immediately — same short-circuit pattern as Task 7's scan submission, avoiding a doomed request/timeout.

- [ ] **Step 6: Add the two new i18n keys**

Add to `en`: `attachPhoto: 'Attach a photo', removePhoto: 'Remove photo',` and matching `kn`/`te`/`hi` translations.

- [ ] **Step 7: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add mobile/src/screens/MeTab.tsx mobile/src/screens/HomeTab.tsx mobile/src/screens/AdviceTab.tsx mobile/src/screens/ScanTab.tsx mobile/App.tsx mobile/src/i18n.ts
git commit -m "mobile: complete bug-report flow with screen context, recent errors, and photo attachment"
```

---

### Task 9: Live-device verification (manual, no code changes)

**Files:** none modified — this task is the spec's section 3 proof, run against a real build.

**Interfaces:** none.

- [ ] **Step 1: Build and install a dev build on a real device**

Run: `cd mobile && npx expo run:android` (or `run:ios`), sign in with a real farmer account, and use the app normally (view Home/Data/Advice/Scan, play one advisory's voice) so every cache key gets populated at least once.

- [ ] **Step 2: Offline read proof**

Turn on airplane mode (confirm mobile data is off too, not just Wi-Fi). Force-close and reopen the app. For each of Home, Data, Advice, Scan, Me: confirm cached data renders (no blank screen, no infinite spinner) with a real `<LastUpdated>` timestamp. Take one screenshot per tab.

- [ ] **Step 3: Offline write proof**

While still offline, attempt: add a field, submit a scan, request OTP (sign out first if needed to reach the OTP screen), submit feedback on an advisory, submit a bug report. Confirm each shows the exact `noInternetWrite` copy, not a crash or silent no-op. Take at least two screenshots.

- [ ] **Step 4: Reconnect proof**

Turn network back on. Confirm the previously-viewed screens refresh (their `<LastUpdated>` timestamp advances) without a reinstall or manual cache clear.

- [ ] **Step 5: Error pipeline proof**

Trigger one genuine server error if possible (e.g. an action while the backend is intentionally misconfigured, or rely on a naturally occurring 5xx) and confirm the shared `serverBusy`/`genericError` copy appears consistently. Confirm the error boundary's fallback (`crashedTitle`/`crashedBody`) has not appeared unexpectedly anywhere during this whole test pass (it should never trigger during normal use — if it does, that's a real bug to fix before sign-off, not to paper over).

- [ ] **Step 6: Bug-report live proof**

Submit one real bug report through the app (with a photo attached, from a specific screen's "Report a problem" entry point) while online. Do not use the voice/"Ask by voice" flow during this pass (no Sarvam quota burn). Confirm via `supabase` CLI or the admin dashboard's Bug Reports tab (Module 50) that the row landed with the folded screen-context/recent-error text in `message` and a populated `photo_url`.

- [ ] **Step 7: Record results in PROGRESS.md**

Add a "Module 51" section to `PROGRESS.md` following this module's own required handoff format (from `module-51-offline-errors-bug-reporting.md`'s "Handoff format" section) — offline contract per screen, live-proof confirmation, error-handling pipeline summary, bug-reporting summary, known limitations, next recommended step. Commit:

```bash
git add PROGRESS.md
git commit -m "Module 51: record offline/error-pipeline/bug-reporting completion and live-proof results"
```
