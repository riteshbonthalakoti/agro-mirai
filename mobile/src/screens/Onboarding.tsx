import React, { useEffect, useRef, useState } from 'react';
import { ImageBackground, KeyboardAvoidingView, Platform, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { requestRecordingPermissionsAsync } from 'expo-audio';
import { ApiError, Farmer, requestOtp, verifyOtp } from '../api';
import { playOnboardingClip, stopAudio } from '../audio';
import { makeT } from '../ctx';
import { Icon, IconName } from '../../icons';
import { LANGS, Lang } from '../i18n';
import { C, S } from '../theme';
import { Banner, Btn, Chip, Input, Label, Muted, st } from '../ui';

/** Requested once, right after picking a language -- so the app never
 *  interrupts the farmer with a permission dialog mid-task later. Declining
 *  is fine; every screen that actually needs one of these re-asks in context
 *  and degrades honestly (per-feature error text) if still declined. */
export function PermissionsScreen({ lang, onDone }: { lang: Lang; onDone: () => void }) {
  const t = makeT(lang);
  const [busy, setBusy] = useState(false);

  const askAll = async () => {
    setBusy(true);
    try { await Location.requestForegroundPermissionsAsync(); } catch {}
    try { await ImagePicker.requestCameraPermissionsAsync(); } catch {}
    try { await ImagePicker.requestMediaLibraryPermissionsAsync(); } catch {}
    try { await requestRecordingPermissionsAsync(); } catch {}
    setBusy(false);
    onDone();
  };

  const ROWS: { icon: IconName; titleKey: 'permLocationLabel' | 'permCamera' | 'permGallery' | 'permMic'; bodyKey: 'permLocationBody' | 'permCameraBody' | 'permGalleryBody' | 'permMicBody' }[] = [
    { icon: 'location', titleKey: 'permLocationLabel', bodyKey: 'permLocationBody' },
    { icon: 'camera', titleKey: 'permCamera', bodyKey: 'permCameraBody' },
    { icon: 'gallery', titleKey: 'permGallery', bodyKey: 'permGalleryBody' },
    { icon: 'mic', titleKey: 'permMic', bodyKey: 'permMicBody' },
  ];

  return (
    <ScrollView contentContainerStyle={{ padding: S.xl, paddingTop: 80, flexGrow: 1 }}>
      <Text style={st.h1}>{t('permTitle')}</Text>
      <Text style={[st.body, { marginTop: S.sm, marginBottom: S.xl }]}>{t('permBody')}</Text>
      {ROWS.map((r) => (
        <View key={r.titleKey} style={{ flexDirection: 'row', marginBottom: S.lg }}>
          <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: C.surface, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
            <Icon name={r.icon} size={20} color={C.accent} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: C.text }}>{t(r.titleKey)}</Text>
            <Text style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>{t(r.bodyKey)}</Text>
          </View>
        </View>
      ))}
      <View style={{ flex: 1 }} />
      <Btn label={t('permAllow')} onPress={askAll} busy={busy} style={{ marginTop: S.md }} />
      <Btn label={t('permSkip')} kind="secondary" onPress={onDone} style={{ marginTop: S.sm }} />
    </ScrollView>
  );
}

/** First-launch language pick. Big blocks, English/Telugu on top, Hindi/Kannada
 *  paired below -- tapping a block plays that language's welcome greeting from
 *  a bundled local audio file (no network, no API call). */
// Real photos (Wikimedia Commons, CC-licensed -- see assets/lang/CREDITS.md)
// of a place associated with each language: India Gate for English, Charminar
// for Telugu, Mysore Palace for Kannada, Hawa Mahal for Hindi.
const LANG_PHOTOS: Record<Lang, number> = {
  en: require('../../assets/lang/en.jpg'),
  te: require('../../assets/lang/te.jpg'),
  kn: require('../../assets/lang/kn.jpg'),
  hi: require('../../assets/lang/hi.jpg'),
};

