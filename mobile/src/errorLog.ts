import { cacheGet, cacheSet } from './storage';

export type LoggedError = { at: number; context: string; message: string; stack?: string };

const KEY = 'errorLog';
const CAP = 50;

/** Rolling local log of unexpected errors, capped at CAP entries (oldest
 *  dropped first). Never throws -- same degrade-silently contract as
 *  cacheSet, since a logging failure must never mask the original error
 *  or crash the error boundary that's calling this. Cleared on sign-out
 *  by clearFarmerCache (this key is not in its keep-list). */
export async function logError(context: string, error: unknown): Promise<void> {
  try {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;
    const existing = (await cacheGet<LoggedError[]>(KEY)) || [];
    const next = [{ at: Date.now(), context, message, stack }, ...existing].slice(0, CAP);
    await cacheSet(KEY, next);
  } catch {
    // logging must never throw
  }
}

export async function getRecentErrors(n = 5): Promise<LoggedError[]> {
  try {
    const all = (await cacheGet<LoggedError[]>(KEY)) || [];
    return all.slice(0, n);
  } catch {
    return [];
  }
}
