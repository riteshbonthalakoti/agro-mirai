import React, { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StatusBar, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

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
import { ApiError, Farmer, Field, getMe, listFields, logout, patchMe, setUnauthorizedHandler, subscribeNet, isOnline, wakeServer, getAdvisories } from './src/api';
import { AppCtx, Ctx, makeT } from './src/ctx';
import { Lang, LANGS } from './src/i18n';
import { AdviceTab } from './src/screens/AdviceTab';
import { DataTab } from './src/screens/DataTab';
import { FieldForm } from './src/screens/FieldForm';
import { HomeTab } from './src/screens/HomeTab';
import { MeTab } from './src/screens/MeTab';
import { AuthScreen, LanguageScreen, PermissionsScreen } from './src/screens/Onboarding';
import { CoachTour, TourStep } from './src/components/CoachTour';
import { NotificationsProvider, useNotifications } from './src/notifications';
import { playOnboardingClip, stopAudio } from './src/audio';
import { ScanTab } from './src/screens/ScanTab';
import { cacheGet, cacheSet, clearFarmerCache } from './src/storage';
import { C, S } from './src/theme';
import { Banner, Btn } from './src/ui';
import { Icon, IconName } from './icons';
import { ToastProvider } from './src/toast';
import { AnimatedSplashScreen } from './src/components/AnimatedSplashScreen';

/** One consistent top bar for every main tab: no logo, no branding -- just
 *  the active field's name, and a chip switcher when there's more than one
 *  field. Deliberately plain, per design direction: the app should feel
 *  the same at the top no matter which tab is open. */
function Header() {
  const ctx = React.useContext(AppCtx);
  if (!ctx || !ctx.field) return null;
  const { field, fields, selectField } = ctx;
  const { unread, openInbox } = useNotifications();
  return (
    <View style={{ paddingHorizontal: S.lg, paddingTop: S.md, paddingBottom: S.sm, backgroundColor: C.bg, borderBottomWidth: 1, borderBottomColor: C.border }}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Text style={{ flex: 1, fontSize: 22, fontWeight: '700', color: C.text }} numberOfLines={1}>{field.name}</Text>
        <TouchableOpacity onPress={openInbox} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} style={{ padding: 4 }}>
          <Icon name="bell" size={24} color={C.text} />
          {unread > 0 ? (
            <View style={{ position: 'absolute', top: 0, right: 0, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: C.danger, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3 }}>
              <Text style={{ color: '#fff', fontSize: 10, fontWeight: '700' }}>{unread > 9 ? '9+' : unread}</Text>
            </View>
          ) : null}
        </TouchableOpacity>
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

const isLang = (v: unknown): v is Lang => LANGS.some((l) => l.code === v);

export default function App() {
  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <StatusBar barStyle="dark-content" backgroundColor={C.bg} />
        <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }} edges={['top', 'bottom']}>
          <ToastProvider>
            <Root />
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
  const tabRefs = useRef<Record<string, View | null>>({});
  const { notify } = useNotifications();
  const [farmer, setFarmer] = useState<Farmer | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [fieldId, setFieldId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('home');
  const [form, setForm] = useState<{ edit?: Field } | null>(null);
  const [online, setOnline] = useState(isOnline());
  const [authNotice, setAuthNotice] = useState('');
  const [bootError, setBootError] = useState('');
  const [waking, setWaking] = useState(false);

  const t = useMemo(() => makeT(lang), [lang]);
  const field = fields.find((f) => f.id === fieldId) ?? fields[0] ?? null;

  useEffect(() => subscribeNet(setOnline), []);

  const goAuth = useCallback(async (notice = '') => {
    // A 401 during boot just means "not signed in": the boot sequence handles it
    // itself (language -> permissions -> sign-in), with no "session ended" notice.
    if (phaseRef.current === 'boot') return;
    await clearFarmerCache();
    setFarmer(null);
    setFields([]);
    setFieldId(null);
    setAuthNotice(notice);
    setPhase('auth');
  }, []);

  // A 401 from any request means the server-side session is gone.
  useEffect(() => {
    setUnauthorizedHandler(() => goAuth(t('sessionExpired')));
    return () => setUnauthorizedHandler(null);
  }, [goAuth, t]);

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
      const saved = await cacheGet<string>('lang');
      if (isLang(saved)) setLang(saved);
      try {
        await awake;
        setWaking(false);
        const me = await getMe();
        setFarmer(me);
        cacheSet('farmer', me);
        if (isLang(me.preferred_language)) { setLang(me.preferred_language); cacheSet('lang', me.preferred_language); }
        await loadFields();
        setPendingPhase('main');
      } catch (e) {
        const ae = e as ApiError;
        if (ae.status === 401) {
          // Not signed in (fresh install, cleared data, or ended session):
          // after the splash, ask for the language, then permissions (first time only), then sign-in.
          await clearFarmerCache();
          setPendingPhase('lang');
          return;
        }
        const cachedFarmer = await cacheGet<Farmer>('farmer');
        if (cachedFarmer) {
          setFarmer(cachedFarmer);
          const cachedFields = (await cacheGet<Field[]>('fields')) || [];
          setFields(cachedFields);
          setFieldId(cachedFields[0]?.id ?? null);
          setPendingPhase('main');
        } else {
          setBootError(ae.isNetwork ? makeT(isLang(saved) ? saved : 'en')('cantReachServer') : ae.message);
          setPendingPhase(isLang(saved) ? 'auth' : 'lang');
        }
      }
    })();
  }, [loadFields]);

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

  const signOut = useCallback(async () => {
    await logout();
    await goAuth();
  }, [goAuth]);

  const ctx: Ctx | null = farmer
    ? {
        lang, t, farmer, setFarmer, fields, field,
        selectField: setFieldId,
        reloadFields: loadFields,
        changeLang,
        openFieldForm: (f?: Field) => setForm({ edit: f }),
        signOut,
      }
    : null;

  // Farm alerts: turn fresh high/severe advisories into notifications.
  const fieldIdForAlerts = field?.id;
  const fieldNameForAlerts = field?.name;
  useEffect(() => {
    if (phase !== 'main' || !fieldIdForAlerts) return;
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

  const TOUR_CLIPS: Record<string, 'tour_home' | 'tour_data' | 'tour_advice' | 'tour_scan' | undefined> = {
    home: 'tour_home', data: 'tour_data', advice: 'tour_advice', scan: 'tour_scan',
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
    return <PermissionsScreen lang={lang} onDone={() => { cacheSet('permsAsked', true); setPhase('auth'); }} />;
  }
  if (phase === 'auth' || !ctx) {
    return (
      <AuthScreen
        lang={lang}
        notice={authNotice || bootError}
        onLoggedIn={async (f, isNew) => {
          setFarmer(f);
          cacheSet('farmer', f);
          try { await patchMe({ preferred_language: lang }); } catch {}
          try { await loadFields(); } catch {}
          setAuthNotice('');
          setBootError('');
          // Tied to local device state only, not whether the phone number is
          // new server-side: a fresh install or "clear data" resets tourSeen
          // and should show the tour again even for a returning phone number.
          const tourSeen = await cacheGet<boolean>('tourSeen');
          if (!tourSeen) setTourPending(true);
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
      <View style={{ flex: 1 }}>
        {!online ? <Banner text={t('offlineBanner')} /> : null}
        {form ? (
          <FieldForm initial={form.edit} onDone={finishForm} onCancel={fields.length ? () => setForm(null) : undefined} />
        ) : fields.length === 0 ? (
          <View style={{ flex: 1 }}>
            <View style={{ padding: S.lg, paddingTop: 64 }}>
              <Text style={{ fontSize: 22, fontWeight: '700', color: C.text }}>{t('noFieldTitle')}</Text>
              <Text style={{ color: C.muted, marginTop: S.sm }}>{t('noFieldBody')}</Text>
              <Btn label={t('addField')} onPress={() => setForm({})} style={{ marginTop: S.lg }} />
              <Btn label={t('signOut')} kind="secondary" onPress={signOut} style={{ marginTop: S.md }} />
            </View>
          </View>
        ) : (
          <>
            <Header />
            <View style={{ flex: 1 }}>
              {tab === 'home' && <HomeTab />}
              {tab === 'data' && <DataTab />}
              {tab === 'advice' && <AdviceTab />}
              {tab === 'scan' && <ScanTab />}
              {tab === 'me' && <MeTab />}
            </View>
            <View style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.border, backgroundColor: C.bg }}>
              {([
                ['home', t('tabHome'), 'home'], ['data', t('tabData'), 'field'], ['advice', t('tabAdvice'), 'speaker'],
                ['scan', t('tabScan'), 'camera'], ['me', t('tabMe'), 'user'],
              ] as [Tab, string, IconName][]).map(([k, label, icon]) => {
                const on = tab === k;
                return (
                  <View key={k} ref={(r) => { tabRefs.current[k] = r; }} collapsable={false} style={{ flex: 1 }}>
                  <TouchableOpacity onPress={() => setTab(k)} style={{ paddingTop: 8, paddingBottom: 10, alignItems: 'center' }}>
                    <View style={{ height: 3, width: 28, borderRadius: 2, marginBottom: 6, backgroundColor: on ? C.accent : 'transparent' }} />
                    <Icon name={icon} size={24} color={on ? C.accent : C.muted} />
                    <Text style={{ fontSize: 11, marginTop: 3, fontWeight: on ? '700' : '400', color: on ? C.accent : C.muted }} numberOfLines={1}>
                      {label}
                    </Text>
                  </TouchableOpacity>
                  </View>
                );
              })}
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
      </View>
    </AppCtx.Provider>
  );
}
