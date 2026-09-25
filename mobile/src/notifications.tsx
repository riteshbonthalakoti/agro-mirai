import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, AppState, Image, Modal, Platform, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import Constants from 'expo-constants';
import { cacheGet, cacheSet } from './storage';
import { feedback } from './feedback';
import { C, S, levelColor } from './theme';

/** Notification system: one `notify()` entry point.
 *   - every alert      -> a real Android system notification (heads-up banner, sound, notification
 *                          shade), whether the app is open or not
 *   - always           -> also saved to a persistent inbox (bell in the header)
 *   - Expo Go only     -> the OS layer is unavailable there, so a themed in-app banner stands in
 *   - daily reminder   -> `setDailyReminder(text)` schedules a 7:00 notification with today's advice;
 *                         the OS delivers it even when the app is closed
 *  Remote push needs a dev/release build + backend token registration --
 *  see docs/MOBILE_ONBOARDING_NOTIFICATIONS.md. */

export type Notif = { id: string; title: string; body: string; severity?: string; ts: number; read: boolean };
type NotifCtx = {
  items: Notif[];
  unread: number;
  notify: (n: { id?: string; title: string; body: string; severity?: string }) => void;
  openInbox: () => void;
  /** Schedules the 7:00 daily reminder (replaces the previous one). No-op without the OS layer/permission. */
  setDailyReminder: (title: string, body: string) => void;
};

const Ctx = createContext<NotifCtx>({ items: [], unread: 0, notify: () => {}, openInbox: () => {}, setDailyReminder: () => {} });
export const useNotifications = () => useContext(Ctx);

// Expo Go (Android, SDK 53+) logs a hard error the moment expo-notifications is
// imported (remote push was removed from Expo Go). There we skip the OS layer
// entirely and keep the in-app banner + inbox; a dev/release build loads it.
const IN_EXPO_GO = Constants.executionEnvironment === 'storeClient';
const Notifications: typeof import('expo-notifications') | null =
  IN_EXPO_GO && Platform.OS === 'android' ? null : require('expo-notifications');

const INBOX_KEY = 'inbox';
const MAX_ITEMS = 50;
const CHANNEL = 'alerts';
const DAILY_ID = 'daily-advice';

Notifications?.setNotificationHandler({
  // Real Android notification even while the app is open (heads-up banner + shade + sound).
  handleNotification: async () => ({
    shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false,
  }),
});

