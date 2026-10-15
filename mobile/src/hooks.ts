import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, PanResponder, PanResponderInstance } from 'react-native';
import { ApiError, isOnline, subscribeNet } from './api';
import { Key } from './i18n';
import { cacheGet, cacheGetWithTime, cacheSet } from './storage';

export type Load<T> = { data: T | null; error: ApiError | null; loading: boolean; fromCache: boolean; lastUpdatedAt: number | null; reload: () => void };

// In-memory cache for instant 0ms tab switching without flashing skeletons or buffering
const MEM_CACHE = new Map<string, { value: any; cachedAt: number }>();

export function useLoad<T>(cacheKey: string | null, fn: () => Promise<T>, deps: unknown[]): Load<T> {
  const cachedMem = cacheKey ? (MEM_CACHE.get(cacheKey) as { value: T; cachedAt: number } | undefined) : undefined;
  const [data, setData] = useState<T | null>(cachedMem ? cachedMem.value : null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(!cachedMem);
  const [fromCache, setFromCache] = useState(!!cachedMem);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(cachedMem ? cachedMem.cachedAt : null);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const dataRef = useRef(data);
  dataRef.current = data;

  useEffect(() => {
    let alive = true;
    (async () => {
      // If we don't have data in memory yet, read from persistent storage
      if (!dataRef.current && cacheKey) {
        setLoading(true);
        const cached = await cacheGetWithTime<T>(cacheKey);
        if (alive && cached) {
          MEM_CACHE.set(cacheKey, cached);
          setData(cached.value);
          setFromCache(true);
          setLastUpdatedAt(cached.cachedAt);
          setLoading(false);
        }
      }

      // Fetch latest data silently in the background without clearing the screen
      try {
        const fresh = await fnRef.current();
        if (!alive) return;
        if (cacheKey) {
          MEM_CACHE.set(cacheKey, { value: fresh, cachedAt: Date.now() });
          await cacheSet(cacheKey, fresh);
        }
        setData(fresh);
        setFromCache(false);
        setLastUpdatedAt(Date.now());
        setError(null);
      } catch (e) {
        if (alive && !dataRef.current) {
          setError(e instanceof ApiError ? e : new ApiError(0, String(e)));
        }
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

  // Reconnect: when the app comes back online after being offline, refresh
  // a screen that's showing cached-but-stale data, without reacting to every
  // online/offline flap -- only a genuine false->true edge.
  useEffect(() => {
    let wasOffline = !isOnline();
    return subscribeNet((online) => {
      if (online && wasOffline) setTick((x) => x + 1);
      wasOffline = !online;
    });
  }, []);

  return { data, error, loading, fromCache, lastUpdatedAt, reload };
}

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

// ---- on-screen translation of server-generated English text ----------------
import { translateTexts } from './api';
import { Lang } from './i18n';

const hash = (s: string) => {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return String(h >>> 0);
};

/** Translates English strings into `lang` through the backend
 *  (POST /v2/translate). Results are cached on the device per (text, language),
 *  so switching languages back and forth is instant after the first time.
 *  `state`: 'loading' while fetching, 'failed' if the server could not
 *  translate (the original English is returned), else 'done'/'idle'. */
export function useTranslated(texts: (string | null | undefined)[], lang: Lang) {
  const clean = texts.map((t) => t || '');
  const sig = JSON.stringify(clean) + lang;
  const [out, setOut] = useState<string[]>(clean);
  const [state, setState] = useState<'idle' | 'loading' | 'failed' | 'done'>('idle');

  useEffect(() => {
    let alive = true;
    if (lang === 'en' || clean.every((t) => !t)) {
      setOut(clean);
      setState('idle');
      return;
    }
    (async () => {
      setState('loading');
      const result = [...clean];
      const missing: number[] = [];
      for (let i = 0; i < clean.length; i++) {
        if (!clean[i]) continue;
        const hit = await cacheGet<string>(`tr:${lang}:${hash(clean[i])}`);
        if (hit) result[i] = hit;
        else missing.push(i);
      }
      if (alive) setOut([...result]);
      if (missing.length === 0) {
        if (alive) setState('done');
        return;
      }
      try {
        const r = await translateTexts(missing.map((i) => clean[i]), lang);
        if (!alive) return;
        if (r.translated) {
          missing.forEach((idx, n) => {
            result[idx] = r.texts[n];
            cacheSet(`tr:${lang}:${hash(clean[idx])}`, r.texts[n]);
          });
          setOut([...result]);
          setState('done');
        } else {
          setState('failed');
        }
      } catch {
        if (alive) setState('failed');
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  return { out, state };
}

export function useDragToDismiss(
  translateY: Animated.Value,
  onDismiss: () => void,
  threshold: number = 80,
): PanResponderInstance {
  return useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, g) => g.dy > 5,
      onPanResponderMove: (_, g) => {
        if (g.dy > 0) translateY.setValue(g.dy);
      },
      onPanResponderRelease: (_, g) => {
        if (g.dy > threshold) {
          onDismiss();
        } else {
          Animated.spring(translateY, { toValue: 0, useNativeDriver: true }).start();
        }
      },
    })
  ).current;
}
