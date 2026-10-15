import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import type { Farmer } from './api';
import { emitAccountSignedIn, emitAccountSignedOut, emitAccountSwitched } from './accountEvents';

const ACCOUNTS_KEY = 'agro:v2:accounts';
const ACTIVE_KEY = 'agro:v2:activeAccountId';
export const MAX_ACCOUNTS = 5;

// Module 56 fix: a request already in flight when a farmer finishes signing
// in (fired with the previous/no account's token, or racing the new token
// just being written) can land its 401 a moment *after* login already
// succeeded, forcing the app's sign-out handler (App.tsx's goAuth) to fire
// for a session that is, in fact, perfectly valid -- the farmer is kicked
// right back to the sign-in screen with no visible error, even though the
// login itself worked (a cold restart proves this: it lands on the
// dashboard). This grace window tells goAuth to ignore a 401-triggered
// sign-out for a few seconds right after a fresh login/account-switch; a
// session that's genuinely invalid will 401 again on the very next real
// request anyway, just not spuriously within this window.
export const LOGIN_GRACE_MS = 4000;

export function withinLoginGraceWindow(justLoggedInAt: number, now: number): boolean {
  return now - justLoggedInAt < LOGIN_GRACE_MS;
}

export type SavedAccount = {
  id: string;
  name: string;
  phone: string;
  lastActiveAt: number;
  photo_url?: string | null;
  sessionExpired?: boolean;
};

export class AccountLimitReached extends Error {}

let activeAccountId: string | null = null;
let activeToken: string | null = null;

const tokenKey = (id: string) => `account:${id}:token`;
// Degrade, never fail (project-wide doctrine): SecureStore wraps the
// Android Keystore, which has real-world failure modes on some OEM ROMs/
// first-use-on-device timing that have nothing to do with whether the
// farmer's login is otherwise valid. A plain AsyncStorage fallback is
// less hardened but still correct and still private to the app sandbox --
// far better than the farmer being stuck unable to sign in at all.
const fallbackKey = (id: string) => `account:${id}:token:fallback`;

async function setToken(id: string, token: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(tokenKey(id), token);
  } catch {
    await AsyncStorage.setItem(fallbackKey(id), token);
  }
}

async function getToken(id: string): Promise<string | null> {
  try {
    const v = await SecureStore.getItemAsync(tokenKey(id));
    if (v) return v;
  } catch {
    // fall through to the fallback below
  }
  return AsyncStorage.getItem(fallbackKey(id));
}

async function deleteToken(id: string): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(tokenKey(id));
  } catch {
    // no-op -- nothing securely stored to remove
  }
  await AsyncStorage.removeItem(fallbackKey(id));
}

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

// Call once at app start, before any request or cache read -- loads the
// active account id and token so api.ts/storage.ts can read them synchronously.
export async function init(): Promise<void> {
  try {
    activeAccountId = await AsyncStorage.getItem(ACTIVE_KEY);
    activeToken = activeAccountId ? await getToken(activeAccountId) : null;
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

// A saved account's own token, not the active one's -- used to log out an account that isn't active.
export async function getTokenFor(id: string): Promise<string | null> {
  return getToken(id);
}

export async function listAccounts(): Promise<SavedAccount[]> {
  return readList();
}

// Sign-in and add-account both call this: if the id is already saved, it's a switch not a duplicate.
export async function addOrSwitch(farmer: Farmer, token: string): Promise<void> {
  const list = await readList();
  const existing = list.find((a) => a.id === farmer.id);
  if (!existing && list.length >= MAX_ACCOUNTS) throw new AccountLimitReached();

  await setToken(farmer.id, token);
  const now = Date.now();
  const next = existing
    ? list.map((a) => (a.id === farmer.id ? { ...a, name: farmer.name, phone: farmer.phone || a.phone, photo_url: farmer.photo_url !== undefined ? farmer.photo_url : a.photo_url, lastActiveAt: now, sessionExpired: false } : a))
    : [...list, { id: farmer.id, name: farmer.name, phone: farmer.phone || '', photo_url: farmer.photo_url, lastActiveAt: now }];
  await writeList(next);
  await AsyncStorage.setItem(ACTIVE_KEY, farmer.id);

  const previousId = activeAccountId;
  activeAccountId = farmer.id;
  activeToken = token;
  if (existing) emitAccountSwitched(previousId, farmer.id);
  else emitAccountSignedIn(farmer.id);
}

export async function updateAccountProfile(id: string, updates: Partial<SavedAccount>): Promise<void> {
  const list = await readList();
  const next = list.map((a) => (a.id === id ? { ...a, ...updates } : a));
  await writeList(next);
}

// Switches to an already-saved account, no OTP. Caller reloads that account's farmer/fields.
export async function switchTo(id: string): Promise<void> {
  const list = await readList();
  const account = list.find((a) => a.id === id);
  if (!account) throw new Error(`No saved account ${id}`);

  const token = await getToken(id);
  const previousId = activeAccountId;
  await AsyncStorage.setItem(ACTIVE_KEY, id);
  activeAccountId = id;
  activeToken = token;
  await writeList(list.map((a) => (a.id === id ? { ...a, lastActiveAt: Date.now() } : a)));
  emitAccountSwitched(previousId, id);
}

// Flags an account so the Me tab shows "sign in again". Doesn't delete anything.
export async function markSessionExpired(id: string): Promise<void> {
  const list = await readList();
  await writeList(list.map((a) => (a.id === id ? { ...a, sessionExpired: true } : a)));
}

// Removes an account's token and list entry (caller also clears its cache separately).
// If it was active, switches to the most-recently-active remaining one, or returns null.
export async function remove(id: string): Promise<string | null> {
  const list = await readList();
  const remaining = list.filter((a) => a.id !== id);
  await deleteToken(id);
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