export async function setupNotificationChannel() {
  if (!Notifications || Platform.OS !== 'android') return;
  try {
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: 'Farm alerts',
      importance: Notifications.AndroidImportance.HIGH,
      lightColor: '#2E7D32',
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

export function NotificationsProvider({ children, t }: { children: React.ReactNode; t: (k: any) => string }) {
  const [items, setItems] = useState<Notif[]>([]);
  const [banner, setBanner] = useState<Notif | null>(null);
  const [inbox, setInbox] = useState(false);
  const anim = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    setupNotificationChannel();
    cacheGet<Notif[]>(INBOX_KEY).then((v) => {
      if (Array.isArray(v)) { setItems(v); v.forEach((n) => seen.current.add(n.id)); }
    });
  }, []);

  const persist = (next: Notif[]) => { cacheSet(INBOX_KEY, next); return next; };

  const showBanner = useCallback((n: Notif) => {
    if (timer.current) clearTimeout(timer.current);
    setBanner(n);
    anim.setValue(0);
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 8 }).start();
    timer.current = setTimeout(() => {
      Animated.timing(anim, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => setBanner(null));
    }, 5000);
  }, [anim]);

  const notify = useCallback((n: { id?: string; title: string; body: string; severity?: string }) => {
    const id = n.id || `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    if (seen.current.has(id)) return; // never notify twice for the same event
    seen.current.add(id);
    const item: Notif = { id, title: n.title, body: n.body, severity: n.severity, ts: Date.now(), read: false };
    setItems((cur) => persist([item, ...cur].slice(0, MAX_ITEMS)));
    if (Notifications) {
      // always a real system notification; the inbox above keeps the history
      Notifications.scheduleNotificationAsync({
        content: { title: n.title, body: n.body, color: '#2E7D32', data: { id, severity: n.severity } },
        trigger: Platform.OS === 'android' ? { channelId: CHANNEL } as any : null,
      }).catch(() => {});
    } else if (AppState.currentState === 'active') {
      showBanner(item); // Expo Go: no OS layer, use the in-app banner
      feedback.notify(); // the OS plays its own sound and vibration for a real notification
    }
  }, [showBanner]);

  const setDailyReminder = useCallback((title: string, body: string) => {
    if (!Notifications) return;
    (async () => {
      try {
        const perm = await Notifications.getPermissionsAsync();
        if (!perm.granted) return;
        await Notifications.cancelScheduledNotificationAsync(DAILY_ID).catch(() => {});
        await Notifications.scheduleNotificationAsync({
          identifier: DAILY_ID,
          content: { title, body, color: '#2E7D32', data: { id: `daily-${new Date().toDateString()}` } },
          trigger: { type: Notifications.SchedulableTriggerInputTypes.DAILY, hour: 7, minute: 0, channelId: CHANNEL },
        });
      } catch {}
    })();
  }, []);

  // Pushes that arrive while the app is open, and taps on a notification.
  useEffect(() => {
    if (!Notifications) return;
    const got = Notifications.addNotificationReceivedListener((e) => {
      const c = e.request.content;
      if (c.title) notify({ id: (c.data as any)?.id, title: c.title, body: c.body || '', severity: (c.data as any)?.severity });
    });
    const tap = Notifications.addNotificationResponseReceivedListener(() => setInbox(true));
    return () => { got.remove(); tap.remove(); };
  }, [notify]);

  const openInbox = useCallback(() => {
    feedback.tap();
    setInbox(true);
    setItems((cur) => persist(cur.map((n) => ({ ...n, read: true }))));
  }, []);

  const value = useMemo<NotifCtx>(
    () => ({ items, unread: items.filter((n) => !n.read).length, notify, openInbox, setDailyReminder }),
    [items, notify, openInbox, setDailyReminder],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {banner ? (
        <Animated.View
          style={{
            position: 'absolute', top: 44, left: S.md, right: S.md, opacity: anim,
            transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-24, 0] }) }],
          }}
        >
          <TouchableOpacity activeOpacity={0.9} onPress={() => { setBanner(null); openInbox(); }}>
            <View style={{
              flexDirection: 'row', alignItems: 'center', backgroundColor: C.bg, borderRadius: 14, padding: S.md,
              borderWidth: 1, borderColor: C.border, borderLeftWidth: 5, borderLeftColor: levelColor(banner.severity) || C.accent,
              elevation: 10, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 10, shadowOffset: { width: 0, height: 4 },
            }}>
              <Image source={require('../assets/logo-mark.png')} style={{ width: 36, height: 36, marginRight: S.md }} resizeMode="contain" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, color: C.muted, letterSpacing: 0.5 }}>AGRO MIRAI</Text>
                <Text style={{ fontSize: 15, fontWeight: '700', color: C.text }} numberOfLines={1}>{banner.title}</Text>
                <Text style={{ fontSize: 13, color: C.muted }} numberOfLines={2}>{banner.body}</Text>
              </View>
            </View>
          </TouchableOpacity>
        </Animated.View>
      ) : null}

      <Modal visible={inbox} animationType="slide" transparent onRequestClose={() => setInbox(false)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(16,24,16,0.5)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: C.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '75%', padding: S.lg }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
              <Text style={{ flex: 1, fontSize: 20, fontWeight: '700', color: C.text }}>{t('notifTitle')}</Text>
              {items.length ? (
                <TouchableOpacity
                  onPress={() => {
                    feedback.clear();
                    setItems(persist([]));
                    // also empty what is still sitting in the Android notification shade
                    Notifications?.dismissAllNotificationsAsync().catch(() => {});
                  }}
                  style={{ marginRight: S.lg }}
                >
                  <Text style={{ color: C.muted }}>{t('notifClear')}</Text>
                </TouchableOpacity>
              ) : null}
              <TouchableOpacity onPress={() => setInbox(false)}>
                <Text style={{ color: C.accent, fontWeight: '700' }}>{t('close')}</Text>
              </TouchableOpacity>
            </View>
            <ScrollView>
              {items.length === 0 ? (
                <Text style={{ color: C.muted, paddingVertical: S.xl, textAlign: 'center' }}>{t('notifEmpty')}</Text>
              ) : items.map((n) => (
                <View key={n.id} style={{
                  borderLeftWidth: 4, borderLeftColor: levelColor(n.severity) || C.accent, backgroundColor: C.surface,
                  borderRadius: 10, padding: S.md, marginBottom: S.sm,
                }}>
                  <Text style={{ fontWeight: '700', color: C.text }}>{n.title}</Text>
                  <Text style={{ color: C.muted, marginTop: 2 }}>{n.body}</Text>
                  <Text style={{ color: C.muted, fontSize: 11, marginTop: 4 }}>{new Date(n.ts).toLocaleString()}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </Ctx.Provider>
  );
}
