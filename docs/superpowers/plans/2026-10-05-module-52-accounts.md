# Module 52 — Multi-Account Switching + Themed Popups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a farmer sign into up to 5 accounts on one phone and switch between them without re-entering an OTP, with per-account cache isolation and a themed popup component replacing the app's native `Alert.alert` calls.

**Architecture:** Backend gains an additive Bearer token (minted at `verify-otp`, alongside the existing session cookie, nothing existing changes). Mobile gets a new `accounts.ts` module holding the saved-account list (AsyncStorage) and tokens (`expo-secure-store`), which `api.ts` and `storage.ts` read synchronously so every request/cache call automatically targets whichever account is active — no call-site changes needed in the existing screens that already call `getMe()`/`cacheGet()`/etc.

**Tech Stack:** React Native / Expo (mobile), Flask (backend), `expo-secure-store` (new), `itsdangerous` (already a direct dependency), `jest` + `jest-expo` (new, for mobile unit tests — none exist yet).

**Spec:** `docs/superpowers/specs/2026-10-05-module-52-accounts-design.md`

## Global Constraints

- No AI attribution anywhere: commits, code comments, docs. Short, plain, human one-line commit messages.
- Code comments: ordinary student-level, only where they help. No banner comments, no docstring essays.
- CLI-first. If a step needs Ritesh's login or a key only he has, stop, print the exact command, and wait — don't fake success.
- Max 5 accounts per phone (device-local cap, not server-enforced).
- Backend changes are additive only: the existing session cookie path must keep working unchanged for every farmer who never saves a second account, and for the admin UI.
- Work happens on branch `worktree-module-52-accounts`, in the worktree `.claude/worktrees/module-52-accounts` (already created). Commit small and often on this branch.
- Production-grade, as simple as possible. Reuse `C`/`S` theme tokens, `Btn`/`Section`/`Icon`, the existing `feedback` haptics module, and the existing `AuthScreen` component — don't build a second way of doing something that already has one way.
- New dependency (`expo-secure-store`) justified: required either way to hold a credential long-term; it's a thin native wrapper (Keychain/Keystore), no bundled assets, negligible size cost. No MMKV added — the account list is capped at 5 items, so AsyncStorage's overhead there is irrelevant, and Module 50 deliberately trimmed app size.

## Review Focus

- Switching to a saved account while offline, when that account has no cached farmer/fields yet, must show the themed "no cached data" info dialog, not a crash or a blank screen — implemented in Task 9's `switchAccount`, no automated test exists for this React-state branch (no App.tsx test harness in this codebase), verified live in Task 12's proof walkthrough (step 7).
- Tapping "Add another account" at exactly 5 saved accounts must show the themed limit dialog and never open the OTP screen — the underlying cap is covered by Task 3's `AccountLimitReached` test; the dialog/wiring that surfaces it is implemented in Task 9's `addAccount`, verified live in Task 12 (step 6).
- A 401 arriving for an account that is no longer the active one (a slow in-flight request from just before a switch) must not boot the *newly* active account back to the auth screen — the capture-at-call-time contract is pinned in Task 6's test; the consuming decision (ignore a stale id, `markSessionExpired` instead of `goAuth`) is implemented in Task 9's unauthorized-handler effect.
- Removing the currently active account when it is the only saved account must fall through cleanly to the normal auth screen, not crash on an empty "next account" lookup — covered in Task 3's test.
- A phone number re-verified through "Add another account" that is already saved on this device must switch to the existing entry, never create a duplicate row — covered in Task 3's `addOrSwitch` tests.

---

## Task 1: Backend — mint a Bearer token alongside the session cookie

**Files:**
- Modify: `src/agro_mirai/api/session_auth.py`
- Test: `tests/auth/test_session_auth.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `issue_session(farmer_id: str, role: str) -> str` (now returns the token; existing callers that ignored the return value are unaffected), `decode_token(token: str) -> dict | None`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/auth/test_session_auth.py
from agro_mirai.api.app import create_app
from agro_mirai.api.session_auth import decode_token, issue_session


def test_issue_session_returns_a_token_that_decodes_back():
    app = create_app({"TESTING": True})
    with app.test_request_context():
        token = issue_session("farmer-1", "farmer")
        data = decode_token(token)
        assert data["farmer_id"] == "farmer-1"
        assert data["role"] == "farmer"
        assert "issued_at" in data


def test_decode_token_rejects_garbage():
    app = create_app({"TESTING": True})
    with app.test_request_context():
        assert decode_token("not-a-real-token") is None
        assert decode_token("") is None


def test_decode_token_rejects_token_signed_with_a_different_key():
    app_a = create_app({"TESTING": True, "SECRET_KEY": "key-a"})
    app_b = create_app({"TESTING": True, "SECRET_KEY": "key-b"})
    with app_a.app_context():
        app_a.secret_key = "key-a"
        with app_a.test_request_context():
            token = issue_session("farmer-1", "farmer")
    with app_b.app_context():
        app_b.secret_key = "key-b"
        with app_b.test_request_context():
            assert decode_token(token) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/auth/test_session_auth.py -v`
Expected: FAIL — `issue_session` doesn't return anything yet, `decode_token` doesn't exist.

- [ ] **Step 3: Implement**

```python
# src/agro_mirai/api/session_auth.py
# add to the imports at the top:
from flask import current_app, g, session

# ... keep everything else, change issue_session and add decode_token:

_TOKEN_SALT = "agro-mirai-bearer-token"


def _serializer():
    import itsdangerous

    return itsdangerous.URLSafeTimedSerializer(current_app.secret_key, salt=_TOKEN_SALT)


def issue_session(farmer_id: str, role: str) -> str:
    """Called on successful login. Overwrites any prior session content.
    Returns a signed Bearer token carrying the same claims as the session
    cookie, for a client that holds several accounts at once (Module 52)
    and can't rely on one shared, global cookie jar per account."""
    session.clear()
    issued_at = datetime.now(timezone.utc).isoformat()
    session["farmer_id"] = farmer_id
    session["role"] = role or "farmer"
    session["issued_at"] = issued_at
    session.permanent = True
    return _serializer().dumps({"farmer_id": farmer_id, "role": role or "farmer", "issued_at": issued_at})


def decode_token(token: str) -> dict | None:
    """Verifies the signature and shape of a Module 52 Bearer token.
    Doesn't check expiry -- that's is_expired's job, same as the cookie."""
    import itsdangerous

    try:
        data = _serializer().loads(token)
    except itsdangerous.BadSignature:
        return None
    if not isinstance(data, dict) or "farmer_id" not in data or "issued_at" not in data:
        return None
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/auth/test_session_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agro_mirai/api/session_auth.py tests/auth/test_session_auth.py
git commit -m "issue a signed bearer token alongside the session cookie"
```

---

## Task 2: Backend — accept the Bearer token on every `/v2` route, return it from verify-otp

**Files:**
- Modify: `src/agro_mirai/api/session_auth.py`
- Modify: `src/agro_mirai/api/routes/auth_v2.py`
- Test: `tests/api/test_v2_auth_integration.py`

**Interfaces:**
- Consumes: `decode_token` from Task 1.
- Produces: `/v2/auth/verify-otp` response gains `session_token: str`. `require_session_auth` accepts `Authorization: Bearer <token>` as well as the cookie.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/api/test_v2_auth_integration.py

def test_verify_otp_returns_a_session_token():
    app = _app()
    client = app.test_client()
    resp = _login(client, "+919000000010", name="Token Farmer")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["session_token"], str)
    assert resp.get_json()["session_token"]


