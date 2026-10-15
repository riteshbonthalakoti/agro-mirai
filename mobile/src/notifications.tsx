import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, AppState, Image, Modal, PanResponder, Platform, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import Constants from 'expo-constants';
import { cacheGet, cacheSet } from './storage';
import { useDragToDismiss } from './hooks';
import { feedback } from './feedback';
import { C, S, levelColor } from './theme';
import { onAccountEvent } from './accountEvents';
import { Icon } from '../icons';

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
  /** Schedules a daily reminder at specified time (replaces the previous one). No-op without the OS layer/permission. */
  setDailyReminder: (title: string, body: string, fieldId?: string, accountId?: string, timeMinutes?: number) => void;
  /** Cancels all scheduled notifications (daily reminder + background alerts). Call on logout. */
  clearScheduledNotifications: () => void;
};

const Ctx = createContext<NotifCtx>({ items: [], unread: 0, notify: () => {}, openInbox: () => {}, setDailyReminder: () => {}, clearScheduledNotifications: () => {} });
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
  // When inside the app, update the badge and list silently -- never display annoying heads-up banners over the UI
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

export function NotificationsProvider({ children, t }: { children: React.ReactNode; t: (k: any) => string }) {
  const [items, setItems] = useState<Notif[]>([]);
  const [banner, setBanner] = useState<Notif | null>(null);
  const [inbox, setInbox] = useState(false);
  const anim = useRef(new Animated.Value(0)).current;
  const panY = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seen = useRef<Set<string>>(new Set());

  const panResponder = useDragToDismiss(panY, () => {
    Animated.timing(panY, {
      toValue: 400,
      duration: 200,
      useNativeDriver: true,
    }).start(() => {
      setInbox(false);
      panY.setValue(0);
    });
  }, 60);

  useEffect(() => {
    setupNotificationChannel();
    cacheGet<Notif[]>(INBOX_KEY).then((v) => {
      if (Array.isArray(v)) {
        setItems(v);
        v.forEach((n) => seen.current.add(n.id));
      }
    });
  }, []);

  const persist = (next: Notif[]) => {
    cacheSet(INBOX_KEY, next);
    return next;
  };

  const showBanner = useCallback((n: Notif) => {
    if (timer.current) clearTimeout(timer.current);
    setBanner(n);
    anim.setValue(0);
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 8 }).start();
    timer.current = setTimeout(() => {
      Animated.timing(anim, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => setBanner(null));
    }, 4500);
  }, [anim]);

  const notify = useCallback((n: { id?: string; title: string; body: string; severity?: string }) => {
    const id = n.id || `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    if (seen.current.has(id)) return; // never notify twice for the same event
    seen.current.add(id);
    const item: Notif = { id, title: n.title, body: n.body, severity: n.severity, ts: Date.now(), read: false };
    setItems((cur) => persist([item, ...cur].slice(0, MAX_ITEMS)));

    // Only fire system OS status-bar notifications when the app is in the background or killed
    if (AppState.currentState !== 'active') {
      if (Notifications) {
        Notifications.scheduleNotificationAsync({
          identifier: id,
          content: { title: n.title, body: n.body, color: C.accent, data: { id, severity: n.severity } },
          trigger: Platform.OS === 'android' ? ({ channelId: CHANNEL } as any) : null,
        }).catch(() => {});
      }
    }
  }, []);

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

  // Account lifecycle: clear on sign-out, reschedule on sign-in/switch
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

  // Pushes that arrive while the app is open, and taps on a notification.
  useEffect(() => {
    if (!Notifications) return;
    const got = Notifications.addNotificationReceivedListener((e) => {
      const c = e.request.content;
      const id = (c.data as any)?.id || `${Date.now()}`;
      if (seen.current.has(id)) return;
      seen.current.add(id);
      if (c.title) {
        const item: Notif = {
          id,
          title: c.title,
          body: c.body || '',
          severity: (c.data as any)?.severity,
          ts: Date.now(),
          read: false,
        };
        setItems((cur) => persist([item, ...cur.filter((x) => x.id !== id)].slice(0, MAX_ITEMS)));
      }
    });
    const tap = Notifications.addNotificationResponseReceivedListener(() => setInbox(true));
    return () => { got.remove(); tap.remove(); };
  }, []);

  const openInbox = useCallback(() => {
    feedback.tap();
    panY.setValue(0);
    setInbox(true);
    setItems((cur) => persist(cur.map((n) => ({ ...n, read: true }))));
  }, [panY]);

  const value = useMemo<NotifCtx>(
    () => ({ items, unread: items.filter((n) => !n.read).length, notify, openInbox, setDailyReminder, clearScheduledNotifications }),
    [items, notify, openInbox, setDailyReminder, clearScheduledNotifications],
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
          <TouchableOpacity activeOpacity={0.9} onPress={() => { setBanner(null); openInbox(); }}>
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

      <Modal visible={inbox} animationType="slide" transparent onRequestClose={() => setInbox(false)}>
        <View style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.35)' }}>
          <TouchableOpacity activeOpacity={1} onPress={() => setInbox(false)} style={{ flex: 1 }} />
          <Animated.View
            style={{
              transform: [{ translateY: panY }],
              backgroundColor: C.bg,
              borderTopLeftRadius: 24,
              borderTopRightRadius: 24,
              maxHeight: '78%',
              paddingHorizontal: S.lg,
              paddingTop: S.sm,
              paddingBottom: S.xl,
              borderTopWidth: 1,
              borderColor: C.border,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: -3 },
              shadowOpacity: 0.1,
              shadowRadius: 10,
              elevation: 12,
            }}
          >
            {/* Grab handle with PanResponder for drag-to-dismiss */}
            <View {...panResponder.panHandlers} style={{ paddingVertical: 10, alignItems: 'center', width: '100%' }}>
              <View style={{ width: 44, height: 5, borderRadius: 2.5, backgroundColor: C.border }} />
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md, paddingTop: 4 }}>
              <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontSize: 20, fontWeight: '800', color: C.text }}>{t('notifTitle')}</Text>
                {items.length > 0 ? (
                  <View style={{ backgroundColor: C.surface, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 }}>
                    <Text style={{ fontSize: 12, fontWeight: '700', color: C.muted }}>{items.length}</Text>
                  </View>
                ) : null}
              </View>
              {items.length ? (
                <TouchableOpacity
                  onPress={() => {
                    feedback.clear();
                    setItems(persist([]));
                    Notifications?.dismissAllNotificationsAsync().catch(() => {});
                  }}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  style={{ marginRight: S.md, paddingVertical: 4, paddingHorizontal: 8 }}
                >
                  <Text style={{ color: C.muted, fontWeight: '600', fontSize: 13 }}>{t('notifClear')}</Text>
                </TouchableOpacity>
              ) : null}
              <TouchableOpacity
                onPress={() => setInbox(false)}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: C.surface, alignItems: 'center', justifyContent: 'center' }}
              >
                <Icon name="close" size={16} color={C.muted} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: S.lg }}>
              {items.length === 0 ? (
                <View style={{ alignItems: 'center', paddingVertical: S.xl * 1.5 }}>
                  <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: C.surface, alignItems: 'center', justifyContent: 'center', marginBottom: S.sm }}>
                    <Icon name="bell" size={26} color={C.muted} />
                  </View>
                  <Text style={{ color: C.muted, fontSize: 15, fontWeight: '600' }}>{t('notifEmpty')}</Text>
                </View>
              ) : (
                items.map((n) => (
                  <View
                    key={n.id}
                    style={{
                      borderLeftWidth: 4,
                      borderLeftColor: levelColor(n.severity) || C.accent,
                      backgroundColor: C.surface,
                      borderWidth: 1,
                      borderColor: C.border,
                      borderRadius: 14,
                      padding: S.md,
                      marginBottom: S.sm,
                    }}
                  >
                    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                      <Text style={{ fontWeight: '700', color: C.text, fontSize: 15, flex: 1 }}>{n.title}</Text>
                      {n.severity ? (
                        <View style={{ backgroundColor: `${levelColor(n.severity)}18`, paddingHorizontal: 6, paddingVertical: 1.5, borderRadius: 6, marginLeft: 6 }}>
                          <Text style={{ fontSize: 10, fontWeight: '800', color: levelColor(n.severity), textTransform: 'uppercase' }}>{n.severity}</Text>
                        </View>
                      ) : null}
                    </View>
                    <Text style={{ color: C.muted, fontSize: 13.5, lineHeight: 19 }}>{n.body}</Text>
                    <Text style={{ color: C.muted, fontSize: 11, marginTop: 6, fontWeight: '500' }}>{new Date(n.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {new Date(n.ts).toLocaleDateString()}</Text>
                  </View>
                ))
              )}
            </ScrollView>
          </Animated.View>
        </View>
      </Modal>
    </Ctx.Provider>
  );
}
