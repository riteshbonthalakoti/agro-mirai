import React, { useState } from 'react';
import { Alert, Image, Platform, ScrollView, Text, View } from 'react-native';
import Constants from 'expo-constants';
import * as ImagePicker from 'expo-image-picker';
import { API_BASE_URL, ApiError, deleteField, patchMe, sendBugReport } from '../api';
import { cropLabel, useApp } from '../ctx';
import { errorText } from '../hooks';
import { LANGS } from '../i18n';
import { C, S } from '../theme';
import { Banner, Btn, Card, Chip, Input, KV, Label, Muted, st } from '../ui';

const BUG_CATS: [string, 'bugCategoryCrash' | 'bugCategoryWrongAdvice' | 'bugCategoryScanFailed' | 'bugCategoryLoginFailed' | 'bugCategoryOther'][] = [
  ['crash', 'bugCategoryCrash'],
  ['wrong_info', 'bugCategoryWrongAdvice'],
  ['photo_scan_failed', 'bugCategoryScanFailed'],
  ['login_failed', 'bugCategoryLoginFailed'],
  ['other', 'bugCategoryOther'],
];

export function MeTab() {
  const { farmer, setFarmer, fields, field, selectField, reloadFields, lang, changeLang, openFieldForm, signOut, t } = useApp();
  const [name, setName] = useState(farmer.name);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [bugCat, setBugCat] = useState<string | null>(null);
  const [bugMsg, setBugMsg] = useState('');
  const [bugNote, setBugNote] = useState('');
  const [bugBusy, setBugBusy] = useState(false);

  const saveName = async () => {
    setErr(''); setMsg('');
    if (!name.trim()) return setErr(t('nameRequired'));
    setBusy(true);
    try {
      setFarmer(await patchMe({ name: name.trim() }));
      setMsg(t('save') + ' ✓');
    } catch (e) {
      setErr(errorText(t, e as ApiError));
    } finally {
      setBusy(false);
    }
  };

  const changePhoto = async () => {
    setErr('');
    const p = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!p.granted) return setErr(t('galleryPerm'));
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.4, base64: true });
    const a = r.assets?.[0];
    if (r.canceled || !a?.base64) return;
    try {
      setFarmer(await patchMe({ photo_url: `data:${a.mimeType || 'image/jpeg'};base64,${a.base64}` }));
    } catch (e) {
      setErr(errorText(t, e as ApiError));
    }
  };

  const chooseLang = async (l: typeof lang) => {
    changeLang(l);
    try { setFarmer(await patchMe({ preferred_language: l })); } catch {}
  };

  const confirmDelete = (id: string) =>
    Alert.alert(t('deleteField'), t('deleteConfirm'), [
      { text: t('cancel'), style: 'cancel' },
      {
        text: t('delete'), style: 'destructive',
        onPress: async () => {
          try { await deleteField(id); await reloadFields(); } catch (e) { setErr(errorText(t, e as ApiError)); }
        },
      },
    ]);

  const sendBug = async () => {
    setBugNote('');
    if (!bugCat && !bugMsg.trim()) return setBugNote(t('bugReportError'));
    setBugBusy(true);
    try {
      await sendBugReport({
        category: bugCat || undefined, message: bugMsg.trim() || undefined,
        app_version: Constants.expoConfig?.version, platform: Platform.OS,
      });
      setBugNote(t('bugReportSuccess'));
      setBugCat(null); setBugMsg('');
    } catch {
      setBugNote(t('bugReportError'));
    } finally {
      setBugBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: 48 }} keyboardShouldPersistTaps="handled">
      <Text style={st.h1}>{t('profile')}</Text>
      {err ? <Banner text={err} kind="error" /> : null}
      {msg ? <Banner text={msg} kind="ok" /> : null}
      <Card>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: S.md }}>
          {farmer.photo_url ? (
            <Image source={{ uri: farmer.photo_url }} style={{ width: 56, height: 56, borderRadius: 28 }} />
          ) : (
            <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: C.surface }} />
          )}
          <Btn label={t('changePhoto')} kind="secondary" onPress={changePhoto} />
        </View>
        <Label>{t('nameLabel')}</Label>
        <Input value={name} onChangeText={setName} />
        <KV k={t('phoneLabel')} v={farmer.phone} />
        <Btn label={t('save')} onPress={saveName} busy={busy} style={{ marginTop: S.sm }} />
      </Card>

      <Card title={t('language')}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
          {LANGS.map((l) => (
            <Chip key={l.code} label={l.native} selected={lang === l.code} onPress={() => chooseLang(l.code)} />
          ))}
        </View>
      </Card>

      <Card title={t('myFields')}>
        {fields.map((f) => (
          <View key={f.id} style={{ paddingVertical: S.sm, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={{ fontSize: 15, fontWeight: '600' }}>{f.name}{field?.id === f.id ? ' ✓' : ''}</Text>
            <Muted>{`${f.area_ha} ${t('ha')} · ${cropLabel(lang, f.current_crop)} · ${f.latitude.toFixed(3)}, ${f.longitude.toFixed(3)}`}</Muted>
            <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.sm }}>
              {field?.id !== f.id ? <Btn label={t('activeField')} kind="secondary" onPress={() => selectField(f.id)} style={{ flex: 1 }} /> : null}
              <Btn label={t('edit')} kind="secondary" onPress={() => openFieldForm(f)} style={{ flex: 1 }} />
              <Btn label={t('delete')} kind="danger" onPress={() => confirmDelete(f.id)} style={{ flex: 1 }} />
            </View>
          </View>
        ))}
        <Btn label={t('addField')} onPress={() => openFieldForm()} style={{ marginTop: S.md }} />
      </Card>

      <Card title={t('reportProblem')}>
        <Muted>{t('bugReportSub')}</Muted>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: S.sm }}>
          {BUG_CATS.map(([code, key]) => (
            <Chip key={code} label={t(key)} selected={bugCat === code} onPress={() => setBugCat(bugCat === code ? null : code)} />
          ))}
        </View>
        <Input value={bugMsg} onChangeText={setBugMsg} placeholder={t('bugReportMessagePlaceholder')} multiline />
        {bugNote ? <Muted style={{ marginTop: S.sm }}>{bugNote}</Muted> : null}
        <Btn label={t('bugReportSubmit')} onPress={sendBug} busy={bugBusy} style={{ marginTop: S.sm }} />
      </Card>

      <Card>
        <KV k={t('server')} v={API_BASE_URL} />
        <KV k={t('version')} v={Constants.expoConfig?.version} />
      </Card>
      <Btn label={t('signOut')} kind="danger" onPress={signOut} style={{ marginBottom: S.xl }} />
    </ScrollView>
  );
}