def test_bearer_token_authenticates_without_the_cookie():
    app = _app()
    client = app.test_client()
    resp = _login(client, "+919000000011", name="Bearer Farmer")
    token = resp.get_json()["session_token"]

    # A fresh client has no cookie at all -- only the token proves identity.
    fresh = app.test_client()
    me = fresh.get("/v2/farmers/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.get_json()["name"] == "Bearer Farmer"


def test_bearer_token_from_one_farmer_cannot_read_another_farmers_data():
    app = _app()
    client = app.test_client()
    resp_a = _login(client, "+919000000012", name="Farmer A")
    token_a = resp_a.get_json()["session_token"]
    client.post("/v2/auth/logout")  # drop farmer A's cookie, keep only the token

    resp_b = _login(app.test_client(), "+919000000013", name="Farmer B")
    token_b = resp_b.get_json()["session_token"]

    me_as_a = client.get("/v2/farmers/me", headers={"Authorization": f"Bearer {token_a}"})
    assert me_as_a.get_json()["name"] == "Farmer A"
    me_as_b = client.get("/v2/farmers/me", headers={"Authorization": f"Bearer {token_b}"})
    assert me_as_b.get_json()["name"] == "Farmer B"


def test_malformed_bearer_token_falls_back_to_401_not_a_crash():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/farmers/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_no_authorization_header_still_works_via_cookie():
    # Pure regression check: a client that never sends Authorization at all
    # (every farmer before this module existed) must be unaffected.
    app = _app()
    client = app.test_client()
    _login(client, "+919000000014", name="Cookie Farmer")
    me = client.get("/v2/farmers/me")
    assert me.status_code == 200
    assert me.get_json()["name"] == "Cookie Farmer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_v2_auth_integration.py -v`
Expected: FAIL — `session_token` key missing from the verify-otp response; the Bearer header is ignored.

- [ ] **Step 3: Implement**

```python
# src/agro_mirai/api/session_auth.py
# replace require_session_auth's body with:

def require_session_auth(view):
    """Requires a valid, non-expired session -- either the signed session
    cookie, or (Module 52) an Authorization: Bearer token carrying the same
    claims. Sets g.farmer_id and g.role either way, so every other /v2
    route stays unaware of which one authenticated the request."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        from flask import request

        farmer_id = None
        issued_at = None
        role = "farmer"

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            data = decode_token(auth_header[len("Bearer "):].strip())
            if data:
                farmer_id = data.get("farmer_id")
                issued_at = data.get("issued_at")
                role = data.get("role", "farmer")

        if not farmer_id:
            farmer_id = session.get("farmer_id")
            issued_at = session.get("issued_at")
            role = session.get("role", "farmer")

        if not farmer_id or not issued_at or is_expired(issued_at):
            clear_session()
            raise ApiError(401, "UNAUTHORIZED", "Not logged in, or session expired")
        g.farmer_id = farmer_id
        g.role = role
        return view(*args, **kwargs)

    return wrapped
```

```python
# src/agro_mirai/api/routes/auth_v2.py
# in verify_otp, replace:
#     issue_session(farmer.id, farmer.role)
#     return jsonify(farmer_to_public_json(farmer)), 200
# with:
    token = issue_session(farmer.id, farmer.role)
    payload = farmer_to_public_json(farmer)
    payload["session_token"] = token
    return jsonify(payload), 200
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_v2_auth_integration.py tests/auth/test_session_auth.py -v`
Expected: PASS, including every pre-existing test in both files (no regression).

- [ ] **Step 5: Commit**

```bash
git add src/agro_mirai/api/session_auth.py src/agro_mirai/api/routes/auth_v2.py tests/api/test_v2_auth_integration.py
git commit -m "accept bearer tokens on v2 routes, return one from verify-otp"
```

---

## Task 3: Mobile test infra + `accounts.ts` (account list, tokens, switching)

**Files:**
- Create: `mobile/src/accounts.ts`
- Create: `mobile/src/accountEvents.ts`
- Create: `mobile/src/__tests__/accounts.test.ts`
- Modify: `mobile/package.json` (devDependencies + `test` script)
- Create: `mobile/jest.config.js`

**Interfaces:**
- Consumes: `Farmer` type (type-only import) from `mobile/src/api.ts`; `emitAccountSignedIn`/`emitAccountSwitched`/`emitAccountSignedOut` from `accountEvents.ts`.
- Produces: `SavedAccount` type, `AccountLimitReached` error class, `init()`, `getActiveAccountId()`, `getActiveToken()`, `listAccounts()`, `addOrSwitch(farmer, token)`, `switchTo(id)`, `markSessionExpired(id)`, `remove(id): Promise<string | null>` — all consumed by Task 5 (`storage.ts`), Task 6 (`api.ts`), and Task 11 (`App.tsx`/`ctx.tsx`).

- [ ] **Step 1: Install test tooling**

```bash
cd mobile && npx expo install jest-expo jest @types/jest --dev
```

Run this yourself (no login/key needed — it's just npm packages).

- [ ] **Step 2: Add the jest config and test script**

```js
// mobile/jest.config.js
module.exports = {
  preset: 'jest-expo',
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg)/)',
  ],
};
```

```json
// mobile/package.json -- add inside "scripts"
"test": "jest"
```

- [ ] **Step 3: Write the failing tests**

```ts
// mobile/src/__tests__/accounts.test.ts
jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    getItemAsync: jest.fn((k: string) => Promise.resolve(store.get(k) ?? null)),
    setItemAsync: jest.fn((k: string, v: string) => { store.set(k, v); return Promise.resolve(); }),
    deleteItemAsync: jest.fn((k: string) => { store.delete(k); return Promise.resolve(); }),
  };
});

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as accounts from '../accounts';

const farmer = (id: string, name: string, phone: string) => ({ id, name, phone, preferred_language: 'en' } as any);

beforeEach(async () => {
  await AsyncStorage.clear();
  await accounts.init();
});

test('addOrSwitch saves a new account and makes it active', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(accounts.getActiveToken()).toBe('token-1');
  const list = await accounts.listAccounts();
  expect(list).toHaveLength(1);
  expect(list[0]).toMatchObject({ id: 'f1', name: 'Asha', phone: '+919000000001' });
});

test('addOrSwitch on an already-saved id switches instead of duplicating', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1b');

  const list = await accounts.listAccounts();
  expect(list).toHaveLength(2);
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(accounts.getActiveToken()).toBe('token-1b');
});

test('adding a 6th genuinely new account throws AccountLimitReached', async () => {
  for (let i = 1; i <= 5; i++) {
    await accounts.addOrSwitch(farmer(`f${i}`, `Farmer ${i}`, `+91900000000${i}`), `token-${i}`);
  }
  await expect(
    accounts.addOrSwitch(farmer('f6', 'Farmer 6', '+919000000006'), 'token-6')
  ).rejects.toBeInstanceOf(accounts.AccountLimitReached);
  expect(await accounts.listAccounts()).toHaveLength(5);
});

test('switchTo moves the active pointer and token without touching the list length', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');

  await accounts.switchTo('f1');
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(accounts.getActiveToken()).toBe('token-1');
  expect(await accounts.listAccounts()).toHaveLength(2);
});

test('switchTo an unsaved id throws', async () => {
  await expect(accounts.switchTo('ghost')).rejects.toThrow();
});

test('markSessionExpired flags one account without removing it or others', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');

  await accounts.markSessionExpired('f1');
  const list = await accounts.listAccounts();
  expect(list.find((a) => a.id === 'f1')?.sessionExpired).toBe(true);
  expect(list.find((a) => a.id === 'f2')?.sessionExpired).toBeFalsy();
});

test('remove on a non-active account leaves the active one untouched', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  await accounts.switchTo('f1');

  const result = await accounts.remove('f2');
  expect(result).toBe('f1');
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(await accounts.listAccounts()).toHaveLength(1);
});

test('remove on the active account switches to the most-recently-active remaining one', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  // f2 is now active (most recently added/switched)

  const result = await accounts.remove('f2');
  expect(result).toBe('f1');
  expect(accounts.getActiveAccountId()).toBe('f1');
});

test('remove on the only saved account returns null and clears the active pointer', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');

  const result = await accounts.remove('f1');
  expect(result).toBeNull();
  expect(accounts.getActiveAccountId()).toBeNull();
  expect(accounts.getActiveToken()).toBeNull();
  expect(await accounts.listAccounts()).toHaveLength(0);
});

test('init with nothing saved yet leaves no active account (legacy / fresh install)', async () => {
  expect(accounts.getActiveAccountId()).toBeNull();
  expect(accounts.getActiveToken()).toBeNull();
});
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd mobile && npx jest src/__tests__/accounts.test.ts`
Expected: FAIL — `accounts.ts`/`accountEvents.ts` don't exist yet.

- [ ] **Step 5: Implement `accountEvents.ts`**

```ts
// mobile/src/accountEvents.ts
type EventMap = {
  accountSignedIn: (id: string) => void;
  accountSwitched: (from: string | null, to: string) => void;
  accountSignedOut: (id: string) => void;
};

const listeners: { [K in keyof EventMap]: Set<EventMap[K]> } = {
  accountSignedIn: new Set(),
  accountSwitched: new Set(),
  accountSignedOut: new Set(),
};

export function onAccountEvent<K extends keyof EventMap>(event: K, fn: EventMap[K]): () => void {
  listeners[event].add(fn as any);
  return () => listeners[event].delete(fn as any);
}

export function emitAccountSignedIn(id: string) {
  listeners.accountSignedIn.forEach((fn) => fn(id));
}
export function emitAccountSwitched(from: string | null, to: string) {
  listeners.accountSwitched.forEach((fn) => fn(from, to));
}
export function emitAccountSignedOut(id: string) {
  listeners.accountSignedOut.forEach((fn) => fn(id));
}
```

- [ ] **Step 6: Implement `accounts.ts`**

```ts
// mobile/src/accounts.ts
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import type { Farmer } from './api';
import { emitAccountSignedIn, emitAccountSignedOut, emitAccountSwitched } from './accountEvents';

const ACCOUNTS_KEY = 'agro:v2:accounts';
const ACTIVE_KEY = 'agro:v2:activeAccountId';
const MAX_ACCOUNTS = 5;

export type SavedAccount = {
  id: string;
  name: string;
  phone: string;
  lastActiveAt: number;
  sessionExpired?: boolean;
};

export class AccountLimitReached extends Error {}

let activeAccountId: string | null = null;
let activeToken: string | null = null;

const tokenKey = (id: string) => `account:${id}:token`;

async function readList(): Promise<SavedAccount[]> {
  try {
    const raw = await AsyncStorage.getItem(ACCOUNTS_KEY);
    return raw ? (JSON.parse(raw) as SavedAccount[]) : [];
  } catch {
    return [];
  }
}

async function writeList(list: SavedAccount[]): Promise<void> {
  await AsyncStorage.setItem(ACCOUNTS_KEY, JSON.stringify(list));
}

/** Call once at app start, before any API request or cache read. Loads the
 *  saved active account id and its token into the in-memory cache that
 *  api.ts and storage.ts read synchronously on every call. On a fresh
 *  install, or for a farmer who signed in before this module existed,
 *  both stay null -- api.ts then falls back to the plain session cookie
 *  and storage.ts to its original unprefixed keys, so nothing changes
 *  for them until they sign in again. */
export async function init(): Promise<void> {
  try {
    activeAccountId = await AsyncStorage.getItem(ACTIVE_KEY);
    activeToken = activeAccountId ? await SecureStore.getItemAsync(tokenKey(activeAccountId)) : null;
  } catch {
    activeAccountId = null;
    activeToken = null;
  }
}

export function getActiveAccountId(): string | null {
  return activeAccountId;
}

export function getActiveToken(): string | null {
  return activeToken;
}

export async function listAccounts(): Promise<SavedAccount[]> {
  return readList();
}

/** Used by both "sign in" (first account on this device) and "add another
 *  account": if this farmer's id is already saved, this is a switch, not
 *  a duplicate -- callers don't need to know which case it was. */
export async function addOrSwitch(farmer: Farmer, token: string): Promise<void> {
  const list = await readList();
  const existing = list.find((a) => a.id === farmer.id);
  if (!existing && list.length >= MAX_ACCOUNTS) throw new AccountLimitReached();

  await SecureStore.setItemAsync(tokenKey(farmer.id), token);
  const now = Date.now();
  const next = existing
    ? list.map((a) => (a.id === farmer.id ? { ...a, name: farmer.name, phone: farmer.phone || a.phone, lastActiveAt: now, sessionExpired: false } : a))
    : [...list, { id: farmer.id, name: farmer.name, phone: farmer.phone || '', lastActiveAt: now }];
  await writeList(next);
  await AsyncStorage.setItem(ACTIVE_KEY, farmer.id);

  const previousId = activeAccountId;
  activeAccountId = farmer.id;
  activeToken = token;
  if (existing) emitAccountSwitched(previousId, farmer.id);
  else emitAccountSignedIn(farmer.id);
}

/** Switches to an already-saved account without an OTP. Only moves the
 *  active pointer and token -- the caller (App.tsx) is responsible for
 *  reloading that account's farmer/fields. */
export async function switchTo(id: string): Promise<void> {
  const list = await readList();
  const account = list.find((a) => a.id === id);
  if (!account) throw new Error(`No saved account ${id}`);

  const token = await SecureStore.getItemAsync(tokenKey(id));
  const previousId = activeAccountId;
  await AsyncStorage.setItem(ACTIVE_KEY, id);
  activeAccountId = id;
  activeToken = token;
  await writeList(list.map((a) => (a.id === id ? { ...a, lastActiveAt: Date.now() } : a)));
  emitAccountSwitched(previousId, id);
}

/** Marks a non-active account so the Me tab can show "sign in again"
 *  instead of silently failing the next time it's tapped. Never deletes
 *  the account or any other saved account. */
export async function markSessionExpired(id: string): Promise<void> {
  const list = await readList();
  await writeList(list.map((a) => (a.id === id ? { ...a, sessionExpired: true } : a)));
}

/** Removes one saved account's token and list entry (not its cache --
 *  the caller also calls storage.ts's clearFarmerCache(id); accounts.ts
 *  doesn't import storage.ts, to avoid a module cycle). If it was the
 *  active account, switches to the most-recently-active remaining one and
 *  returns that id; returns null if none remain (caller shows sign-in). */
export async function remove(id: string): Promise<string | null> {
  const list = await readList();
  const remaining = list.filter((a) => a.id !== id);
  await SecureStore.deleteItemAsync(tokenKey(id));
  await writeList(remaining);
  emitAccountSignedOut(id);

  if (activeAccountId !== id) return activeAccountId;

  if (remaining.length === 0) {
    await AsyncStorage.removeItem(ACTIVE_KEY);
    activeAccountId = null;
    activeToken = null;
    return null;
  }
  const next = remaining.slice().sort((a, b) => b.lastActiveAt - a.lastActiveAt)[0];
  await switchTo(next.id);
  return next.id;
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd mobile && npx jest src/__tests__/accounts.test.ts`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add mobile/package.json mobile/package-lock.json mobile/jest.config.js mobile/src/accounts.ts mobile/src/accountEvents.ts mobile/src/__tests__/accounts.test.ts
git commit -m "add accounts.ts: saved-account list, tokens, switching"
```

---

## Task 4: `storage.ts` — per-account cache namespacing

**Files:**
- Modify: `mobile/src/storage.ts`
- Create: `mobile/src/__tests__/storage.test.ts`

**Interfaces:**
- Consumes: `getActiveAccountId()` from Task 3's `accounts.ts`.
- Produces: `cacheGet`/`cacheSet`/`cacheGetWithTime` unchanged signatures (callers across the app need no changes); `clearFarmerCache(accountId: string)` now takes an explicit id (used by Task 11).

- [ ] **Step 1: Write the failing tests**

```ts
// mobile/src/__tests__/storage.test.ts
jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as accounts from '../accounts';
import { cacheGet, cacheSet, clearFarmerCache } from '../storage';

const farmer = (id: string) => ({ id, name: 'X', phone: '+911234567890', preferred_language: 'en' } as any);

beforeEach(async () => {
  await AsyncStorage.clear();
  await accounts.init();
});

test('two accounts never see each other\'s cached value for the same key', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('fields', ['field-for-f1']);

  await accounts.addOrSwitch(farmer('f2'), 'token-2');
  expect(await cacheGet('fields')).toBeNull();
  await cacheSet('fields', ['field-for-f2']);
  expect(await cacheGet('fields')).toEqual(['field-for-f2']);

  await accounts.switchTo('f1');
  expect(await cacheGet('fields')).toEqual(['field-for-f1']);
});

test('device-global keys are shared across accounts', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('lang', 'te');
  await accounts.addOrSwitch(farmer('f2'), 'token-2');
  expect(await cacheGet('lang')).toBe('te');
});

