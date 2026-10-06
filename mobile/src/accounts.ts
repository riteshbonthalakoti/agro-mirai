import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import type { Farmer } from './api';
import { emitAccountSignedIn, emitAccountSignedOut, emitAccountSwitched } from './accountEvents';

const ACCOUNTS_KEY = 'agro:v2:accounts';
const ACTIVE_KEY = 'agro:v2:activeAccountId';
export const MAX_ACCOUNTS = 5;

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

// Call once at app start, before any request or cache read -- loads the
// active account id and token so api.ts/storage.ts can read them synchronously.
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

// A saved account's own token, not the active one's -- used to log out an account that isn't active.
export async function getTokenFor(id: string): Promise<string | null> {
  return SecureStore.getItemAsync(tokenKey(id));
}

export async function listAccounts(): Promise<SavedAccount[]> {
  return readList();
}

// Sign-in and add-account both call this: if the id is already saved, it's a switch not a duplicate.
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

// Switches to an already-saved account, no OTP. Caller reloads that account's farmer/fields.
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
