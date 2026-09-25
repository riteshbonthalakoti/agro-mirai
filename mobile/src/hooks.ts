import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './api';
import { Key } from './i18n';
import { cacheGet, cacheSet } from './storage';

export type Load<T> = { data: T | null; error: ApiError | null; loading: boolean; fromCache: boolean; reload: () => void };

/** Fetch with a cache-first paint: cached data (if any) shows immediately and
 *  is replaced by the fresh response; on failure the cached copy stays and
 *  `error` is set, so a screen can show both "saved data" and the real reason. */
export function useLoad<T>(cacheKey: string | null, fn: () => Promise<T>, deps: unknown[]): Load<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [fromCache, setFromCache] = useState(false);
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
        const cached = await cacheGet<T>(cacheKey);
        if (alive && cached) {
          setData(cached);
          setFromCache(true);
        }
      }
      try {
        const fresh = await fnRef.current();
        if (!alive) return;
        setData(fresh);
        setFromCache(false);
        if (cacheKey) cacheSet(cacheKey, fresh);
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
  return { data, error, loading, fromCache, reload };
}

/** Human message for an ApiError, localized where the backend gives a stable code. */
export function errorText(t: (k: Key) => string, e: ApiError | null): string {
  if (!e) return '';
  if (e.isNetwork) return t('cantReachServer');
  if (e.code === 'NO_WEATHER_DATA') return t('noWeatherData');
  if (e.code === 'INSUFFICIENT_DATA') return t('insufficientData');
  if (e.status === 401) return t('sessionExpired');
  if (e.status === 429) return t('tooManyRequests');
  // raw 500s say "An unexpected error occurred"; on the free server that usually means it is busy or waking up
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
