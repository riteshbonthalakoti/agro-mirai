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

// Sign-out / dead session: cached data belongs to that farmer. Keeps the
// language choice (a device preference, not farmer data).
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
