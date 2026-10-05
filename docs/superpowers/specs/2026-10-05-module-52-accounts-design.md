# Module 52 — Multi-account switching + themed popups

Branch: `mod-52-accounts`. Conflict zones: auth/login screens, `api.ts`
token handling, Me tab, root navigation. Notifications are Module 53 —
not touched here, only emitted as events.

## Goal

Instagram-style accounts on one phone. A farmer logs in once, can add up
to 4 more accounts, and switches between them without an OTP each time.

## Key finding that changes the brief's assumption

Auth today is a **Flask signed session cookie** only
(`agro_mirai/api/session_auth.py`), set on `/v2/auth/verify-otp` and
resent automatically by React Native's native networking layer. There is
no token anywhere in the client (`mobile/src/api.ts:1-7` says so
explicitly). RN's cookie jar is global to the app process, not something
JS can namespace per saved account. Real multi-account switching needs a
way to hold several live, independently-addressable sessions — that
needs a token, which doesn't exist yet.

**Decision (confirmed with Ritesh):** add Bearer-token auth, additively,
alongside the existing cookie. Nothing that already works changes.

## 1. Backend — additive token issuance

- `agro_mirai/api/session_auth.py`: `issue_session(farmer_id, role)` also
  returns a signed token string (reuse the same `itsdangerous` secret and
  payload shape as the session cookie: `farmer_id`, `role`, `issued_at`,
  so `is_expired` keeps working unchanged). Add
  `decode_token(token) -> dict | None`.
- `require_session_auth`: first checks `Authorization: Bearer <token>` if
  present, decodes it the same way, falls back to the session cookie
  otherwise. Expiry check (`is_expired`) applies identically to both
  paths.
- `agro_mirai/api/routes/auth_v2.py`: `verify_otp`'s JSON response gains
  an additive field, `session_token`, alongside the existing farmer
  fields. `request-otp`/`logout` responses are unchanged.
- Admin UI (`admin_ui.py`) and any farmer who never saves a second
  account keep using the cookie exactly as today — this is purely
  additive, no existing path changes behavior.

## 2. Mobile storage — new `mobile/src/accounts.ts`

- **Tokens**: `expo-secure-store` (new dependency — required either way
  for holding a credential long-term; justified regardless of the
  AsyncStorage-vs-MMKV call below). One entry per account:
  `account:<farmerId>:token`.
- **Account list + active pointer**: existing `AsyncStorage`, new keys
  under the current `agro:v2:` prefix: `accounts` →
  `{id, name, phone, lastActiveAt, sessionExpired?}[]` (max 5), and
  `activeAccountId`. No MMKV added — the list is capped at 5 items, so
  AsyncStorage's overhead is irrelevant, and Module 50 deliberately
  trimmed app size; a new native module isn't worth it for this.
- A 401 for the account that isn't currently active just marks that
  entry `sessionExpired: true` in the list (never deletes it or the
  other accounts). A 401 for the *active* account behaves as it does
  today (`goAuth` in `App.tsx`) but only for that one account's state.
- Public API: `listAccounts()`, `switchTo(id)`, `addOrSwitch(farmer, token)`
  (used by both "sign in" and "add another account" — if the id is
  already saved, this is a switch, not a duplicate), `remove(id)`,
  `getActiveToken()` (sync, from an in-memory cache kept warm by this
  module, not re-read from SecureStore per request).

## 3. `api.ts` — attach the active account's token

- `request()` adds `Authorization: Bearer <token>` using
  `accounts.getActiveToken()`. The cookie-based admin/legacy path is
  untouched; a request made with no saved accounts falls back to cookie
  auth exactly as today (so a farmer who never uses multi-account sees
  no behavior change at all).
- `onUnauthorized` becomes `onUnauthorized(accountId)`. Each request
  captures its account id at call time, so a slow in-flight request from
  an account that's no longer active can't 401-boot the *new* active
  account — `App.tsx`'s handler ignores a 401 whose accountId doesn't
  match the current active one (that account was likely already
  switched away from, not actually logged out).

## 4. Cache isolation (`storage.ts`)

- Prefix becomes `agro:v2:<accountId>:` for farmer-owned data, instead of
  flat `agro:v2:`. `lang`, `permsAsked`, `permsV2`, `tourSeen` stay
  device-global and unprefixed (device preferences, not farmer data).
