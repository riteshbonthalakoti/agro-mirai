import AsyncStorage from '@react-native-async-storage/async-storage';

// Module 37: local persistence for offline use.
//
// AsyncStorage (not expo-sqlite) on purpose: everything cached here is one
// farmer's small, always-read-whole JSON documents (profile, field list, the
// active field's advisories, scan history) -- there is no querying,
// filtering or joining done in SQL terms, so a relational store would only
// add a native module + schema/migration surface for no gain. The app
// already depends on AsyncStorage for preferences (onboarding/language).
//
// Every read/write is wrapped so a corrupt or unreadable cache degrades to
// "no cache" instead of throwing into the render tree.

const KEY_FARMER = 'cache:v1:farmer';
const KEY_SNAPSHOT = 'cache:v1:snapshot';
const KEY_SCANS = 'cache:v1:scanHistory';

export type CachedFarmer = { id: string; name: string; phone: string | null; photo_url?: string | null };

export type CachedSnapshot = {
  fields: any[];
  advisories: any[];
  syncedAt: number; // epoch ms of the last *successful* sync with the server
};

async function readJson<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

async function writeJson(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Best effort -- worst case the next offline open has less to show.
  }
}

export const loadFarmer = () => readJson<CachedFarmer>(KEY_FARMER);
export const saveFarmer = (f: CachedFarmer) => writeJson(KEY_FARMER, f);
export const loadSnapshot = () => readJson<CachedSnapshot>(KEY_SNAPSHOT);
export const saveSnapshot = (s: CachedSnapshot) => writeJson(KEY_SNAPSHOT, s);
export const loadScans = async () => (await readJson<any[]>(KEY_SCANS)) || [];
export const saveScans = (s: any[]) => writeJson(KEY_SCANS, s.slice(0, 50));

// Explicit sign-out / server-confirmed dead session (401): the cache belongs
// to that farmer and must not outlive their login.
export async function clearFarmerCache(): Promise<void> {
  try {
    await AsyncStorage.multiRemove([KEY_FARMER, KEY_SNAPSHOT, KEY_SCANS]);
  } catch {
    // ignore
  }
}

/** fetch() that rejects after `ms` instead of hanging forever on a dead host. */
export async function fetchWithTimeout(url: string, init: RequestInit = {}, ms = 8000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export function formatSyncedAt(ts: number | null | undefined): string {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === now.toDateString()
    ? time
    : `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })}, ${time}`;
}