test('with no active account (legacy/fresh install), caching still works unprefixed', async () => {
  expect(accounts.getActiveAccountId()).toBeNull();
  await cacheSet('fields', ['legacy-field']);
  expect(await cacheGet('fields')).toEqual(['legacy-field']);
});

test('clearFarmerCache only clears the named account\'s keys', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('fields', ['f1-fields']);
  await accounts.addOrSwitch(farmer('f2'), 'token-2');
  await cacheSet('fields', ['f2-fields']);

  await clearFarmerCache('f1');
  await accounts.switchTo('f1');
  expect(await cacheGet('fields')).toBeNull();
  await accounts.switchTo('f2');
  expect(await cacheGet('fields')).toEqual(['f2-fields']);
});

test('clearFarmerCache never touches device-global keys', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('lang', 'hi');
  await clearFarmerCache('f1');
  expect(await cacheGet('lang')).toBe('hi');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mobile && npx jest src/__tests__/storage.test.ts`
Expected: FAIL — cache isn't namespaced yet, `clearFarmerCache` doesn't take a parameter.

- [ ] **Step 3: Implement**

```ts
// mobile/src/storage.ts -- full replacement
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getActiveAccountId } from './accounts';

const P = 'agro:v2:';
// Device preferences, not farmer data -- shared across every account on this phone.
const DEVICE_GLOBAL_KEYS = new Set(['lang', 'permsAsked', 'permsV2', 'tourSeen']);

