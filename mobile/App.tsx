import React, { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Animated, Easing, Image, Modal, Platform, ScrollView, StatusBar, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import * as SplashScreen from 'expo-splash-screen';

// Keeps Android's native cold-start splash (app.json's expo-splash-screen
// config: our logo-mark on the same cream background the JS splash uses)
// on screen until AnimatedSplashScreen itself has mounted and painted a
// frame -- without this, the native splash auto-hides the instant the JS
// bundle finishes loading, which can be a beat before React has actually
// rendered anything, showing a flash of the bare window background.
SplashScreen.preventAutoHideAsync().catch(() => {});

// Top-level dev-facing boundary: catches anything anywhere in the tree
// (including boot/lang/perms/auth, before a farmer/`t` even exists) and
// shows the raw error for debugging. `MainErrorBoundary` below is the
// farmer-facing one, scoped to the main screen stack, with a friendly
// localized message and a call into the local error log.
class ErrorBoundary extends Component<{ children: React.ReactNode }, { error: string }> {
  constructor(props: any) { super(props); this.state = { error: '' }; }
  static getDerivedStateFromError(e: any) { return { error: String(e?.message || e) }; }
  componentDidCatch(e: any, info: any) { console.error('CRASH:', e?.message, info?.componentStack); }
  render() {
    if (this.state.error) {
      return (
        <View style={{ flex: 1, backgroundColor: '#fff', padding: 20, paddingTop: 60 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', color: '#b00', marginBottom: 12 }}>App Crash</Text>
          <ScrollView><Text selectable style={{ fontFamily: 'monospace', fontSize: 13, color: '#333' }}>{this.state.error}</Text></ScrollView>
        </View>
      );
    }
    return this.props.children;
  }
}

class MainErrorBoundary extends React.Component<{ t: (k: Key) => string; children: React.ReactNode }, { crashed: boolean }> {
  constructor(props: { t: (k: Key) => string; children: React.ReactNode }) {
    super(props);
    this.state = { crashed: false };
  }
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  componentDidCatch(error: Error) {
    logError('boundary', error);
  }
  render() {
    if (this.state.crashed) {
      return (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: S.lg, backgroundColor: C.bg }}>
          <Text style={{ fontSize: 16, fontWeight: '700', color: C.text, textAlign: 'center' }}>{this.props.t('crashedTitle')}</Text>
          <Text style={{ fontSize: 13, color: C.muted, textAlign: 'center', marginTop: S.sm }}>{this.props.t('crashedBody')}</Text>
        </View>
      );
    }
    return this.props.children;
  }
}
import { ApiError, Farmer, Field, getMe, listFields, logout, logoutWithToken, patchMe, setUnauthorizedHandler, subscribeNet, isOnline, wakeServer, getAdvisories } from './src/api';
import { AppCtx, Ctx, cropLabel, makeT } from './src/ctx';
import { Key, Lang, LANGS } from './src/i18n';
import { logError } from './src/errorLog';
import { applyDownloadedUpdate, checkForAppUpdate, AppUpdateInfo } from './src/updates';
import { AdviceTab } from './src/screens/AdviceTab';
import { DataTab } from './src/screens/DataTab';
import { FieldForm } from './src/screens/FieldForm';
import { HomeTab } from './src/screens/HomeTab';
import { MeTab } from './src/screens/MeTab';
import { AddAccountScreen, AuthScreen, LanguageScreen, PermissionsScreen } from './src/screens/Onboarding';
import { CoachTour, TourStep } from './src/components/CoachTour';
import { NotificationsProvider, useNotifications } from './src/notifications';
import { registerBackgroundAlerts, setBackgroundField } from './src/backgroundAlerts';
import { emitAccountSignedIn, emitAccountSignedOut, onAccountEvent } from './src/accountEvents';
import { playOnboardingClip, stopAudio } from './src/audio';
import { getReminderSettings } from './src/reminderSettings';
import { ScanTab } from './src/screens/ScanTab';
import { FirstField } from './src/screens/FirstField';
import { cacheGet, cacheSet, clearFarmerCache } from './src/storage';
import { C, S } from './src/theme';
import { Banner, Btn } from './src/ui';
import { Icon, IconName } from './icons';
import { ToastProvider } from './src/toast';
import { AnimatedSplashScreen } from './src/components/AnimatedSplashScreen';
import { feedback } from './src/feedback';
import { DialogHost, dialog } from './src/dialog';
import * as accounts from './src/accounts';
import { SavedAccount } from './src/accounts';
import { handleNotificationTap } from './src/notificationTapHandler';
import Constants from 'expo-constants';

/** One consistent top bar for every main tab: no logo, no branding -- just
 *  the active field's name, and a chip switcher when there's more than one
 *  field. Deliberately plain, per design direction: the app should feel
 *  the same at the top no matter which tab is open. */
function Header() {
  const ctx = React.useContext(AppCtx);
  if (!ctx || !ctx.field) return null;
  const { field, fields, selectField, lang } = ctx;
  const { unread, openInbox } = useNotifications();
  const bellAnim = useRef(new Animated.Value(0)).current;

  const handleBellPress = () => {
    Animated.sequence([
      Animated.timing(bellAnim, { toValue: 1, duration: 70, useNativeDriver: true }),
      Animated.timing(bellAnim, { toValue: -1, duration: 70, useNativeDriver: true }),
      Animated.timing(bellAnim, { toValue: 0.6, duration: 60, useNativeDriver: true }),
      Animated.timing(bellAnim, { toValue: -0.6, duration: 60, useNativeDriver: true }),
      Animated.timing(bellAnim, { toValue: 0, duration: 50, useNativeDriver: true }),
    ]).start();
    openInbox();
  };

  const bellRotate = bellAnim.interpolate({
    inputRange: [-1, 0, 1],
    outputRange: ['-20deg', '0deg', '20deg'],
  });

  return (
    <View style={{ paddingHorizontal: S.lg, paddingTop: S.sm, paddingBottom: S.sm, backgroundColor: C.bg, borderBottomWidth: 1, borderBottomColor: C.border }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', minHeight: 48 }}>
        <View style={{ width: 48, alignItems: 'flex-start' }}>
          <Image source={require('./assets/logo-mark.png')} style={{ width: 40, height: 40 }} resizeMode="contain" />
        </View>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={{ fontSize: 19, fontWeight: '800', color: C.text }} numberOfLines={1}>{field.name}</Text>
          {field.current_crop ? <Text style={{ fontSize: 13, color: C.muted, marginTop: 1 }} numberOfLines={1}>{cropLabel(lang, field.current_crop)}</Text> : null}
        </View>
        <View style={{ width: 48, alignItems: 'flex-end' }}>
          <TouchableOpacity onPress={handleBellPress} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} style={{ padding: 4 }}>
            <Animated.View style={{ transform: [{ rotate: bellRotate }] }}>
              <Icon name="bell" size={26} color={C.text} />
              {unread > 0 ? (
                <View style={{ position: 'absolute', top: 0, right: 0, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: C.danger, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3 }}>
                  <Text style={{ color: '#fff', fontSize: 10, fontWeight: '700' }}>{unread > 9 ? '9+' : unread}</Text>
                </View>
              ) : null}
            </Animated.View>
          </TouchableOpacity>
        </View>
      </View>
      {fields.length > 1 ? (
        // one scrollable row: with several fields the chips used to wrap into many rows and push the content off screen
        <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" style={{ marginTop: S.xs }} contentContainerStyle={{ paddingRight: S.lg }}>
          {fields.map((f) => (
            <TouchableOpacity
              key={f.id}
              onPress={() => selectField(f.id)}
              hitSlop={{ top: 6, bottom: 6, left: 2, right: 2 }}
              style={{
                borderWidth: 1, borderColor: f.id === field.id ? C.accent : C.border,
                backgroundColor: f.id === field.id ? C.accent : 'transparent',
                borderRadius: 16, paddingHorizontal: S.md, paddingVertical: 6, marginRight: S.sm,
              }}
            >
              <Text style={{ fontSize: 13, color: f.id === field.id ? C.accentText : C.muted }}>{f.name}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      ) : null}
    </View>
  );
}

type Phase = 'boot' | 'lang' | 'perms' | 'auth' | 'tour' | 'main';
type Tab = 'home' | 'data' | 'advice' | 'scan' | 'me';

function AnimatedTabPane({ active, children }: { active: boolean; children: React.ReactNode }) {
  const anim = useRef(new Animated.Value(active ? 1 : 0)).current;

  useEffect(() => {
    if (active) {
      anim.setValue(0);
      Animated.timing(anim, {
        toValue: 1,
        duration: 180,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
    }
  }, [active, anim]);

  if (!active) return null;

  return (
    <Animated.View
      style={{
        flex: 1,
        opacity: anim,
        transform: [
          {
            translateY: anim.interpolate({
              inputRange: [0, 1],
              outputRange: [6, 0],
            }),
          },
        ],
      }}
    >
      {children}
    </Animated.View>
  );
}

function TabBarButton({
  label,
  icon,
  on,
  onPress,
  tabRef,
}: {
  label: string;
  icon: IconName;
  on: boolean;
  onPress: () => void;
  tabRef: (r: any) => void;
}) {
  const scale = useRef(new Animated.Value(on ? 1.05 : 1)).current;

  useEffect(() => {
    Animated.spring(scale, {
      toValue: on ? 1.05 : 1,
      tension: 120,
      friction: 12,
      useNativeDriver: true,
    }).start();
  }, [on, scale]);

  return (
    <View ref={tabRef} collapsable={false} style={{ flex: 1 }}>
      <TouchableOpacity
        onPress={onPress}
        activeOpacity={0.75}
        style={{ paddingTop: 8, paddingBottom: 10, alignItems: 'center' }}
      >
        <View
          style={{
            height: 3,
            width: 28,
            borderRadius: 2,
            marginBottom: 6,
            backgroundColor: on ? C.accent : 'transparent',
          }}
        />
        <Animated.View style={{ alignItems: 'center', transform: [{ scale }] }}>
          <Icon name={icon} size={24} color={on ? C.accent : C.muted} />
          <Text
            style={{
              fontSize: 11,
              marginTop: 3,
              fontWeight: on ? '700' : '500',
              color: on ? C.accent : C.muted,
            }}
            numberOfLines={1}
          >
            {label}
          </Text>
        </Animated.View>
      </TouchableOpacity>
    </View>
  );
}

const isLang = (v: unknown): v is Lang => LANGS.some((l) => l.code === v);

export default function App() {
  const [updateInfo, setUpdateInfo] = useState<AppUpdateInfo | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const dialogScale = useRef(new Animated.Value(0.88)).current;
  const dialogOpacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    checkForAppUpdate().then(setUpdateInfo);
  }, []);
  useEffect(() => {
    if (updateInfo && !dismissed) {
      Animated.parallel([
        Animated.timing(dialogOpacity, { toValue: 1, duration: 240, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.spring(dialogScale, { toValue: 1, friction: 7, tension: 60, useNativeDriver: true }),
      ]).start();
    }
  }, [updateInfo, dismissed]);

  const showUpdateDialog = !!updateInfo && !dismissed;

  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <StatusBar barStyle="dark-content" backgroundColor={C.bg} />
        <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }} edges={['top', 'bottom']}>
          <ToastProvider>
            <Root />
            <DialogHost />
            {showUpdateDialog ? (
              // A fetched update applies on next cold start regardless; this
              // dialog lets the farmer pick the moment (not mid-form) rather
              // than it silently happening on some future unnoticed relaunch.
              // "Later" only dismisses this session's prompt, never forces a reload.
              <Modal visible transparent animationType="none" onRequestClose={() => setDismissed(true)}>
                <View style={{ flex: 1, backgroundColor: 'rgba(10,18,10,0.65)', alignItems: 'center', justifyContent: 'center', padding: S.xl }}>
                  <Animated.View style={{
                    width: '100%', maxWidth: 360,
                    opacity: dialogOpacity,
                    transform: [{ scale: dialogScale }],
                  }}>
                    {/* Header band — forest green matching HeroHeader */}
                    <View style={{ backgroundColor: '#1B4332', borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: S.lg, paddingTop: S.lg, paddingBottom: S.md }}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: S.sm }}>
                        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#74C69D', alignItems: 'center', justifyContent: 'center' }}>
                          <Text style={{ fontSize: 18 }}>🌿</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.6)', letterSpacing: 1, textTransform: 'uppercase' }}>Agro Mirai</Text>
                          <Text style={{ fontSize: 18, fontWeight: '800', color: '#FFFFFF', marginTop: 1 }}>New update ready</Text>
                        </View>
                      </View>
                    </View>
                    {/* Body card */}
                    <View style={{ backgroundColor: '#FFFFFF', borderBottomLeftRadius: 22, borderBottomRightRadius: 22, padding: S.lg }}>
                      {/* Version badge */}
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: S.sm, marginBottom: S.md }}>
                        <View style={{ backgroundColor: '#E8F5E9', borderRadius: 8, paddingHorizontal: S.sm, paddingVertical: 4 }}>
                          <Text style={{ fontSize: 12, fontWeight: '700', color: '#2E7D32' }}>✓  Downloaded</Text>
                        </View>
                        {updateInfo?.publishedAt ? (
                          <Text style={{ fontSize: 12, color: '#888', flex: 1 }}>
                            {updateInfo.publishedAt.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
                          </Text>
                        ) : null}
                      </View>
                      {/* What's in the update */}
                      <Text style={{ fontSize: 15, fontWeight: '700', color: '#1A1D19', marginBottom: S.xs }}>What's new</Text>
                      <View style={{ gap: 6, marginBottom: S.md }}>
                        {[
                          'Bug fixes & performance improvements',
                          'Better crop advisory accuracy',
                          'Smoother offline experience',
                        ].map((item) => (
                          <View key={item} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
                            <Text style={{ color: '#2E7D32', fontSize: 14, marginTop: 1 }}>•</Text>
                            <Text style={{ fontSize: 13, color: '#444', flex: 1, lineHeight: 20 }}>{item}</Text>
                          </View>
                        ))}
                      </View>
                      {/* Warning note */}
                      <View style={{ backgroundColor: '#FFF8E1', borderRadius: 10, padding: S.sm, marginBottom: S.md, flexDirection: 'row', gap: 8 }}>
                        <Text style={{ fontSize: 14 }}>⚠️</Text>
                        <Text style={{ fontSize: 12, color: '#7A5800', flex: 1, lineHeight: 18 }}>
                          Restarting will apply the update immediately. Any unsaved entries on the current screen will be lost.
                        </Text>
                      </View>
                      {/* Actions */}
                      <View style={{ flexDirection: 'row', gap: S.sm }}>
                        <TouchableOpacity
                          onPress={() => setDismissed(true)}
                          disabled={restarting}
                          style={{ flex: 1, paddingVertical: 13, borderRadius: 12, borderWidth: 1.5, borderColor: '#D8E6D0', alignItems: 'center' }}
                        >
                          <Text style={{ fontSize: 15, fontWeight: '600', color: '#666D64' }}>Later</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          onPress={() => {
                            setRestarting(true);
                            applyDownloadedUpdate().catch(() => setRestarting(false));
                          }}
                          disabled={restarting}
                          style={{ flex: 2, paddingVertical: 13, borderRadius: 12, backgroundColor: '#2E7D32', alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 8 }}
                        >
                          {restarting
                            ? <ActivityIndicator color="#FFF" size="small" />
                            : <Text style={{ fontSize: 15, fontWeight: '700', color: '#FFFFFF' }}>Restart & update</Text>
                          }
                        </TouchableOpacity>
                      </View>
                    </View>
                  </Animated.View>
                </View>
              </Modal>
            ) : null}
          </ToastProvider>
        </SafeAreaView>
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}

