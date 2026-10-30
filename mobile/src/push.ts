import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { registerPushToken, unregisterPushToken } from './api';
import { logError } from './errorLog';
import { cacheGet, cacheSet } from './storage';

/** Module 59: Android push notifications. Registers this device for an
 * Expo push token and sends it to the backend so it can proactively
 * notify this farmer (a disease-scan result, an irrigation sweep) even
 * with the app fully closed -- see api/push_client.py and
 * tools/push_sweep.py on the backend side. iOS/Expo Go are never
 * attempted (no credentials configured for either here). */

const IN_EXPO_GO = Constants.executionEnvironment === 'storeClient';
const LAST_SENT_KEY = 'pushTokenSent';

const Notifications: typeof import('expo-notifications') | null =
  IN_EXPO_GO || Platform.OS !== 'android' ? null : require('expo-notifications');

/** Call once after a successful sign-in. Never throws -- a push-registration
 * failure must never block login or any other farmer-facing flow. */
export async function registerForPushNotifications(): Promise<void> {
  if (!Notifications) return;
  try {
    const perm = await Notifications.getPermissionsAsync();
    let granted = perm.granted;
    if (!granted) {
      const req = await Notifications.requestPermissionsAsync();
      granted = req.granted;
    }
    if (!granted) return;

    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    if (!projectId) return;
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    if (!token) return;

    // Avoid re-POSTing the identical token on every app start -- the backend
    // upsert is idempotent either way, this just saves a request.
    const lastSent = await cacheGet<string>(LAST_SENT_KEY);
    if (lastSent === token) return;

    await registerPushToken(token);
    await cacheSet(LAST_SENT_KEY, token);
  } catch (e) {
    logError('push.registerForPushNotifications', e);
  }
}

/** Call on sign-out -- a signed-out device should stop receiving this
 * farmer's pushes immediately. */
export async function unregisterForPushNotifications(): Promise<void> {
  try {
    const lastSent = await cacheGet<string>(LAST_SENT_KEY);
    if (!lastSent) return;
    await unregisterPushToken(lastSent);
    await cacheSet(LAST_SENT_KEY, null);
  } catch (e) {
    logError('push.unregisterForPushNotifications', e);
  }
}
