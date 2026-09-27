import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { getAdvisories } from './api';
import { cacheGet, cacheSet } from './storage';

/** Farm alerts while the app is closed: the OS wakes this task about every 15+ minutes
 *  (Android WorkManager decides exactly when), it fetches fresh high/severe advisories
 *  and posts real system notifications. Not available in Expo Go -- needs a dev/release
 *  build. Notifications are also written to the in-app inbox so the foreground poller
 *  never announces the same advisory twice. */
export const ALERT_TASK = 'agro-alerts';
const BG_FIELD_KEY = 'bgField';
const CHANNEL = 'alerts';

const IN_EXPO_GO = Constants.executionEnvironment === 'storeClient';
const enabled = !IN_EXPO_GO && Platform.OS === 'android';

const TaskManager: typeof import('expo-task-manager') | null = enabled ? require('expo-task-manager') : null;
const BackgroundTask: typeof import('expo-background-task') | null = enabled ? require('expo-background-task') : null;
const Notifications: typeof import('expo-notifications') | null = enabled ? require('expo-notifications') : null;

// defineTask must run at module load (top level), before the app renders.
TaskManager?.defineTask(ALERT_TASK, async () => {
  try {
    const target = await cacheGet<{ id: string; name: string }>(BG_FIELD_KEY);
    if (!target || !Notifications) return BackgroundTask!.BackgroundTaskResult.Success;
    const perm = await Notifications.getPermissionsAsync();
    if (!perm.granted) return BackgroundTask!.BackgroundTaskResult.Success;

    const list = await getAdvisories(target.id, false);
    const inbox = (await cacheGet<any[]>('inbox')) || [];
    const seen = new Set(inbox.map((n) => n.id));
    const fresh = list
      .filter((a) => (a.severity === 'high' || a.severity === 'severe') && Date.now() - Date.parse(a.created_at) < 48 * 3600e3)
      .filter((a) => !seen.has(`adv-${a.id}`))
      .slice(0, 3);
    for (const a of fresh) {
      const title = `${target.name}: ${a.title}`;
      const body = (a.body_plain || a.body).slice(0, 140);
      await Notifications.scheduleNotificationAsync({
        content: { title, body, color: '#2E7D32', data: { id: `adv-${a.id}`, severity: a.severity } },
        trigger: { channelId: CHANNEL } as any,
      });
      inbox.unshift({ id: `adv-${a.id}`, title, body, severity: a.severity, ts: Date.now(), read: false });
    }
    if (fresh.length) await cacheSet('inbox', inbox.slice(0, 50));
    return BackgroundTask!.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask!.BackgroundTaskResult.Failed;
  }
});

/** Remember which field the background task should watch (call when the active field changes). */
export function setBackgroundField(id: string | undefined, name: string | undefined) {
  if (enabled && id) cacheSet(BG_FIELD_KEY, { id, name: name || '' });
}

/** Register the periodic task (idempotent). Call once after the notification permission is granted. */
export async function registerBackgroundAlerts() {
  if (!BackgroundTask || !TaskManager) return;
  try {
    if (await TaskManager.isTaskRegisteredAsync(ALERT_TASK)) return;
    await BackgroundTask.registerTaskAsync(ALERT_TASK, { minimumInterval: 15 });
  } catch {}
}
