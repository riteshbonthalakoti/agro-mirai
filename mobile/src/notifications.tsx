import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, AppState, Image, Platform, Text, TouchableOpacity, View } from 'react-native';
import Constants from 'expo-constants';
import { C, S, levelColor } from './theme';
import { onAccountEvent } from './accountEvents';

/** Notification system: one `notify()` entry point.
 *   - every alert      -> a real Android system notification (heads-up banner, sound, notification
 *                          shade), whether the app is open or not
 *   - app open         -> a transient in-app banner popup instead (the OS banner would be redundant
 *                          over the UI the farmer is already looking at)
 *   - Expo Go only     -> the OS layer is unavailable there, so the in-app banner stands in
 *   - daily reminder   -> `setDailyReminder(text)` schedules a 7:00 notification with today's advice;
 *                         the OS delivers it even when the app is closed
 *  Remote push needs a dev/release build + backend token registration --
 *  see docs/MOBILE_ONBOARDING_NOTIFICATIONS.md.
 *
 *  Module 60 (2026-10-28, user-directed): removed the in-app notification
 *  inbox (bell icon + drawer) entirely -- real Android notifications are
 *  the system of record for anything the farmer missed; the in-app layer
 *  is just a transient popup for what's happening right now. */

export type Notif = { id: string; title: string; body: string; severity?: string; ts: number };
type NotifCtx = {
  notify: (n: { id?: string; title: string; body: string; severity?: string }) => void;
  /** Schedules a daily reminder at specified time (replaces the previous one). No-op without the OS layer/permission. */
  setDailyReminder: (title: string, body: string, fieldId?: string, accountId?: string, timeMinutes?: number) => void;
  /** Cancels all scheduled notifications (daily reminder + background alerts). Call on logout. */
  clearScheduledNotifications: () => void;
};

const Ctx = createContext<NotifCtx>({ notify: () => {}, setDailyReminder: () => {}, clearScheduledNotifications: () => {} });
export const useNotifications = () => useContext(Ctx);

// Expo Go (Android, SDK 53+) logs a hard error the moment expo-notifications is
// imported (remote push was removed from Expo Go). There we skip the OS layer
// entirely and keep the in-app banner; a dev/release build loads it.
const IN_EXPO_GO = Constants.executionEnvironment === 'storeClient';
const Notifications: typeof import('expo-notifications') | null =
  IN_EXPO_GO && Platform.OS === 'android' ? null : require('expo-notifications');

const CHANNEL = 'alerts';
const DAILY_ID = 'daily-advice';

Notifications?.setNotificationHandler({
  // When inside the app, update the badge silently -- never display annoying heads-up banners over the UI
  handleNotification: async () => ({
    shouldShowBanner: false,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: true,
  }),
});

export async function setupNotificationChannel() {
  if (!Notifications || Platform.OS !== 'android') return;
  try {
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: 'Farm alerts',
      importance: Notifications.AndroidImportance.HIGH,
      lightColor: C.accent,
      vibrationPattern: [0, 200, 100, 200],
    });
  } catch {}
}

