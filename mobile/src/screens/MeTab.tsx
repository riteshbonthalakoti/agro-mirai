import React, { useState } from 'react';
import { Alert, Image, Platform, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import Constants from 'expo-constants';
import * as ImagePicker from 'expo-image-picker';
import { API_BASE_URL, ApiError, deleteField, patchMe, sendBugReport } from '../api';
import { cropLabel, useApp } from '../ctx';
import { errorText } from '../hooks';
import { Icon } from '../../icons';
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

const AVATAR_COLORS = ['#2E7D32', '#B36B00', '#1E5AA8', '#8E3B8E', '#B3261E', '#2E7D6E'];
function avatarColor(seed: string) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}
function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase();
}

export function MeTab() {
  const { farmer, setFarmer, fields, field, selectField, reloadFields, lang, changeLang, openFieldForm, signOut, t } = useApp();
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(farmer.name);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [bugCat, setBugCat] = useState<string | null>(null);
  const [bugMsg, setBugMsg] = useState('');
  const [bugNote, setBugNote] = useState('');
  const [bugBusy, setBugBusy] = useState(false);
  const [bugOpen, setBugOpen] = useState(false);

  const saveName = async () => {
    setErr(''); setMsg('');
    if (!name.trim()) return setErr(t('nameRequired'));
    setBusy(true);
    try {
      setFarmer(await patchMe({ name: name.trim() }));
      setMsg(t('save') + ' ✓');
      setEditingName(false);
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

  const avColor = avatarColor(farmer.id);

  return (
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }} keyboardShouldPersistTaps="handled">
      {err ? <Banner text={err} kind="error" /> : null}
      {msg ? <Banner text={msg} kind="ok" /> : null}

      {/* Hero identity block */}
      <View style={{ alignItems: 'center', paddingVertical: S.lg }}>
        <TouchableOpacity onPress={changePhoto} activeOpacity={0.8}>
          {farmer.photo_url ? (
            <Image source={{ uri: farmer.photo_url }} style={{ width: 88, height: 88, borderRadius: 44 }} />
          ) : (
            <View style={{ width: 88, height: 88, borderRadius: 44, backgroundColor: avColor, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ fontSize: 32, fontWeight: '700', color: '#fff' }}>{initials(farmer.name)}</Text>
            </View>
          )}
          <View style={{ position: 'absolute', bottom: -2, right: -2, width: 28, height: 28, borderRadius: 14, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: C.bg }}>
            <Icon name="camera" size={14} color="#fff" />
          </View>
        </TouchableOpacity>

        {editingName ? (
          <View style={{ marginTop: S.md, width: '100%', maxWidth: 320 }}>
            <Input value={name} onChangeText={setName} autoFocus textAlign="center" style={{ fontSize: 18, fontWeight: '700' }} />
            <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.sm }}>
              <Btn label={t('cancel')} kind="secondary" onPress={() => { setName(farmer.name); setEditingName(false); }} style={{ flex: 1 }} />
              <Btn label={t('save')} onPress={saveName} busy={busy} style={{ flex: 1 }} />
            </View>
          </View>
        ) : (
          <TouchableOpacity onPress={() => setEditingName(true)} style={{ flexDirection: 'row', alignItems: 'center', marginTop: S.md }}>
            <Text style={{ fontSize: 20, fontWeight: '700', color: C.text }}>{farmer.name}</Text>
            <View style={{ marginLeft: S.xs }}><Icon name="chevron-down" size={14} color={C.muted} /></View>
          </TouchableOpacity>
        )}
        <Muted style={{ marginTop: 2 }}>{farmer.phone}</Muted>
      </View>

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
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Icon name="field" size={16} color={field?.id === f.id ? C.accent : C.muted} />
              <Text style={{ fontSize: 15, fontWeight: '600', marginLeft: S.sm, flex: 1 }}>{f.name}</Text>
              {field?.id === f.id ? <View style={{ backgroundColor: C.accent, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 }}><Text style={{ color: '#fff', fontSize: 11, fontWeight: '700' }}>{t('activeField')}</Text></View> : null}
            </View>
            <Muted style={{ marginLeft: 24 }}>{`${f.area_ha} ${t('ha')} · ${cropLabel(lang, f.current_crop)} · ${f.latitude.toFixed(3)}, ${f.longitude.toFixed(3)}`}</Muted>
            <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.sm, marginLeft: 24 }}>
              {field?.id !== f.id ? <Btn label={t('useThisField')} kind="secondary" onPress={() => selectField(f.id)} style={{ flex: 1 }} /> : null}
              <Btn label={t('edit')} kind="secondary" onPress={() => openFieldForm(f)} style={{ flex: 1 }} />
              <Btn label={t('delete')} kind="danger" onPress={() => confirmDelete(f.id)} style={{ flex: 1 }} />
            </View>
          </View>
        ))}
        <Btn label={t('addField')} onPress={() => openFieldForm()} style={{ marginTop: S.md }} />
      </Card>

      <TouchableOpacity onPress={() => setBugOpen(!bugOpen)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: S.md }}>
        <Text style={{ fontSize: 16, fontWeight: '700', color: C.text }}>{t('reportProblem')}</Text>
        <Icon name={bugOpen ? 'chevron-up' : 'chevron-down'} size={18} color={C.muted} />
      </TouchableOpacity>
      {bugOpen ? (
        <Card>
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
      ) : null}

      <View style={{ marginTop: S.md, paddingTop: S.md, borderTopWidth: 1, borderTopColor: C.border }}>
        <KV k={t('version')} v={Constants.expoConfig?.version} />
        <Muted style={{ fontSize: 11 }}>{API_BASE_URL}</Muted>
      </View>
      <Btn label={t('signOut')} kind="danger" onPress={() => Alert.alert(t('signOut'), t('signOutAsk'), [{ text: t('cancel'), style: 'cancel' }, { text: t('signOut'), style: 'destructive', onPress: signOut }])} style={{ marginTop: S.lg, marginBottom: S.xl }} />
    </ScrollView>
  );
}