export function LanguageScreen({ onPick }: { onPick: (l: Lang) => void }) {
  const [sel, setSel] = useState<Lang | null>(null);
  const t = makeT(sel ?? 'en');
  const byCode = Object.fromEntries(LANGS.map((l) => [l.code, l]));

  const pick = (l: Lang) => {
    setSel(l);
    playOnboardingClip('welcome', l).catch(() => {});
  };

  useEffect(() => () => { stopAudio().catch(() => {}); }, []);

  const Block = ({ code, big }: { code: Lang; big?: boolean }) => (
    <TouchableOpacity
      onPress={() => pick(code)}
      activeOpacity={0.85}
      style={{
        flex: 1,
        minHeight: big ? 110 : 96,
        borderRadius: 16,
        borderWidth: sel === code ? 3 : 1,
        borderColor: sel === code ? C.accent : C.border,
        overflow: 'hidden',
      }}
    >
      <ImageBackground source={LANG_PHOTOS[code]} style={{ flex: 1 }} imageStyle={{ opacity: sel === code ? 1 : 0.9 }}>
        <View style={{ flex: 1, backgroundColor: sel === code ? 'rgba(46,125,50,0.55)' : 'rgba(0,0,0,0.35)', alignItems: 'center', justifyContent: 'center', paddingVertical: S.md }}>
          <Text style={{ fontSize: big ? 26 : 22, fontWeight: '700', color: '#fff' }}>{byCode[code].native}</Text>
          <Text style={{ fontSize: 13, marginTop: 2, color: 'rgba(255,255,255,0.85)' }}>{byCode[code].english}</Text>
        </View>
      </ImageBackground>
    </TouchableOpacity>
  );

  return (
    <ScrollView contentContainerStyle={{ padding: S.xl, paddingTop: 80, flexGrow: 1 }}>
      <Text style={st.h1}>Agro Mirai</Text>
      <Text style={[st.body, { marginBottom: S.xl }]}>{t('chooseLanguage')}</Text>

      <Block code="en" big />
      <View style={{ height: S.md }} />
      <Block code="te" big />
      <View style={{ height: S.md }} />
      <View style={{ flexDirection: 'row', gap: S.md }}>
        <Block code="hi" />
        <Block code="kn" />
      </View>

      <View style={{ flex: 1 }} />
      <Btn label={t('continue')} onPress={() => sel && onPick(sel)} disabled={!sel} style={{ marginTop: S.xl }} />
    </ScrollView>
  );
}

const TOUR_STEPS: { clip: 'tour_home' | 'tour_data' | 'tour_advice' | 'tour_scan'; titleKey: 'tabHome' | 'tabData' | 'tabAdvice' | 'tabScan' }[] = [
  { clip: 'tour_home', titleKey: 'tabHome' },
  { clip: 'tour_data', titleKey: 'tabData' },
  { clip: 'tour_advice', titleKey: 'tabAdvice' },
  { clip: 'tour_scan', titleKey: 'tabScan' },
];

/** Narrated first-run tour shown right after signup, in the language the
 *  farmer just picked. Fully local audio, no server call. */
export function TourScreen({ lang, onDone }: { lang: Lang; onDone: () => void }) {
  const t = makeT(lang);
  const [step, setStep] = useState(0);
  const played = useRef(-1);

  useEffect(() => {
    if (played.current === step) return;
    played.current = step;
    playOnboardingClip(TOUR_STEPS[step].clip, lang).catch(() => {});
    return () => { stopAudio().catch(() => {}); };
  }, [step, lang]);

  const next = () => (step < TOUR_STEPS.length - 1 ? setStep(step + 1) : onDone());

  return (
    <View style={{ flex: 1, backgroundColor: C.bg, padding: S.xl, paddingTop: 100, justifyContent: 'space-between' }}>
      <View>
        <View style={{ flexDirection: 'row', gap: S.xs, marginBottom: S.xl }}>
          {TOUR_STEPS.map((_, i) => (
            <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: i <= step ? C.accent : C.border }} />
          ))}
        </View>
        <Text style={st.h1}>{t(TOUR_STEPS[step].titleKey)}</Text>
        <Text style={[st.body, { marginTop: S.md, fontSize: 17, lineHeight: 26 }]}>
          {t(`tourBody_${TOUR_STEPS[step].clip}` as any)}
        </Text>
      </View>
      <View>
        <Btn label={step < TOUR_STEPS.length - 1 ? t('tourNext') : t('tourStart')} onPress={next} />
        <Btn label={t('tourSkip')} kind="secondary" onPress={() => { stopAudio(); onDone(); }} style={{ marginTop: S.sm }} />
      </View>
    </View>
  );
}

