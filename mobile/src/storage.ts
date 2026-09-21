import AsyncStorage from '@react-native-async-storage/async-storage';

// Small JSON cache. Everything is wrapped so a corrupt/unavailable store
// degrades to "no cache" instead of throwing into the render tree.
const P = 'agro:v2:';

export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(P + key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export async function cacheSet(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(P + key, JSON.stringify(value));
  } catch {
    // best effort
  }
}

// Sign-out / dead session: cached data belongs to that farmer. Keeps the
// language choice (a device preference, not farmer data).
export async function clearFarmerCache(): Promise<void> {
  try {
    const keys = await AsyncStorage.getAllKeys();
    const mine = keys.filter((k) => k.startsWith(P) && k !== P + 'lang');
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