/** Called from the first-launch permissions screen. Never throws. */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!Notifications) return false;
  try {
    await setupNotificationChannel();
    const cur = await Notifications.getPermissionsAsync();
    if (cur.granted) return true;
    const res = await Notifications.requestPermissionsAsync();
    return res.granted;
  } catch {
    return false;
  }
}

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const [banner, setBanner] = useState<Notif | null>(null);
  const anim = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    setupNotificationChannel();
  }, []);

  const showBanner = useCallback((n: Notif) => {
    if (timer.current) clearTimeout(timer.current);
    setBanner(n);
    anim.setValue(0);
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 8 }).start();
    timer.current = setTimeout(() => {
      Animated.timing(anim, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => setBanner(null));
    }, 4500);
  }, [anim]);

  const dismissBanner = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    Animated.timing(anim, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => setBanner(null));
  }, [anim]);

  const notify = useCallback((n: { id?: string; title: string; body: string; severity?: string }) => {
    const id = n.id || `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    if (seen.current.has(id)) return; // never notify twice for the same event
    seen.current.add(id);

    if (AppState.currentState === 'active') {
      showBanner({ id, title: n.title, body: n.body, severity: n.severity, ts: Date.now() });
    } else if (Notifications) {
      Notifications.scheduleNotificationAsync({
        identifier: id,
        content: { title: n.title, body: n.body, color: C.accent, data: { id, severity: n.severity } },
        trigger: Platform.OS === 'android' ? ({ channelId: CHANNEL } as any) : null,
      }).catch(() => {});
    }
  }, [showBanner]);

  const setDailyReminder = useCallback((title: string, body: string, fieldId?: string, accountId?: string, timeMinutes?: number) => {
    if (!Notifications) return;
    (async () => {
      try {
        const perm = await Notifications.getPermissionsAsync();
        if (!perm.granted) return;
        await Notifications.cancelScheduledNotificationAsync(DAILY_ID).catch(() => {});
        const mins = timeMinutes ?? 7 * 60;
        const hour = Math.floor(mins / 60);
        const minute = mins % 60;
        await Notifications.scheduleNotificationAsync({
          identifier: DAILY_ID,
          content: { title, body, color: C.accent, data: { id: `daily-${new Date().toDateString()}`, fieldId, accountId } },
          trigger: { type: Notifications.SchedulableTriggerInputTypes.DAILY, hour, minute, channelId: CHANNEL },
        });
      } catch {}
    })();
  }, []);

  const clearScheduledNotifications = useCallback(() => {
    if (!Notifications) return;
    (async () => {
      try {
        await Notifications.cancelScheduledNotificationAsync(DAILY_ID).catch(() => {});
        await Notifications.cancelAllScheduledNotificationsAsync().catch(() => {});
      } catch {}
    })();
  }, []);

  // Account lifecycle: clear on sign-out
  useEffect(() => {
    const unsubscribe = onAccountEvent('accountSignedOut', () => {
      if (!Notifications) return;
      (async () => {
        try {
          await Notifications.cancelScheduledNotificationAsync(DAILY_ID).catch(() => {});
          await Notifications.cancelAllScheduledNotificationsAsync().catch(() => {});
        } catch {}
      })();
    });
    return unsubscribe;
  }, []);

  // Pushes that arrive while the app is open: dedupe only, no inbox to persist to.
  useEffect(() => {
    if (!Notifications) return;
    const got = Notifications.addNotificationReceivedListener((e) => {
      const id = (e.request.content.data as any)?.id || `${Date.now()}`;
      seen.current.add(id);
    });
    return () => { got.remove(); };
  }, []);

  const value = useMemo<NotifCtx>(
    () => ({ notify, setDailyReminder, clearScheduledNotifications }),
    [notify, setDailyReminder, clearScheduledNotifications],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {banner ? (
        <Animated.View
          style={{
            position: 'absolute', top: 48, left: S.md, right: S.md, opacity: anim,
            transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-20, 0] }) }],
          }}
        >
          <TouchableOpacity activeOpacity={0.9} onPress={dismissBanner}>
            <View style={{
              flexDirection: 'row', alignItems: 'center', backgroundColor: C.bg, borderRadius: 16, padding: S.md,
              borderWidth: 1, borderColor: C.border, borderLeftWidth: 4, borderLeftColor: levelColor(banner.severity) || C.accent,
              elevation: 4, shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
            }}>
              <Image source={require('../assets/logo-mark.png')} style={{ width: 32, height: 32, marginRight: S.md }} resizeMode="contain" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, fontWeight: '700', color: C.muted, letterSpacing: 0.5 }}>AGRO MIRAI</Text>
                <Text style={{ fontSize: 14, fontWeight: '700', color: C.text }} numberOfLines={1}>{banner.title}</Text>
                <Text style={{ fontSize: 13, color: C.muted, marginTop: 1 }} numberOfLines={2}>{banner.body}</Text>
              </View>
            </View>
          </TouchableOpacity>
        </Animated.View>
      ) : null}
    </Ctx.Provider>
  );
}
