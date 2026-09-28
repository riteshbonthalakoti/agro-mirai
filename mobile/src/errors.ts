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