- `clearFarmerCache(accountId)` takes the account id and only clears that
  namespace.
- Every existing `cacheGet`/`cacheSet` call site (in `App.tsx`,
  `MeTab.tsx`, etc.) gets audited during implementation to confirm it
  passes through the per-account prefix — this is the actual risk area
  the brief calls out ("account B never shows account A's cached data"),
  so it gets a written-down checklist, not just a mental pass.

## 5. `App.tsx` / `ctx.tsx` — account-aware root

- New thin `AccountsProvider` sits above the existing `RootInner`, owns
  `accounts[]` + `activeAccountId` (backed by `accounts.ts`).
- Switching calls `accounts.switchTo(id)` then re-mounts `RootInner` keyed
  by `activeAccountId` (`<RootInner key={activeAccountId} .../>`) — reuses
  the exact boot sequence that already loads a farmer's cached/live data
  on fresh mount, rather than building a second, parallel state-reset
  path.
- `signOut`: removes the active account's token + cache
  (`accounts.remove`, `clearFarmerCache`); if other accounts remain,
  switches to the most-recently-active one; otherwise falls through to
  the existing `auth` phase.

## 6. MeTab — Accounts section

- New `Section` (reusing the existing `Section` component in
  `MeTab.tsx`) placed above "My fields": lists saved accounts (avatar
  initials — reusing `avatarColor`/`initials` already in this file —
  name, phone last 4, active tick, or a "sign in again" tag when
  `sessionExpired`). Tapping a non-active row switches instantly, no OTP.
  "Add another account". Per-row "Remove" (themed confirm, see below).
- "Sign out" (existing button) behavior updated per §5.

## 7. Add-another-account flow

- A lean variant of the existing `AuthScreen` (`Onboarding.tsx`): same
  phone→OTP UI, but skips `LanguageScreen`/`PermissionsScreen`/tour,
  pre-filled with the already-active `lang`. Reuses `requestOtp`/
  `verifyOtp` unchanged — the backend already finds-or-creates by phone,
  this flow doesn't need to know "new vs existing" beyond what
  `verifyOtp`'s response already tells it.
- On success, `accounts.addOrSwitch(farmer, token)` decides add-vs-switch.
- At 5 accounts, "Add another account" shows the themed info dialog
  instead of opening the flow (no dead button, no silent no-op).

## 8. Themed dialog (`mobile/src/dialog.tsx`)

- One component built from `theme.ts`'s `C`/`S` tokens (light/dark if the
  app has it — confirm during implementation whether `theme.ts` currently
  branches on scheme). Imperative API: `dialog.confirm({title, body,
  destructive?}): Promise<boolean>`, `dialog.info({title, body}):
  Promise<void>`.
- Replaces the app's only two `Alert.alert` call sites, both in
  `MeTab.tsx` (delete-field confirm, sign-out confirm), and backs the new
  remove-account confirm, 5-account-limit info, and "can't switch, no
  cached data for this account while offline" info.
- OS-level permission pre-prompts stay native (Android/iOS draws those
  itself) — called out as a known limitation in the handoff, not fixed.

## 9. Events for Module 53

- New `mobile/src/accountEvents.ts`: a small typed emitter/hook —
  `accountSignedIn(id)`, `accountSwitched(from, to)`,
  `accountSignedOut(id)`. Fired from `accounts.ts` at the relevant
  points. No listener or notification logic lives here — Module 53 owns
  that.

## Testing

- Backend: unit tests for `decode_token`/bearer-path auth in
  `session_auth.py` (valid token, expired token, malformed token, cookie
  still works with no header) and for `verify_otp` returning
  `session_token`.
- Mobile: tests for `accounts.ts` (add/switch/remove, 5-account cap,
  sessionExpired marking) and the `storage.ts` namespacing change
  (existing cache tests gain an accountId dimension). No filler tests for
  UI layout.

## Proof (live device/emulator, per standing rules)

Add a 2nd and 3rd account, switch back and forth showing different data
per account, kill the app and reopen (both still there), attempt a 6th
(blocked with themed dialog), sign out one, remove one, themed-popup
screenshots (delete-field, sign-out, remove-account — ≥3), and switching
while offline using cached data.

## Known limitations

- OS permission dialogs are not themed (platform-drawn, can't be).
- Switching to an account with no cached data for the current field,
  while offline, shows the themed "no cached data for this account"
  info dialog rather than any data — there isn't anything to show.
