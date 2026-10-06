import { cacheGet, cacheSet } from './storage';

export type ReminderSettings = {
  enabled: boolean;
  timeMinutes: number; // minutes from midnight (0-1439)
};

const DEFAULT_TIME = 7 * 60; // 7:00 AM

export async function getReminderSettings(): Promise<ReminderSettings> {
  const enabled = await cacheGet<boolean>('reminderEnabled');
  const time = await cacheGet<number>('reminderTime');
  return {
    enabled: enabled !== false, // default true
    timeMinutes: time ?? DEFAULT_TIME,
  };
}

export async function setReminderEnabled(enabled: boolean): Promise<void> {
  await cacheSet('reminderEnabled', enabled);
}

export async function setReminderTime(minutes: number): Promise<void> {
  if (minutes < 0 || minutes > 1439) throw new Error('Invalid time');
  await cacheSet('reminderTime', minutes);
}