function Root() {
  const [lang, setLang] = useState<Lang>('en');
  return (
    <NotificationsProvider t={makeT(lang)}>
      <RootInner lang={lang} setLang={setLang} />
    </NotificationsProvider>
  );
}

function RootInner({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const [phase, setPhase] = useState<Phase>('boot');
  const [tourPending, setTourPending] = useState(false);
  const phaseRef = useRef<Phase>('boot');
  phaseRef.current = phase;
  // See accounts.ts's withinLoginGraceWindow doc comment for why this exists.
  const justLoggedInAtRef = useRef(0);
  const tabRefs = useRef<Record<string, View | null>>({});
  const { notify, clearScheduledNotifications, setDailyReminder } = useNotifications();
  const [farmer, setFarmer] = useState<Farmer | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [fieldId, setFieldId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('home');
  const [bugReportContext, setBugReportContext] = useState<string | null>(null);
  const [form, setForm] = useState<{ edit?: Field } | null>(null);
  const [online, setOnline] = useState(isOnline());
  const [authNotice, setAuthNotice] = useState('');
  const [bootError, setBootError] = useState('');
  const [waking, setWaking] = useState(false);
  const [savedAccounts, setSavedAccounts] = useState<SavedAccount[]>([]);
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);
  const [addAccountOpen, setAddAccountOpen] = useState(false);

  const refreshAccountsList = useCallback(async () => {
    setSavedAccounts(await accounts.listAccounts());
    setActiveAccountId(accounts.getActiveAccountId());
  }, []);

  const t = useMemo(() => makeT(lang), [lang]);
  const field = fields.find((f) => f.id === fieldId) ?? fields[0] ?? null;

  useEffect(() => subscribeNet(setOnline), []);

  // Reschedule notifications when signing in or switching accounts
  useEffect(() => {
    const unsubIn = onAccountEvent('accountSignedIn', () => {
      if (field && farmer) {
        (async () => {
          const settings = await getReminderSettings(farmer.id);
          if (!settings.enabled) {
            clearScheduledNotifications();
            return;
          }
          const title = `${field.name}: Daily Reminder`;
          const body = (await getAdvisories(field.id, false).catch(() => null))?.[0]?.title || `Check your ${cropLabel(lang, field.current_crop || '')} field`;
          setDailyReminder(title, body, field.id, farmer.id, settings.timeMinutes);
        })();
      }
    });
    const unsubSwitch = onAccountEvent('accountSwitched', () => {
      if (field && farmer) {
        (async () => {
          const settings = await getReminderSettings(farmer.id);
          if (!settings.enabled) {
            clearScheduledNotifications();
            return;
          }
          const title = `${field.name}: Daily Reminder`;
          const body = (await getAdvisories(field.id, false).catch(() => null))?.[0]?.title || `Check your ${cropLabel(lang, field.current_crop || '')} field`;
          setDailyReminder(title, body, field.id, farmer.id, settings.timeMinutes);
        })();
      }
    });
    return () => { unsubIn(); unsubSwitch(); };
  }, [field, farmer, lang, setDailyReminder, clearScheduledNotifications]);

  const goAuth = useCallback(async (notice = '') => {
    // A 401 during boot just means "not signed in": the boot sequence handles it
    // itself (language -> permissions -> sign-in), with no "session ended" notice.
    if (phaseRef.current === 'boot') return;
    if (accounts.withinLoginGraceWindow(justLoggedInAtRef.current, Date.now())) return;
    // Emit sign-out event before clearing state (notifications listener needs to know who signed out)
    if (farmer) emitAccountSignedOut(farmer.id);
    clearScheduledNotifications();
    setBackgroundField(undefined, undefined);
    const id = accounts.getActiveAccountId();
    if (id) {
      await accounts.markSessionExpired(id);
      await clearFarmerCache(id);
    }
    setFarmer(null);
    setFields([]);
    setFieldId(null);
    setAuthNotice(notice);
    setPhase('auth');
  }, [clearScheduledNotifications, farmer]);

  // A 401 from any request means the server-side session is gone -- unless
  // it was captured under an account we've since switched away from, in
  // which case it's stale and shouldn't boot the account that's active now.
  useEffect(() => {
    setUnauthorizedHandler((staleAccountId) => {
      if (staleAccountId && staleAccountId !== accounts.getActiveAccountId()) {
        accounts.markSessionExpired(staleAccountId).then(refreshAccountsList);
        return;
      }
      goAuth(t('sessionExpired'));
    });
    return () => setUnauthorizedHandler(null);
  }, [goAuth, t, refreshAccountsList]);

  const loadFields = useCallback(async () => {
    try {
      const list = await listFields();
      setFields(list);
      setFieldId((cur) => (cur && list.some((f) => f.id === cur) ? cur : list[0]?.id ?? null));
      cacheSet('fields', list);
    } catch (e) {
      if (e instanceof ApiError && e.isNetwork) {
        const cached = await cacheGet<Field[]>('fields');
        if (cached) { setFields(cached); setFieldId((cur) => cur ?? cached[0]?.id ?? null); }
      } else if (!(e instanceof ApiError && e.status === 401)) {
        throw e;
      }
    }
  }, []);

  // Boot: saved language -> existing session (GET /v2/farmers/me) -> main.
  const [splashDone, setSplashDone] = useState(false);
  const [pendingPhase, setPendingPhase] = useState<Phase | null>(null);

  useEffect(() => {
    (async () => {
      const awake = wakeServer(() => setWaking(true));
      await accounts.init();
      await refreshAccountsList();
      const saved = await cacheGet<string>('lang');
      if (isLang(saved)) setLang(saved);
      try {
        await awake;
        setWaking(false);
        const me = await getMe();
        setFarmer(me);
        cacheSet('farmer', me);
        emitAccountSignedIn(me.id);
        if (isLang(me.preferred_language)) { setLang(me.preferred_language); cacheSet('lang', me.preferred_language); }
        await loadFields();
        // people who were already signed in before notifications existed never saw the permission
        // screen: ask everything once here too (per-install, remembered in permsV2)
        setPendingPhase((await cacheGet<boolean>('permsV2')) ? 'main' : 'perms');
      } catch (e) {
        const ae = e as ApiError;
        if (ae.status === 401) {
          // Not signed in (fresh install, cleared data, or ended session):
          // after the splash, ask for the language, then permissions (first time only), then sign-in.
          const bootId = accounts.getActiveAccountId();
          if (bootId) await clearFarmerCache(bootId);
          setPendingPhase('lang');
          return;
        }
        const cachedFarmer = await cacheGet<Farmer>('farmer');
        if (cachedFarmer) {
          setFarmer(cachedFarmer);
          const cachedFields = (await cacheGet<Field[]>('fields')) || [];
          setFields(cachedFields);
          setFieldId(cachedFields[0]?.id ?? null);
          setPendingPhase((await cacheGet<boolean>('permsV2')) ? 'main' : 'perms');
        } else {
          setBootError(ae.isNetwork ? makeT(isLang(saved) ? saved : 'en')('cantReachServer') : ae.message);
          setPendingPhase(isLang(saved) ? 'auth' : 'lang');
        }
      }
    })();
  }, [loadFields, refreshAccountsList]);

  // Transition from boot to the target phase once the 3-second animated splash completes
  useEffect(() => {
    if (splashDone && pendingPhase) {
      setPhase(pendingPhase);
    }
  }, [splashDone, pendingPhase]);

  const changeLang = useCallback((l: Lang) => {
    setLang(l);
    cacheSet('lang', l);
  }, []);

  const addAccount = useCallback(async (f: Farmer, token: string) => {
    try {
      await accounts.addOrSwitch(f, token);
    } catch (e) {
      if (e instanceof accounts.AccountLimitReached) {
        await dialog.info({ title: t('accountLimitTitle'), body: t('accountLimitBody') });
        return false;
      }
      throw e;
    }
    await refreshAccountsList();
    setFarmer(f);
    cacheSet('farmer', f);
    setFields([]);
    setFieldId(null);
    try { await loadFields(); } catch {}
    return true;
  }, [loadFields, refreshAccountsList, t]);

  const switchAccount = useCallback(async (id: string) => {
    if (id === activeAccountId) return;
    // Never null out `farmer` here: ctx (and the whole main render) is
    // gated on `farmer` being set, so doing that would drop straight to
    // the full sign-in screen for the duration of the switch instead of
    // showing the `switching` overlay. The previous account's data stays
    // on screen, under the overlay, until the new account's data (fresh
    // or cached) is ready to replace it.
    const previousId = activeAccountId;
    setSwitching(true);
    try {
      await accounts.switchTo(id);
      await refreshAccountsList();
      setTab('home');
      setForm(null);
      setBugReportContext(null);
      setTourPending(false);
      try {
        const me = await getMe();
        setFarmer(me);
        cacheSet('farmer', me);
        await loadFields();
      } catch (e) {
        const ae = e as ApiError;
        if (ae instanceof ApiError && ae.isNetwork) {
          const cached = await cacheGet<Farmer>('farmer');
          if (cached) {
            setFarmer(cached);
            const cachedFields = (await cacheGet<Field[]>('fields')) || [];
            setFields(cachedFields);
            setFieldId(cachedFields[0]?.id ?? null);
          } else {
            // Nothing to show for this account at all (never synced, and
            // offline right now) -- revert to the account we were already
            // on rather than leave the active pointer pointed at an
            // account whose data never actually loaded.
            if (previousId) {
              await accounts.switchTo(previousId);
              await refreshAccountsList();
            }
            await dialog.info({ title: t('noCachedAccountDataTitle'), body: t('noCachedAccountDataBody') });
          }
        } else if (!(ae instanceof ApiError && ae.status === 401)) {
          throw e;
        }
      }
    } finally {
      setSwitching(false);
    }
  }, [activeAccountId, loadFields, refreshAccountsList, t]);

  const removeAccount = useCallback(async (id: string) => {
    const wasActive = id === activeAccountId;
    // That account's own token, not whatever's active right now -- accounts.remove
    // below deletes the stored token, so this has to happen first.
    const token = await accounts.getTokenFor(id);
    if (token) await logoutWithToken(token);
    const nextActiveId = await accounts.remove(id);
    await clearFarmerCache(id);
    await refreshAccountsList();
    if (!wasActive) return;
    if (nextActiveId) {
      await switchAccount(nextActiveId);
    } else {
      setFarmer(null);
      setFields([]);
      setFieldId(null);
      setPhase('auth');
    }
  }, [activeAccountId, refreshAccountsList, switchAccount]);

  const signOut = useCallback(async () => {
    clearScheduledNotifications();
    setBackgroundField(undefined, undefined);
    const id = accounts.getActiveAccountId();
    if (id) {
      // removeAccount already tells the server for us, with this account's own token.
      await removeAccount(id);
    } else {
      // No saved account at all -- a farmer who signed in before this module
      // existed, still on the plain cookie.
      await logout();
      await goAuth();
    }
  }, [goAuth, removeAccount, clearScheduledNotifications]);

  // Handle notification taps: route to field or auth if account missing
  useEffect(() => {
    const IN_EXPO_GO = Constants.executionEnvironment === 'storeClient';
    const Notifications = IN_EXPO_GO && Platform.OS === 'android' ? null : require('expo-notifications');
    if (!Notifications) return;
    const tap = Notifications.addNotificationResponseReceivedListener(async (e: any) => {
      await handleNotificationTap(e.notification.request.content.data, accounts.listAccounts, goAuth, switchAccount, setTab, activeAccountId);
    });
    return () => tap.remove();
  }, [activeAccountId, switchAccount, goAuth]);

  const ctx: Ctx | null = farmer
    ? {
        lang, t, farmer, setFarmer, fields, field,
        selectField: setFieldId,
        reloadFields: loadFields,
        changeLang,
        openFieldForm: (f?: Field) => setForm({ edit: f }),
        signOut,
        openBugReport: (screen: string) => { setBugReportContext(screen); setTab('me'); },
        accounts: savedAccounts,
        activeAccountId,
        switchAccount,
        removeAccount,
        openAddAccount: () => {
          if (savedAccounts.length >= accounts.MAX_ACCOUNTS) {
            dialog.info({ title: t('accountLimitTitle'), body: t('accountLimitBody') });
            return;
          }
          setAddAccountOpen(true);
        },
      }
    : null;

  // Farm alerts: turn fresh high/severe advisories into notifications.
  const fieldIdForAlerts = field?.id;
  const fieldNameForAlerts = field?.name;
  useEffect(() => {
    if (phase !== 'main' || !fieldIdForAlerts) return;
    setBackgroundField(fieldIdForAlerts, fieldNameForAlerts); // so alerts still arrive when the app is closed
    registerBackgroundAlerts();
    let stop = false;
    const check = async () => {
      try {
        const list = await getAdvisories(fieldIdForAlerts, false);
        if (stop) return;
        list
          .filter((a) => (a.severity === 'high' || a.severity === 'severe') && Date.now() - Date.parse(a.created_at) < 48 * 3600e3)
          .slice(0, 3)
          .forEach((a) => notify({ id: `adv-${a.id}`, title: `${fieldNameForAlerts}: ${a.title}`, body: (a.body_plain || a.body).slice(0, 140), severity: a.severity }));
      } catch {}
    };
    check();
    const id = setInterval(check, 15 * 60 * 1000);
    return () => { stop = true; clearInterval(id); };
  }, [phase, fieldIdForAlerts, fieldNameForAlerts, notify]);

  const TOUR_CLIPS: Record<string, 'tour_home' | 'tour_data' | 'tour_advice' | 'tour_scan' | 'tour_me' | undefined> = {
    home: 'tour_home', data: 'tour_data', advice: 'tour_advice', scan: 'tour_scan', me: 'tour_me',
  };
  const tourSteps: TourStep[] = useMemo(() => ([
    { key: 'home', title: t('tabHome'), body: t('tourBody_tour_home' as any) },
    { key: 'data', title: t('tabData'), body: t('tourBody_tour_data' as any) },
    { key: 'advice', title: t('tabAdvice'), body: t('tourBody_tour_advice' as any) },
    { key: 'scan', title: t('tabScan'), body: t('tourBody_tour_scan' as any) },
    { key: 'me', title: t('tabMe'), body: t('tourBody_tour_me' as any) },
  ]), [t]);
  const onTourStep = useCallback((key: string) => {
    setTab(key as Tab);
    const clip = TOUR_CLIPS[key];
    stopAudio().catch(() => {});
    if (clip) playOnboardingClip(clip, lang).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);
  const finishTour = useCallback(() => {
    stopAudio().catch(() => {});
    cacheSet('tourSeen', true);
    setTourPending(false);
    setTab('home');
  }, []);
  const getTourTarget = useCallback((k: string) => tabRefs.current[k] ?? null, []);

  if (phase === 'boot') {
    return <AnimatedSplashScreen onFinish={() => setSplashDone(true)} serverWaking={waking} />;
  }
  if (phase === 'lang') {
    return (
      <LanguageScreen
        onPick={async (l) => {
          changeLang(l);
          // Permissions are only asked the first time on this device.
          const asked = await cacheGet<boolean>('permsAsked');
          setPhase(asked ? 'auth' : 'perms');
        }}
      />
    );
  }
  if (phase === 'perms') {
    return <PermissionsScreen lang={lang} onDone={() => { cacheSet('permsAsked', true); cacheSet('permsV2', true); setPhase(farmer ? 'main' : 'auth'); }} />;
  }
  if (phase === 'auth' || !ctx) {
    return (
      <AuthScreen
        lang={lang}
        onChangeLanguage={() => setPhase('lang')}
        notice={authNotice || bootError}
        onLoggedIn={async (f, isNew, token) => {
          await addAccount(f, token);
          try { await patchMe({ preferred_language: lang }); } catch {}
          setAuthNotice('');
          setBootError('');
          // Tied to local device state only, not whether the phone number is
          // new server-side: a fresh install or "clear data" resets tourSeen
          // and should show the tour again even for a returning phone number.
          const tourSeen = await cacheGet<boolean>('tourSeen');
          if (isNew || !tourSeen) setTourPending(true); // a brand-new farmer always gets the tour
          justLoggedInAtRef.current = Date.now();
          setPhase('main');
        }}
      />
    );
  }

  const finishForm = async (saved: Field) => {
    setForm(null);
    await loadFields();
    setFieldId(saved.id);
    setTab('home');
  };

  return (
    <AppCtx.Provider value={ctx}>
      <MainErrorBoundary t={t}>
      <View style={{ flex: 1 }}>
        {!online ? <Banner text={t('offlineBanner')} /> : null}
        {form ? (
          <FieldForm initial={form.edit} onDone={finishForm} onCancel={fields.length ? () => setForm(null) : undefined} />
        ) : fields.length === 0 ? (
          <FirstField name={farmer?.name || ''} t={t} onAdd={() => setForm({})} onSignOut={signOut} />
        ) : (
          <>
            <Header />
            <View style={{ flex: 1 }}>
              <AnimatedTabPane active={tab === 'home'}><HomeTab /></AnimatedTabPane>
              <AnimatedTabPane active={tab === 'data'}><DataTab /></AnimatedTabPane>
              <AnimatedTabPane active={tab === 'advice'}><AdviceTab key={field?.id} /></AnimatedTabPane>
              <AnimatedTabPane active={tab === 'scan'}><ScanTab /></AnimatedTabPane>
              <AnimatedTabPane active={tab === 'me'}>
                <MeTab
                  initialScreenContext={bugReportContext ?? undefined}
                  onConsumeScreenContext={() => setBugReportContext(null)}
                />
              </AnimatedTabPane>
            </View>
            <View style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.border, backgroundColor: C.bg }}>
              {([
                ['home', t('tabHome'), 'home'], ['data', t('tabData'), 'field'], ['advice', t('tabAdvice'), 'speaker'],
                ['scan', t('tabScan'), 'camera'], ['me', t('tabMe'), 'user'],
              ] as [Tab, string, IconName][]).map(([k, label, icon]) => (
                <TabBarButton
                  key={k}
                  label={label}
                  icon={icon}
                  on={tab === k}
                  onPress={() => { if (k !== tab) feedback.tap(); setTab(k); }}
                  tabRef={(r) => { tabRefs.current[k] = r; }}
                />
              ))}
            </View>
          </>
        )}
        {tourPending && fields.length > 0 && !form ? (
          <CoachTour
            steps={tourSteps}
            getTarget={getTourTarget}
            onStep={onTourStep}
            onDone={finishTour}
            labels={{ next: t('tourNext'), back: t('tourBack'), done: t('tourStart'), skip: t('tourSkip') }}
          />
        ) : null}
        {addAccountOpen ? (
          <Modal visible animationType="slide" onRequestClose={() => setAddAccountOpen(false)}>
            <AddAccountScreen
              lang={lang}
              onCancel={() => setAddAccountOpen(false)}
              onAdded={async (f, token) => {
                const ok = await addAccount(f, token);
                if (ok) {
                  justLoggedInAtRef.current = Date.now();
                  setAddAccountOpen(false);
                }
              }}
            />
          </Modal>
        ) : null}
        {switching ? (
          // Fully opaque, not a translucent tint over the old account's
          // screen -- a partial tint let the previous account's content
          // keep visibly shifting underneath (tab changing, data popping
          // in) while the switch was still in flight, which read as
          // several things happening at once instead of one clean swap.
          <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator size="large" color={C.accent} />
            <Text style={{ marginTop: S.md, fontSize: 15, color: C.muted }}>Switching account…</Text>
          </View>
        ) : null}
      </View>
      </MainErrorBoundary>
    </AppCtx.Provider>
  );
}