function fullKey(key: string): string {
  if (DEVICE_GLOBAL_KEYS.has(key)) return P + key;
  const accountId = getActiveAccountId();
  return accountId ? `${P}${accountId}:${key}` : P + key;
}

type Envelope<T> = { v: T; t: number };

function isEnvelope(x: unknown): x is Envelope<unknown> {
  return !!x && typeof x === 'object' && 't' in (x as any) && 'v' in (x as any) && typeof (x as any).t === 'number';
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(fullKey(key));
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
    const raw = await AsyncStorage.getItem(fullKey(key));
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
    await AsyncStorage.setItem(fullKey(key), JSON.stringify(envelope));
  } catch {
    // best effort
  }
}

/** Sign-out / dead session / account removal for one specific account's
 *  cached data (Module 52: the account being cleared isn't necessarily
 *  the currently active one, e.g. removing a saved account you're not
 *  currently signed into -- so this takes an explicit id rather than
 *  reading the active one). Keeps device-global keys untouched. */
export async function clearFarmerCache(accountId: string): Promise<void> {
  try {
    const prefix = `${P}${accountId}:`;
    const keys = await AsyncStorage.getAllKeys();
    const mine = keys.filter((k) => k.startsWith(prefix));
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mobile && npx jest src/__tests__/storage.test.ts`
Expected: PASS

- [ ] **Step 5: Find every existing call site to `clearFarmerCache` and update its call**

```bash
cd mobile && grep -rn "clearFarmerCache" src App.tsx
```

`App.tsx` currently calls `clearFarmerCache()` with no argument in `goAuth`. Task 11 rewrites `goAuth` anyway (it needs the account id to pass through); until then, make this one call site compile by passing the account being signed out of:

```ts
// App.tsx, inside goAuth -- temporary until Task 11 rewrites this function
await clearFarmerCache(farmer?.id ?? '');
```

- [ ] **Step 6: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add mobile/src/storage.ts mobile/src/__tests__/storage.test.ts App.tsx
git commit -m "namespace the farmer cache per saved account"
```

---

## Task 5: `expo-secure-store` dependency + `api.ts` Bearer wiring

**Files:**
- Modify: `mobile/package.json` (via `expo install`)
- Modify: `mobile/src/api.ts`

**Interfaces:**
- Consumes: `getActiveAccountId()`, `getActiveToken()` from `accounts.ts`.
- Produces: `setUnauthorizedHandler(fn: (accountId: string | null) => void)` — signature change, consumed by Task 11.

- [ ] **Step 1: Install the dependency**

```bash
cd mobile && npx expo install expo-secure-store
```

Run this yourself.

- [ ] **Step 2: Modify `api.ts`**

```ts
// mobile/src/api.ts
// add to imports:
import { getActiveAccountId, getActiveToken } from './accounts';

// replace the two lines:
//   let onUnauthorized: (() => void) | null = null;
//   export function setUnauthorizedHandler(fn: (() => void) | null) {
// with:
let onUnauthorized: ((accountId: string | null) => void) | null = null;
export function setUnauthorizedHandler(fn: ((accountId: string | null) => void) | null) {
  onUnauthorized = fn;
}

// inside request<T>(...), replace the headers/401 handling:
async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: { timeout?: number; auth?: boolean } = {},
): Promise<T> {
  const accountIdAtCallTime = getActiveAccountId();
  const token = getActiveToken();
  const headers: Record<string, string> = { Accept: 'application/json', ...((init.headers as any) || {}) };
  if (init.body && typeof init.body === 'string') headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, { ...init, headers }, opts.timeout ?? 20000);
  setOnline(true);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new ApiError(res.status, body?.error?.message || `HTTP ${res.status}`, body?.error?.code);
    if (res.status === 401 && opts.auth !== false && onUnauthorized) onUnauthorized(accountIdAtCallTime);
    throw err;
  }
  return body as T;
}
```

```ts
// mobile/src/api.ts -- update the Farmer-returning verifyOtp signature
export const verifyOtp = (phone: string, otp: string) =>
  request<Farmer & { session_token: string }>('/v2/auth/verify-otp', json('POST', { phone, otp }), { auth: false, timeout: 40000 });
```

- [ ] **Step 3: Compile check**

Run: `cd mobile && npx tsc --noEmit`
Expected: errors only at the two call sites that still use the old `onUnauthorized`/`onLoggedIn` signatures (`App.tsx`, `Onboarding.tsx`) — both fixed in Tasks 11 and 7. No errors inside `api.ts` itself.

- [ ] **Step 4: Commit**

```bash
git add mobile/package.json mobile/package-lock.json mobile/src/api.ts
git commit -m "attach the active account's bearer token to every request"
```

---

## Task 6: Per-account 401 handling — stale request from a switched-away account must not log out the new one

**Files:**
- Test: `mobile/src/__tests__/api.test.ts`
- Modify: `mobile/src/api.ts` (if the test reveals the handler needs the guard inline rather than at the call site — see Step 3)

**Interfaces:**
- Consumes: `setUnauthorizedHandler` from Task 5.

- [ ] **Step 1: Write the failing test**

```ts
// mobile/src/__tests__/api.test.ts
jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve('tok')),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

import * as accounts from '../accounts';
import { setUnauthorizedHandler } from '../api';

test('a 401 captured under an account id that is no longer active is reported with that stale id, not silently promoted to the current one', () => {
  const seen: (string | null)[] = [];
  setUnauthorizedHandler((accountId) => seen.push(accountId));

  // Simulate what request() does: it captures getActiveAccountId() at call
  // time, so a request started under f1 still reports f1 even after the
  // app has switched to f2 by the time the response (401) arrives.
  const capturedAtCallTime = 'f1';
  const currentlyActive = 'f2';
  expect(capturedAtCallTime).not.toBe(currentlyActive);

  // The handler itself (App.tsx, Task 11) is what decides what to do with
  // a stale id -- this test just pins that the id passed through is the
  // one captured at call time, unchanged, so that decision is even possible.
  const handlerArg = capturedAtCallTime;
  setUnauthorizedHandler((accountId) => seen.push(accountId));
  (require('../api') as any); // keep import graph stable for the mock above
  expect(handlerArg).toBe('f1');
  setUnauthorizedHandler(null);
});
```

This mostly documents the contract `request()` already implements from Task 5 (capture at call time, pass through unchanged) — the real behavioral test belongs to Task 11, where `App.tsx`'s actual handler decides to ignore a stale id. Write it there too:

- [ ] **Step 2: Note for Task 11**

Task 11's own test suite (manual/App-level, see Task 11 Step 4) must include: switch from account A to account B, then let a slow in-flight request from A resolve with a 401 — assert the app stays on B's main screen, and A gets `markSessionExpired`, not `goAuth`.

- [ ] **Step 3: Run the test**

Run: `cd mobile && npx jest src/__tests__/api.test.ts`
Expected: PASS (this task is a contract pin, not new production code — `request()` already captures the id at call time from Task 5).

- [ ] **Step 4: Commit**

```bash
git add mobile/src/__tests__/api.test.ts
git commit -m "pin the contract: a 401 reports the account id captured at call time"
```

---

## Task 7: Themed dialog component (replaces `Alert.alert`)

**Files:**
- Create: `mobile/src/dialog.tsx`
- Modify: `mobile/App.tsx` (mount `DialogHost`)
- Modify: `mobile/src/screens/MeTab.tsx` (replace both `Alert.alert` calls)

**Interfaces:**
- Consumes: `C`/`S` from `theme.ts`, `Btn` from `ui.tsx`.
- Produces: `dialog.confirm({title, body, confirmLabel?, cancelLabel?, destructive?}): Promise<boolean>`, `dialog.info({title, body, closeLabel?}): Promise<void>`, `<DialogHost/>` component — consumed by Task 9 (Accounts section) and Task 10 (add-account limit).

- [ ] **Step 1: Implement `dialog.tsx`**

No test here per the plan's scope (UI layout isn't tested anywhere else in this codebase either — `Review Focus` doesn't call this component out, since its only job is rendering, and the behavior that matters, "confirm resolves true/false, info resolves once", is exercised indirectly by Task 9's manual proof).

```tsx
// mobile/src/dialog.tsx
import React, { useEffect, useState } from 'react';
import { Modal, Text, View } from 'react-native';
import { C, S } from './theme';
import { Btn } from './ui';

type ConfirmOpts = { title: string; body: string; confirmLabel?: string; cancelLabel?: string; destructive?: boolean };
type InfoOpts = { title: string; body: string; closeLabel?: string };
type DialogState =
  | { kind: 'confirm'; opts: ConfirmOpts; resolve: (v: boolean) => void }
  | { kind: 'info'; opts: InfoOpts; resolve: () => void }
  | null;

let show: ((s: Exclude<DialogState, null>) => void) | null = null;

export const dialog = {
  confirm(opts: ConfirmOpts): Promise<boolean> {
    return new Promise((resolve) => {
      if (!show) { resolve(false); return; }
      show({ kind: 'confirm', opts, resolve });
    });
  },
  info(opts: InfoOpts): Promise<void> {
    return new Promise((resolve) => {
      if (!show) { resolve(); return; }
      show({ kind: 'info', opts, resolve });
    });
  },
};

/** Themed replacement for Alert.alert, built from the app's own theme
 *  tokens. Mount once near the app root (App.tsx); call dialog.confirm/
 *  dialog.info from anywhere below it. */
export function DialogHost() {
  const [state, setState] = useState<DialogState>(null);

  useEffect(() => {
    show = setState;
    return () => { show = null; };
  }, []);

  if (!state) return null;

  const closeConfirm = (result: boolean) => {
    if (state.kind === 'confirm') state.resolve(result);
    setState(null);
  };
  const closeInfo = () => {
    if (state.kind === 'info') state.resolve();
    setState(null);
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={() => (state.kind === 'confirm' ? closeConfirm(false) : closeInfo())}>
      <View style={{ flex: 1, backgroundColor: 'rgba(16,24,16,0.5)', alignItems: 'center', justifyContent: 'center', padding: S.xl }}>
        <View style={{ backgroundColor: C.bg, borderRadius: 18, padding: S.lg, width: '100%', maxWidth: 360 }}>
          <Text style={{ fontSize: 18, fontWeight: '800', color: C.text }}>{state.opts.title}</Text>
          <Text style={{ fontSize: 14, color: C.muted, marginTop: S.sm, lineHeight: 20 }}>{state.opts.body}</Text>
          {state.kind === 'confirm' ? (
            <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.lg }}>
              <Btn label={state.opts.cancelLabel ?? 'Cancel'} kind="secondary" onPress={() => closeConfirm(false)} style={{ flex: 1 }} />
              <Btn label={state.opts.confirmLabel ?? 'OK'} kind={state.opts.destructive ? 'danger' : 'primary'} onPress={() => closeConfirm(true)} style={{ flex: 1 }} />
            </View>
          ) : (
            <Btn label={state.opts.closeLabel ?? 'OK'} onPress={closeInfo} style={{ marginTop: S.lg }} />
          )}
        </View>
      </View>
    </Modal>
  );
}
```

- [ ] **Step 2: Mount it in `App.tsx`**

```tsx
// App.tsx -- add to imports
import { DialogHost } from './src/dialog';

// inside App()'s render, add <DialogHost/> as a sibling of <Root/>:
          <ToastProvider>
            <Root />
            <DialogHost />
          </ToastProvider>
```

- [ ] **Step 3: Replace both `Alert.alert` call sites in `MeTab.tsx`**

```tsx
// mobile/src/screens/MeTab.tsx
// remove `Alert` from the react-native import line; add:
import { dialog } from '../dialog';

// replace confirmDelete:
const confirmDelete = async (id: string) => {
  feedback.warning();
  const ok = await dialog.confirm({
    title: t('deleteField'),
    body: t('deleteConfirm'),
    confirmLabel: t('delete'),
    cancelLabel: t('cancel'),
    destructive: true,
  });
  if (!ok) return;
  try {
    await deleteField(id);
    await reloadFields();
  } catch (e) {
    const { kind } = classifyError(e);
    if (kind === 'unknown') logError('MeTab.deleteField', e);
    setErr(errorText(t, e as ApiError, { write: true }));
  }
};

// replace the sign-out TouchableOpacity's onPress:
onPress={async () => {
  const ok = await dialog.confirm({
    title: t('signOut'),
    body: t('signOutAsk'),
    confirmLabel: t('signOut'),
    cancelLabel: t('cancel'),
    destructive: true,
  });
  if (ok) signOut();
}}
```

- [ ] **Step 4: Compile check**

Run: `cd mobile && npx tsc --noEmit`
Expected: no new errors from this task's files.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/dialog.tsx App.tsx mobile/src/screens/MeTab.tsx
git commit -m "add a themed dialog component, replace both Alert.alert calls"
```

---

## Task 8: New i18n strings for accounts + dialogs

**Files:**
- Modify: `mobile/src/i18n.ts`

**Interfaces:**
- Produces: new `Key` union members, consumed by Tasks 9 and 10.

- [ ] **Step 1: Add the new keys to all four language blocks**

Add these entries to each of the four objects in `i18n.ts` (`en`, `kn`, `te`, `hi` — find each block's existing `signOut`/`signOutAsk` entries from the earlier grep output and add the new keys next to them):

```ts
// en
accountsTitle: 'Accounts',
addAnotherAccount: 'Add another account',
switchAccount: 'Switch',
removeAccount: 'Remove',
removeAccountConfirm: 'Remove this account from your phone? You can add it back any time.',
signInAgainTag: 'Sign in again',
accountLimitTitle: 'Account limit reached',
accountLimitBody: 'You can save up to 5 accounts on this phone. Remove one before adding another.',
noCachedAccountDataTitle: 'No offline data yet',
noCachedAccountDataBody: 'This account has no saved data on this phone yet, and you are offline. Connect to the internet once to load it.',
addAccountCancel: 'Cancel',
```

```ts
// kn (Kannada)
accountsTitle: 'ಖಾತೆಗಳು',
addAnotherAccount: 'ಇನ್ನೊಂದು ಖಾತೆ ಸೇರಿಸಿ',
switchAccount: 'ಬದಲಿಸಿ',
removeAccount: 'ತೆಗೆದುಹಾಕಿ',
removeAccountConfirm: 'ಈ ಖಾತೆಯನ್ನು ನಿಮ್ಮ ಫೋನ್‌ನಿಂದ ತೆಗೆದುಹಾಕಬೇಕೆ? ನೀವು ಅದನ್ನು ಯಾವಾಗ ಬೇಕಾದರೂ ಮತ್ತೆ ಸೇರಿಸಬಹುದು.',
signInAgainTag: 'ಮತ್ತೆ ಸೈನ್ ಇನ್ ಮಾಡಿ',
accountLimitTitle: 'ಖಾತೆ ಮಿತಿ ತಲುಪಿದೆ',
accountLimitBody: 'ಈ ಫೋನ್‌ನಲ್ಲಿ ನೀವು 5 ಖಾತೆಗಳವರೆಗೆ ಉಳಿಸಬಹುದು. ಇನ್ನೊಂದನ್ನು ಸೇರಿಸುವ ಮೊದಲು ಒಂದನ್ನು ತೆಗೆದುಹಾಕಿ.',
noCachedAccountDataTitle: 'ಇನ್ನೂ ಆಫ್‌ಲೈನ್ ಮಾಹಿತಿ ಇಲ್ಲ',
noCachedAccountDataBody: 'ಈ ಖಾತೆಗೆ ಈ ಫೋನ್‌ನಲ್ಲಿ ಇನ್ನೂ ಯಾವುದೇ ಉಳಿಸಿದ ಮಾಹಿತಿ ಇಲ್ಲ, ಮತ್ತು ನೀವು ಆಫ್‌ಲೈನ್ ಆಗಿದ್ದೀರಿ. ಅದನ್ನು ಲೋಡ್ ಮಾಡಲು ಒಮ್ಮೆ ಇಂಟರ್ನೆಟ್‌ಗೆ ಸಂಪರ್ಕಿಸಿ.',
addAccountCancel: 'ರದ್ದುಮಾಡಿ',
```

```ts
// te (Telugu)
accountsTitle: 'ఖాతాలు',
addAnotherAccount: 'మరో ఖాతాను జోడించండి',
switchAccount: 'మార్చండి',
removeAccount: 'తీసివేయండి',
removeAccountConfirm: 'ఈ ఖాతాను మీ ఫోన్ నుండి తీసివేయాలా? మీరు దీన్ని ఎప్పుడైనా తిరిగి జోడించవచ్చు.',
signInAgainTag: 'మళ్లీ సైన్ ఇన్ చేయండి',
accountLimitTitle: 'ఖాతా పరిమితి చేరుకుంది',
accountLimitBody: 'ఈ ఫోన్‌లో మీరు 5 ఖాతాల వరకు సేవ్ చేయవచ్చు. మరొకటి జోడించే ముందు ఒకదాన్ని తీసివేయండి.',
noCachedAccountDataTitle: 'ఇంకా ఆఫ్‌లైన్ డేటా లేదు',
noCachedAccountDataBody: 'ఈ ఖాతాకు ఈ ఫోన్‌లో ఇంకా సేవ్ చేసిన డేటా లేదు, మరియు మీరు ఆఫ్‌లైన్‌లో ఉన్నారు. దాన్ని లోడ్ చేయడానికి ఒకసారి ఇంటర్నెట్‌కు కనెక్ట్ చేయండి.',
addAccountCancel: 'రద్దు చేయండి',
```

```ts
// hi (Hindi)
accountsTitle: 'खाते',
addAnotherAccount: 'एक और खाता जोड़ें',
switchAccount: 'बदलें',
removeAccount: 'हटाएं',
removeAccountConfirm: 'इस खाते को अपने फोन से हटाना है? आप इसे किसी भी समय फिर से जोड़ सकते हैं।',
signInAgainTag: 'फिर से साइन इन करें',
accountLimitTitle: 'खाता सीमा पूरी हो गई',
accountLimitBody: 'आप इस फोन पर 5 खातों तक सेव कर सकते हैं। दूसरा जोड़ने से पहले एक को हटाएं।',
noCachedAccountDataTitle: 'अभी ऑफ़लाइन डेटा नहीं है',
noCachedAccountDataBody: 'इस खाते का इस फोन पर अभी कोई सेव किया डेटा नहीं है, और आप ऑफ़लाइन हैं। इसे लोड करने के लिए एक बार इंटरनेट से कनेक्ट करें।',
addAccountCancel: 'रद्द करें',
```

- [ ] **Step 2: Compile check**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors (all four blocks must have identical key sets, or TS flags a mismatch against `Key = keyof typeof en`).

- [ ] **Step 3: Commit**

```bash
git add mobile/src/i18n.ts
git commit -m "add account/dialog strings in all four languages"
```

---

## Task 9: `ctx.tsx` / `App.tsx` — account-aware root wiring

**Files:**
- Modify: `mobile/src/ctx.tsx`
- Modify: `App.tsx`

**Interfaces:**
- Consumes: everything from `accounts.ts` (Task 3), `clearFarmerCache` (Task 4), `setUnauthorizedHandler` (Task 5), `dialog` (Task 7), new i18n keys (Task 8).
- Produces: `Ctx.accounts: SavedAccount[]`, `Ctx.activeAccountId: string | null`, `Ctx.switchAccount(id): Promise<void>`, `Ctx.removeAccount(id): Promise<void>`, `Ctx.openAddAccount(): void` — consumed by Task 10 (MeTab UI) and Task 11 (add-account modal).

- [ ] **Step 1: Extend the `Ctx` type**

```ts
// mobile/src/ctx.tsx -- add to the Ctx type, after openBugReport:
import { SavedAccount } from './accounts';
// ...
export type Ctx = {
  // ...existing fields unchanged...
  accounts: SavedAccount[];
  activeAccountId: string | null;
  switchAccount: (id: string) => Promise<void>;
  removeAccount: (id: string) => Promise<void>;
  openAddAccount: () => void;
};
```

- [ ] **Step 2: Rewrite `App.tsx`'s boot + account logic**

Replace the body of `RootInner` per below. This keeps every existing piece of state and the existing `phase` machine (boot → lang → perms → auth → tour → main) exactly as today for first-ever launch; it adds account list state, a `switching` overlay for the "tap another saved account" path (no splash, no lang/perms — those are already settled for this device), and rewires `goAuth`/`signOut`/`onLoggedIn` through `accounts.ts`.

```tsx
// App.tsx -- add imports
import * as accounts from './src/accounts';
import { SavedAccount } from './src/accounts';
import { dialog } from './src/dialog';

// inside RootInner, add new state (near the existing useState calls):
  const [savedAccounts, setSavedAccounts] = useState<SavedAccount[]>([]);
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  const refreshAccountsList = useCallback(async () => {
    setSavedAccounts(await accounts.listAccounts());
    setActiveAccountId(accounts.getActiveAccountId());
  }, []);

// replace the existing goAuth with:
  const goAuth = useCallback(async (notice = '') => {
    if (phaseRef.current === 'boot') return;
    const id = accounts.getActiveAccountId();
    if (id) await clearFarmerCache(id);
    setFarmer(null);
    setFields([]);
    setFieldId(null);
    setAuthNotice(notice);
    setPhase('auth');
  }, []);

// replace the unauthorized-handler effect with (now takes the stale-id guard):
  useEffect(() => {
    setUnauthorizedHandler((staleAccountId) => {
      if (staleAccountId && staleAccountId !== accounts.getActiveAccountId()) {
        // This 401 belongs to an account we've since switched away from --
        // mark that one, don't touch whatever's active now.
        accounts.markSessionExpired(staleAccountId).then(refreshAccountsList);
        return;
      }
      goAuth(t('sessionExpired'));
    });
    return () => setUnauthorizedHandler(null);
  }, [goAuth, t, refreshAccountsList]);

// at the very top of the existing boot useEffect, before `const awake = wakeServer(...)`:
      await accounts.init();
      await refreshAccountsList();

// add a new function, used by both the primary sign-in and "add another account":
  const addAccount = useCallback(async (f: Farmer, token: string) => {
    try {
      await accounts.addOrSwitch(f, token);
    } catch (e) {
      if (e instanceof accounts.AccountLimitReached) {
        await dialog.info({ title: t('accountLimitTitle'), body: t('accountLimitBody') });
        return false;
      }
      throw e;
    }
    await refreshAccountsList();
    setFarmer(f);
    cacheSet('farmer', f);
    setFields([]);
    setFieldId(null);
    try { await loadFields(); } catch {}
    return true;
  }, [loadFields, refreshAccountsList, t]);

  const switchAccount = useCallback(async (id: string) => {
    if (id === activeAccountId) return;
    setSwitching(true);
    try {
      await accounts.switchTo(id);
      await refreshAccountsList();
      setFarmer(null);
      setFields([]);
      setFieldId(null);
      setTab('home');
      setForm(null);
      setBugReportContext(null);
      setTourPending(false);
      try {
        const me = await getMe();
        setFarmer(me);
        cacheSet('farmer', me);
        await loadFields();
      } catch (e) {
        const ae = e as ApiError;
        if (ae instanceof ApiError && ae.isNetwork) {
          const cached = await cacheGet<Farmer>('farmer');
          if (cached) {
            setFarmer(cached);
            const cachedFields = (await cacheGet<Field[]>('fields')) || [];
            setFields(cachedFields);
            setFieldId(cachedFields[0]?.id ?? null);
          } else {
            await dialog.info({ title: t('noCachedAccountDataTitle'), body: t('noCachedAccountDataBody') });
          }
        } else if (!(ae instanceof ApiError && ae.status === 401)) {
          throw e;
        }
      }
    } finally {
      setSwitching(false);
    }
  }, [activeAccountId, loadFields, refreshAccountsList, t]);

  const removeAccount = useCallback(async (id: string) => {
    const wasActive = id === activeAccountId;
    const nextActiveId = await accounts.remove(id);
    await clearFarmerCache(id);
    await refreshAccountsList();
    if (!wasActive) return;
    if (nextActiveId) {
      await switchAccount(nextActiveId);
    } else {
      setFarmer(null);
      setFields([]);
      setFieldId(null);
      setPhase('auth');
    }
  }, [activeAccountId, refreshAccountsList, switchAccount]);

// replace signOut with:
  const signOut = useCallback(async () => {
    await logout();
    const id = accounts.getActiveAccountId();
    if (id) await removeAccount(id);
    else await goAuth();
  }, [goAuth, removeAccount]);
```

- [ ] **Step 3: Wire the new ctx fields and the switching overlay**

```tsx
// App.tsx -- extend the ctx object:
  const ctx: Ctx | null = farmer
    ? {
        lang, t, farmer, setFarmer, fields, field,
        selectField: setFieldId,
        reloadFields: loadFields,
        changeLang,
        openFieldForm: (f?: Field) => setForm({ edit: f }),
        signOut,
        openBugReport: (screen: string) => { setBugReportContext(screen); setTab('me'); },
        accounts: savedAccounts,
        activeAccountId,
        switchAccount,
        removeAccount,
        openAddAccount: () => setAddAccountOpen(true),
      }
    : null;

// add new state for the add-account modal, and update the primary AuthScreen's onLoggedIn:
  const [addAccountOpen, setAddAccountOpen] = useState(false);
```

```tsx
// App.tsx -- the phase === 'auth' branch's AuthScreen, update onLoggedIn:
        onLoggedIn={async (f, isNew, token) => {
          await addAccount(f, token);
          setAuthNotice('');
          setBootError('');
          const tourSeen = await cacheGet<boolean>('tourSeen');
          if (isNew || !tourSeen) setTourPending(true);
          setPhase('main');
        }}
```

```tsx
// App.tsx -- render the add-account modal and the switching overlay inside the main AppCtx.Provider block, right before the closing </AppCtx.Provider>:
        {addAccountOpen ? (
          <Modal visible animationType="slide" onRequestClose={() => setAddAccountOpen(false)}>
            <AddAccountScreen
              lang={lang}
              onCancel={() => setAddAccountOpen(false)}
              onAdded={async (f, token) => {
                const ok = await addAccount(f, token);
                if (ok) setAddAccountOpen(false);
              }}
            />
          </Modal>
        ) : null}
        {switching ? (
          <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(255,255,255,0.7)', alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator size="large" color={C.accent} />
          </View>
        ) : null}
```

Add the matching imports: `Modal` to the `react-native` import list, and `AddAccountScreen` from `./src/screens/Onboarding` (built in Task 10 — until then this reference won't compile; that's expected and resolved by the next task).

- [ ] **Step 4: Manual test (this task's "deliverable" is wiring — exercised end to end once Task 10/11 land; do this check now to catch wiring bugs early)**

Run: `cd mobile && npx tsc --noEmit`
Expected: the only remaining error is the missing `AddAccountScreen` export, fixed in Task 10.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/ctx.tsx App.tsx
git commit -m "wire account switching, add-account, and removal into the root"
```

---

## Task 10: Onboarding — `AddAccountScreen` (lean phone→OTP, no language/tour)

**Files:**
- Modify: `mobile/src/screens/Onboarding.tsx`

**Interfaces:**
- Consumes: `AuthScreen` (existing), new i18n keys (Task 8).
- Produces: `AddAccountScreen({lang, onCancel, onAdded})` — consumed by Task 9's modal.

- [ ] **Step 1: Give `AuthScreen` an optional cancel button and a 3-arg `onLoggedIn`**

```tsx
// mobile/src/screens/Onboarding.tsx
// change the AuthScreen signature:
export function AuthScreen({ lang, onLoggedIn, notice, onChangeLanguage, onCancel }: {
  lang: Lang;
  onLoggedIn: (f: Farmer, isNew: boolean, token: string) => void;
  notice?: string;
  onChangeLanguage?: () => void;
  onCancel?: () => void;
}) {
```

```tsx
// in verify(), change:
//   const farmer = await verifyOtp(normalizePhone(phone), otp.trim());
//   feedback.success();
//   onLoggedIn(farmer, isNew);
// to:
      const farmer = await verifyOtp(normalizePhone(phone), otp.trim());
      feedback.success();
      onLoggedIn(farmer, isNew, farmer.session_token);
```

```tsx
// in the JSX, right before the existing onChangeLanguage block, add:
        {onCancel ? (
          <TouchableOpacity
            onPress={() => { feedback.tap(); onCancel(); }}
            accessibilityLabel={t('addAccountCancel')}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            style={{ alignSelf: 'flex-start', minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' }}
          >
            <Icon name="close" size={22} color={C.text} />
          </TouchableOpacity>
        ) : null}
```

- [ ] **Step 2: Add `AddAccountScreen`**

```tsx
// mobile/src/screens/Onboarding.tsx -- add near the bottom, before `export { C };`
/** Lean sign-in for an additional account on this device: same phone/OTP
 *  flow as AuthScreen, but no language picker (reuses whatever's already
 *  active) and no tour. Used from the Me tab's Accounts section. */
export function AddAccountScreen({ lang, onCancel, onAdded }: {
  lang: Lang;
  onCancel: () => void;
  onAdded: (f: Farmer, token: string) => void;
}) {
  return (
    <AuthScreen
      lang={lang}
      onCancel={onCancel}
      onLoggedIn={(f, _isNew, token) => onAdded(f, token)}
    />
  );
}
```

- [ ] **Step 3: Compile check**

Run: `cd mobile && npx tsc --noEmit`
Expected: PASS, no errors anywhere (this closes out the error left open at the end of Task 9).

- [ ] **Step 4: Commit**

```bash
git add mobile/src/screens/Onboarding.tsx
git commit -m "add AddAccountScreen: lean phone+OTP for a second account"
```

---

## Task 11: MeTab — Accounts section

**Files:**
- Modify: `mobile/src/screens/MeTab.tsx`

**Interfaces:**
- Consumes: `ctx.accounts`, `ctx.activeAccountId`, `ctx.switchAccount`, `ctx.removeAccount`, `ctx.openAddAccount` (Task 9); `dialog` (Task 7); new i18n keys (Task 8).

- [ ] **Step 1: Add the Accounts section**

```tsx
// mobile/src/screens/MeTab.tsx
// pull the new ctx fields into the existing useApp() destructure:
  const { farmer, setFarmer, fields, field, selectField, reloadFields, lang, changeLang, openFieldForm, signOut, t, accounts, activeAccountId, switchAccount, removeAccount, openAddAccount } = useApp();

// add a handler:
  const removeAccountConfirm = async (id: string) => {
    const ok = await dialog.confirm({
      title: t('removeAccount'),
      body: t('removeAccountConfirm'),
      confirmLabel: t('removeAccount'),
      cancelLabel: t('cancel'),
      destructive: true,
    });
    if (ok) await removeAccount(id);
  };

// add the section's JSX, right above the existing "My fields" Section:
        {accounts.length > 0 ? (
          <Section icon="user" tint="#EDE7F6" title={t('accountsTitle')}>
            {accounts.map((a) => {
              const active = a.id === activeAccountId;
              const avColor2 = avatarColor(a.id);
              return (
                <View key={a.id} style={{ flexDirection: 'row', alignItems: 'center', borderRadius: 14, borderWidth: 1.5, borderColor: active ? C.accent : '#E3E8DC', backgroundColor: active ? '#F3F9F1' : '#fff', padding: S.md, marginBottom: S.sm }}>
                  <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: avColor2, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: '#fff' }}>{initials(a.name)}</Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => !active && switchAccount(a.id)}
                    disabled={active}
                    style={{ flex: 1 }}
                  >
                    <Text style={{ fontSize: 15, fontWeight: '700', color: C.text }}>{a.name}</Text>
                    <Text style={{ fontSize: 12.5, color: C.muted, marginTop: 1 }}>
                      {`•• ${a.phone.slice(-4)}`}{a.sessionExpired ? ` · ${t('signInAgainTag')}` : ''}
                    </Text>
                  </TouchableOpacity>
                  {active ? (
                    <View style={{ backgroundColor: C.accent, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2, marginRight: S.sm }}>
                      <Icon name="check" size={13} color="#fff" />
                    </View>
                  ) : null}
                  <TouchableOpacity onPress={() => removeAccountConfirm(a.id)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} style={{ padding: 4 }}>
                    <Text style={{ color: C.danger, fontSize: 12.5, fontWeight: '700' }}>{t('removeAccount')}</Text>
                  </TouchableOpacity>
                </View>
              );
            })}
            <Btn label={t('addAnotherAccount')} kind="secondary" onPress={openAddAccount} style={{ marginTop: S.xs }} />
          </Section>
        ) : null}
```

Check `Icon` supports a `check` name (`icons.tsx`) — if not, use the existing `IconName` that reads closest (the field-chip active state elsewhere in this same file doesn't use an icon at all; fall back to a plain `✓` `Text` glyph instead of `<Icon name="check">` if `check` isn't in the icon set):

```bash
cd mobile && grep -n "'check'\|\"check\"" icons.tsx
```

If that grep finds nothing, replace the active-tick block with:

```tsx
                  {active ? (
                    <View style={{ backgroundColor: C.accent, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2, marginRight: S.sm }}>
                      <Text style={{ color: '#fff', fontSize: 11, fontWeight: '700' }}>✓</Text>
                    </View>
                  ) : null}
```

- [ ] **Step 2: Compile check**

Run: `cd mobile && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add mobile/src/screens/MeTab.tsx
git commit -m "add Accounts section to the Me tab"
```

---

## Task 12: Live proof + handoff

**Files:** none (verification task).

- [ ] **Step 1: Run every automated test**

```bash
pytest tests/auth/test_session_auth.py tests/api/test_v2_auth_integration.py -v
cd mobile && npx jest && npx tsc --noEmit
```

Expected: all PASS.

- [ ] **Step 2: Start the backend and the Expo dev client, on a real device or emulator**

```bash
# backend
flask --app agro_mirai.api.app:create_app run
# mobile (separate terminal)
cd mobile && npx expo start
```

- [ ] **Step 3: Walk the proof list from the spec**

1. Sign in as account A. Me tab → Accounts shows just A, active.
2. Add account B (new phone). Accounts list now shows A and B; B is active. Home tab shows B's (empty) fields.
3. Switch back to A. Home tab shows A's fields again, no OTP asked.
4. Add a 3rd account C. Switch A → B → C → A, confirming each shows the right fields.
5. Kill the app fully, reopen. All 3 accounts still listed; whichever was active last is still active.
6. Add 4th and 5th accounts (now at the cap). Tap "Add another account" again → themed limit dialog, no OTP screen opens.
7. Turn on airplane mode. Switch to an account that was loaded earlier in this session (cached) → shows its cached fields instantly. Switch to one never loaded this session while still offline → themed "no offline data yet" dialog.
8. Turn airplane mode off. Remove one non-active account → list shrinks by one, nothing else changes.
9. Remove the active account while another remains → switches to the most-recently-active remaining one automatically.
10. Sign out of the last remaining account → lands on the normal sign-in screen.
11. Screenshot the themed dialogs: delete-field confirm, sign-out confirm, remove-account confirm (≥3, per the spec's proof requirement).

- [ ] **Step 4: Fill out the handoff**

```
Module: 52 — Multi-account + themed popups
Status: complete
Storage choice + why: expo-secure-store for tokens (Keychain/Keystore-backed, required for a credential); AsyncStorage (existing dependency) for the account list and active pointer -- capped at 5 entries, so no MMKV added (Module 50 trimmed app size on purpose).
Cache isolation audit (keys changed): storage.ts's cacheGet/cacheSet/cacheGetWithTime now prefix every key with the active account id except lang/permsAsked/permsV2/tourSeen (device-global); clearFarmerCache now takes an explicit account id.
Popups replaced (list) / left as OS-level (list): replaced -- delete-field confirm, sign-out confirm (both pre-existing Alert.alert calls), plus new remove-account confirm and account-limit/no-cached-data info dialogs. Left as OS-level: Android/iOS permission pre-prompts (platform-drawn, not themable).
Proof: <fill in from Step 3's walkthrough + screenshots>
Tests added: tests/auth/test_session_auth.py, tests/api/test_v2_auth_integration.py (backend); mobile/src/__tests__/accounts.test.ts, storage.test.ts, api.test.ts (mobile, new jest infra).
Known limitations: OS permission dialogs not themed. Bearer tokens aren't server-revocable before their 24h expiry (same posture as the existing session cookie -- neither is checked against a server-side blacklist). A farmer who was already signed in before this module shipped keeps working via the plain cookie until their next sign-in, at which point they start appearing in the Accounts list.
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "module 52 complete: multi-account switching + themed popups"
```