const normalizePhone = (raw: string) => {
  const digits = raw.replace(/[^0-9]/g, '');
  return digits ? `+91${digits.slice(-10)}` : '';
};

export function AuthScreen({ lang, onLoggedIn, notice }: { lang: Lang; onLoggedIn: (f: Farmer, isNew: boolean) => void; notice?: string }) {
  const t = makeT(lang);
  // Phone first, always -- name is only asked for when the backend actually
  // needs it (a phone number it has never seen before). A returning farmer
  // never sees a name field at all.
  const [step, setStep] = useState<'phone' | 'name' | 'otp'>('phone');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [isNew, setIsNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const requestWithName = async (theName: string) => {
    setBusy(true);
    try {
      const r = await requestOtp(normalizePhone(phone), theName, lang);
      setIsNew(r.is_new_farmer);
      setStep('otp');
      setOtp('');
      setCooldown(30);
    } catch (e) {
      const ae = e as ApiError;
      if (ae.status === 400 && ae.message === 'name is required') {
        // First time this phone has been seen -- now ask for a name.
        setStep('name');
      } else {
        setErr(ae.isNetwork ? t('cantReachServer') : ae.status === 429 ? t('pleaseWait') : ae.message);
      }
    } finally {
      setBusy(false);
    }
  };

  const submitPhone = async () => {
    setErr('');
    const digits = phone.replace(/[^0-9]/g, '');
    if (digits.length < 10) return setErr(t('enterPhone'));
    await requestWithName('');
  };

  const submitName = async () => {
    setErr('');
    if (!name.trim()) return setErr(t('nameRequired'));
    await requestWithName(name.trim());
  };

  const verify = async () => {
    setErr('');
    setBusy(true);
    try {
      const farmer = await verifyOtp(normalizePhone(phone), otp.trim());
      onLoggedIn(farmer, isNew);
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.isNetwork ? t('cantReachServer') : t('invalidOtp'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ padding: S.xl, paddingTop: 80 }} keyboardShouldPersistTaps="handled">
        <Text style={st.h1}>{t('signIn')}</Text>
        {notice ? <Banner text={notice} /> : null}
        {err ? <Banner text={err} kind="error" /> : null}
        {step === 'phone' ? (
          <>
            <Label>{t('phoneLabel')}</Label>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: S.sm }}>
              <Text style={st.body}>+91</Text>
              <Input
                style={{ flex: 1 }}
                value={phone}
                onChangeText={(v) => setPhone(v.replace(/[^0-9]/g, '').slice(0, 10))}
                keyboardType="number-pad"
                placeholder={t('phoneHint')}
                maxLength={10}
                autoFocus
              />
            </View>
            <Btn label={t('sendOtp')} onPress={submitPhone} busy={busy} disabled={cooldown > 0} style={{ marginTop: S.xl }} />
          </>
        ) : step === 'name' ? (
          <>
            <Muted>+91 {phone}</Muted>
            <Muted style={{ marginTop: 4 }}>{t('newHereNamePrompt')}</Muted>
            <Label>{t('nameLabel')}</Label>
            <Input value={name} onChangeText={setName} autoCapitalize="words" autoFocus />
            <Btn label={t('continue')} onPress={submitName} busy={busy} style={{ marginTop: S.xl }} />
            <Btn label={t('changeNumber')} kind="secondary" onPress={() => { setStep('phone'); setErr(''); }} style={{ marginTop: S.md }} />
          </>
        ) : (
          <>
            <Muted>+91 {phone}</Muted>
            <Label>{t('otpLabel')}</Label>
            <Input value={otp} onChangeText={(v) => setOtp(v.replace(/[^0-9]/g, '').slice(0, 6))} keyboardType="number-pad" maxLength={6} autoFocus />
            <Btn label={t('verify')} onPress={verify} busy={busy} disabled={otp.length < 6} style={{ marginTop: S.xl }} />
            <Btn label={t('changeNumber')} kind="secondary" onPress={() => { setStep('phone'); setErr(''); }} style={{ marginTop: S.md }} />
            <Btn label={cooldown > 0 ? `${t('sendOtp')} (${cooldown})` : t('sendOtp')} kind="secondary" onPress={() => requestWithName(isNew ? name.trim() : '')} disabled={cooldown > 0} style={{ marginTop: S.md }} />
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export { C };
