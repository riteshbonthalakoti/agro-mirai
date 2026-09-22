import React, { Component, useCallback, useEffect, useMemo, useState } from 'react';
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
import { ApiError, Farmer, Field, getMe, listFields, logout, patchMe, setUnauthorizedHandler, subscribeNet, isOnline, wakeServer } from './src/api';
import { AppCtx, Ctx, makeT } from './src/ctx';
import { Lang, LANGS } from './src/i18n';
import { AdviceTab } from './src/screens/AdviceTab';
import { DataTab } from './src/screens/DataTab';
import { FieldForm } from './src/screens/FieldForm';
import { HomeTab } from './src/screens/HomeTab';
import { MeTab } from './src/screens/MeTab';
import { AuthScreen, LanguageScreen, PermissionsScreen, TourScreen } from './src/screens/Onboarding';
import { ScanTab } from './src/screens/ScanTab';
import { cacheGet, cacheSet, clearFarmerCache } from './src/storage';
import { C, S } from './src/theme';
import { Banner, Btn } from './src/ui';
import { Icon, IconName } from './icons';
import { ToastProvider } from './src/toast';

/** One consistent top bar for every main tab: no logo, no branding -- just
 *  the active field's name, and a chip switcher when there's more than one
 *  field. Deliberately plain, per design direction: the app should feel
 *  the same at the top no matter which tab is open. */
function Header() {
  const ctx = React.useContext(AppCtx);
  if (!ctx || !ctx.field) return null;
  const { field, fields, selectField } = ctx;
  return (
    <View style={{ paddingHorizontal: S.lg, paddingTop: S.md, paddingBottom: S.sm, backgroundColor: C.bg, borderBottomWidth: 1, borderBottomColor: C.border }}>
      <Text style={{ fontSize: 22, fontWeight: '700', color: C.text }} numberOfLines={1}>{field.name}</Text>
      {fields.length > 1 ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: S.xs }}>
          {fields.map((f) => (
            <TouchableOpacity
              key={f.id}
              onPress={() => selectField(f.id)}
              style={{
                borderWidth: 1, borderColor: f.id === field.id ? C.accent : C.border,
                backgroundColor: f.id === field.id ? C.accent : 'transparent',
                borderRadius: 14, paddingHorizontal: S.sm, paddingVertical: 4, marginRight: S.xs, marginTop: 4,
              }}
            >
              <Text style={{ fontSize: 12, color: f.id === field.id ? C.accentText : C.muted }}>{f.name}</Text>
            </TouchableOpacity>
          ))}
        </View>
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
  const [phase, setPhase] = useState<Phase>('boot');
  const [lang, setLang] = useState<Lang>('en');
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
  useEffect(() => {
    (async () => {
      // Started immediately so the server is waking while the farmer picks a
      // language / types their number, not after they tap.
      const awake = wakeServer(() => setWaking(true));
      const saved = await cacheGet<string>('lang');
      if (isLang(saved)) setLang(saved);
      if (!isLang(saved)) return setPhase('lang');
      try {
        await awake;
        setWaking(false);
        const me = await getMe();
        setFarmer(me);
        cacheSet('farmer', me);
        if (isLang(me.preferred_language)) { setLang(me.preferred_language); cacheSet('lang', me.preferred_language); }
        await loadFields();
        setPhase('main');
      } catch (e) {
        const ae = e as ApiError;
        if (ae.status === 401) return setPhase('auth');
        // Server unreachable: open with whatever was saved, clearly marked offline.
        const cachedFarmer = await cacheGet<Farmer>('farmer');
        if (cachedFarmer) {
          setFarmer(cachedFarmer);
          const cachedFields = (await cacheGet<Field[]>('fields')) || [];
          setFields(cachedFields);
          setFieldId(cachedFields[0]?.id ?? null);
          setPhase('main');
        } else {
          setBootError(ae.isNetwork ? makeT(saved)('cantReachServer') : ae.message);
          setPhase('auth');
        }
      }
    })();
  }, [loadFields]);

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

  if (phase === 'boot') {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: S.xl }}>
        <ActivityIndicator />
        {waking ? <Text style={{ color: C.muted, marginTop: S.md, textAlign: 'center' }}>{t('serverWaking')}</Text> : null}
      </View>
    );
  }
  if (phase === 'lang') {
    return <LanguageScreen onPick={(l) => { changeLang(l); setPhase('perms'); }} />;
  }
  if (phase === 'perms') {
    return <PermissionsScreen lang={lang} onDone={() => setPhase('auth')} />;
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
          const tourSeen = await cacheGet<boolean>('tourSeen');
          setPhase(isNew && !tourSeen ? 'tour' : 'main');
        }}
      />
    );
  }

  if (phase === 'tour') {
    return <TourScreen lang={lang} onDone={() => { cacheSet('tourSeen', true); setPhase('main'); }} />;
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
                  <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, paddingTop: 8, paddingBottom: 10, alignItems: 'center' }}>
                    <View style={{ height: 3, width: 28, borderRadius: 2, marginBottom: 6, backgroundColor: on ? C.accent : 'transparent' }} />
                    <Icon name={icon} size={24} color={on ? C.accent : C.muted} />
                    <Text style={{ fontSize: 11, marginTop: 3, fontWeight: on ? '700' : '400', color: on ? C.accent : C.muted }} numberOfLines={1}>
                      {label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </>
        )}
      </View>
    </AppCtx.Provider>
  );
}
