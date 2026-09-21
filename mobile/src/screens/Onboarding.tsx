import React, { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { ApiError, Farmer, requestOtp, verifyOtp } from '../api';
import { makeT } from '../ctx';
import { LANGS, Lang } from '../i18n';
import { C, S } from '../theme';
import { Banner, Btn, Chip, Input, Label, Muted, st } from '../ui';

export function LanguageScreen({ onPick }: { onPick: (l: Lang) => void }) {
  const [sel, setSel] = useState<Lang>('en');
  const t = makeT(sel);
  return (
    <ScrollView contentContainerStyle={{ padding: S.xl, paddingTop: 80 }}>
      <Text style={st.h1}>Agro Mirai</Text>
      <Text style={[st.body, { marginBottom: S.lg }]}>{t('chooseLanguage')}</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
        {LANGS.map((l) => (
          <Chip key={l.code} label={l.native} selected={sel === l.code} onPress={() => setSel(l.code)} />
        ))}
      </View>
      <Btn label={t('continue')} onPress={() => onPick(sel)} style={{ marginTop: S.xl }} />
    </ScrollView>
  );
}

const normalizePhone = (raw: string) => {
  const digits = raw.replace(/[^0-9]/g, '');
  return digits ? `+91${digits.slice(-10)}` : '';
};

export function AuthScreen({ lang, onLoggedIn, notice }: { lang: Lang; onLoggedIn: (f: Farmer, isNew: boolean) => void; notice?: string }) {
  const t = makeT(lang);
  const [step, setStep] = useState<'phone' | 'otp'>('phone');
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

  const send = async () => {
    setErr('');
    const digits = phone.replace(/[^0-9]/g, '');
    if (digits.length < 10 || !name.trim()) {
      setErr(t('enterNamePhone'));
      return;
    }
    setBusy(true);
    try {
      const r = await requestOtp(normalizePhone(phone), name.trim(), lang);
      setIsNew(r.is_new_farmer);
      setStep('otp');
      setOtp('');
      setCooldown(30);
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.isNetwork ? t('cantReachServer') : ae.status === 429 ? t('pleaseWait') : ae.message);
    } finally {
      setBusy(false);
    }
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
            <Label>{t('nameLabel')}</Label>
            <Input value={name} onChangeText={setName} autoCapitalize="words" />
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
              />
            </View>
            <Btn label={t('sendOtp')} onPress={send} busy={busy} disabled={cooldown > 0} style={{ marginTop: S.xl }} />
          </>
        ) : (
          <>
            <Muted>+91 {phone}</Muted>
            <Label>{t('otpLabel')}</Label>
            <Input value={otp} onChangeText={(v) => setOtp(v.replace(/[^0-9]/g, '').slice(0, 6))} keyboardType="number-pad" maxLength={6} />
            <Btn label={t('verify')} onPress={verify} busy={busy} disabled={otp.length < 6} style={{ marginTop: S.xl }} />
            <Btn label={t('changeNumber')} kind="secondary" onPress={() => { setStep('phone'); setErr(''); }} style={{ marginTop: S.md }} />
            <Btn label={cooldown > 0 ? `${t('sendOtp')} (${cooldown})` : t('sendOtp')} kind="secondary" onPress={send} disabled={cooldown > 0} style={{ marginTop: S.md }} />
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export { C };
