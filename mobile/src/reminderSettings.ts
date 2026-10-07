import { cacheGet, cacheSet } from './storage';

export type ReminderSettings = {
  enabled: boolean;
  timeMinutes: number; // minutes from midnight (0-1439)
};

const DEFAULT_TIME = 7 * 60; // 7:00 AM

function key(suffix: string, accountId?: string | null): string {
  return accountId ? `reminder:${accountId}:${suffix}` : `reminder:${suffix}`;
}

export async function getReminderSettings(accountId?: string | null): Promise<ReminderSettings> {
  const enabled = await cacheGet<boolean>(key('enabled', accountId));
  const time = await cacheGet<number>(key('time', accountId));
  return {
    enabled: enabled !== false, // default true
    timeMinutes: time ?? DEFAULT_TIME,
  };
}

export async function setReminderEnabled(enabled: boolean, accountId?: string | null): Promise<void> {
  await cacheSet(key('enabled', accountId), enabled);
}

export async function setReminderTime(minutes: number, accountId?: string | null): Promise<void> {
  if (minutes < 0 || minutes > 1439) throw new Error('Invalid time');
  await cacheSet(key('time', accountId), minutes);
}
