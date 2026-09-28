import React, { useState } from 'react';
import { Alert, Image, Platform, ScrollView, Switch, Text, TouchableOpacity, View } from 'react-native';
import { AuthBackdrop } from '../components/AuthBackdrop';
import { IconName } from '../../icons';
import Constants from 'expo-constants';
import * as ImagePicker from 'expo-image-picker';
import { API_BASE_URL, ApiError, deleteField, patchMe, sendBugReport } from '../api';
import { cropLabel, useApp } from '../ctx';
import { classifyError } from '../errors';
import { logError } from '../errorLog';
import { errorText } from '../hooks';
import { feedback, setFeedbackEnabled, useFeedbackEnabled } from '../feedback';
import { Icon } from '../../icons';
import { LANGS } from '../i18n';
import { C, S } from '../theme';
import { Banner, Btn, Chip, Input, KV, Muted } from '../ui';

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

function Section({ icon, tint, title, children }: { icon: IconName; tint: string; title: string; children: React.ReactNode }) {
  return (
    <View style={{ backgroundColor: 'rgba(255,255,255,0.95)', borderRadius: 22, padding: S.lg, marginBottom: S.md, borderWidth: 1, borderColor: '#E3E8DC' }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
        <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: tint, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
          <Icon name={icon} size={20} color={C.accent} />
        </View>
        <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: C.text }}>{title}</Text>
      </View>
      {children}
    </View>
  );
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
      const { kind } = classifyError(e);
      if (kind === 'unknown') logError('MeTab.saveName', e);
      setErr(errorText(t, e as ApiError, { write: true }));
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
      const { kind } = classifyError(e);
      if (kind === 'unknown') logError('MeTab.changePhoto', e);
      setErr(errorText(t, e as ApiError, { write: true }));
    }
  };

  const chooseLang = async (l: typeof lang) => {
    changeLang(l);
    try { setFarmer(await patchMe({ preferred_language: l })); } catch {}
  };

  const feedbackOn = useFeedbackEnabled();
  const confirmDelete = (id: string) => {
    feedback.warning();
    Alert.alert(t('deleteField'), t('deleteConfirm'), [
      { text: t('cancel'), style: 'cancel' },
      {
        text: t('delete'), style: 'destructive',
        onPress: async () => {
          try {
            await deleteField(id);
            await reloadFields();
          } catch (e) {
            const { kind } = classifyError(e);
            if (kind === 'unknown') logError('MeTab.deleteField', e);
            setErr(errorText(t, e as ApiError, { write: true }));
          }
        },
      },
    ]);
  };

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
    <View style={{ flex: 1 }}>
      <AuthBackdrop />
      <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: S.xl * 2 }} keyboardShouldPersistTaps="handled">
        {err ? <Banner text={err} kind="error" /> : null}
        {msg ? <Banner text={msg} kind="ok" /> : null}

        {/* ---- identity hero */}
        <View style={{ backgroundColor: 'rgba(255,255,255,0.95)', borderRadius: 26, padding: S.lg, alignItems: 'center', marginBottom: S.md, borderWidth: 1, borderColor: '#E3E8DC' }}>
          <TouchableOpacity onPress={changePhoto} activeOpacity={0.8}>
            {farmer.photo_url ? (
              <Image source={{ uri: farmer.photo_url }} style={{ width: 92, height: 92, borderRadius: 46 }} />
            ) : (
              <View style={{ width: 92, height: 92, borderRadius: 46, backgroundColor: avColor, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ fontSize: 34, fontWeight: '800', color: '#fff' }}>{initials(farmer.name)}</Text>
              </View>
            )}
            <View style={{ position: 'absolute', bottom: -2, right: -2, width: 30, height: 30, borderRadius: 15, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#fff' }}>
              <Icon name="camera" size={15} color="#fff" />
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
              <Text style={{ fontSize: 21, fontWeight: '800', color: C.text }}>{farmer.name}</Text>
              <View style={{ marginLeft: S.xs }}><Icon name="chevron-down" size={14} color={C.muted} /></View>
            </TouchableOpacity>
          )}
          <Muted style={{ marginTop: 2 }}>{farmer.phone}</Muted>
        </View>

        {/* ---- language: big pill row, matches the sign-in language switcher */}
        <Section icon="globe" tint="#E3F1FA" title={t('language')}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: S.sm }}>
            {LANGS.map((l) => {
              const on = lang === l.code;
              return (
                <TouchableOpacity
                  key={l.code}
                  onPress={() => chooseLang(l.code)}
                  style={{ minHeight: 46, paddingHorizontal: 18, borderRadius: 23, borderWidth: on ? 2 : 1.5, borderColor: on ? C.accent : '#B9C9B4', backgroundColor: on ? '#E8F3E8' : '#fff', alignItems: 'center', justifyContent: 'center' }}
                >
                  <Text style={{ fontSize: 16, fontWeight: on ? '800' : '600', color: on ? C.accent : C.text }}>{l.native}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Section>

        {/* ---- sounds + notifications */}
        <Section icon="bell" tint="#F6ECD6" title={t('soundsTitle')}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ flex: 1, fontSize: 15, lineHeight: 21, color: C.muted, paddingRight: S.md }}>{t('soundsSub')}</Text>
            <Switch value={feedbackOn} onValueChange={(v) => { setFeedbackEnabled(v); if (v) feedback.success(); }} trackColor={{ true: C.accent }} />
          </View>
        </Section>

        {/* ---- my fields */}
        <Section icon="field" tint="#E8F3E8" title={t('myFields')}>
          {fields.map((f) => {
            const active = field?.id === f.id;
            return (
              <View key={f.id} style={{ borderRadius: 16, borderWidth: 1.5, borderColor: active ? C.accent : '#E3E8DC', backgroundColor: active ? '#F3F9F1' : '#fff', padding: S.md, marginBottom: S.sm }}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Text style={{ fontSize: 16, fontWeight: '800', flex: 1, color: C.text }}>{f.name}</Text>
                  {active ? (
                    <View style={{ backgroundColor: C.accent, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 }}>
                      <Text style={{ color: '#fff', fontSize: 11, fontWeight: '700' }}>{t('activeField')}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={{ fontSize: 13.5, color: C.muted, marginTop: 2 }}>{`${f.area_ha} ${t('ha')} · ${cropLabel(lang, f.current_crop)}`}</Text>
                <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.sm }}>
                  {!active ? <Btn label={t('useThisField')} kind="secondary" onPress={() => selectField(f.id)} style={{ flex: 1 }} /> : null}
                  <Btn label={t('edit')} kind="secondary" onPress={() => openFieldForm(f)} style={{ flex: 1 }} />
                  <Btn label={t('delete')} kind="danger" onPress={() => confirmDelete(f.id)} style={{ flex: 1 }} />
                </View>
              </View>
            );
          })}
          <Btn label={t('addField')} onPress={() => openFieldForm()} style={{ marginTop: S.xs }} />
        </Section>

        {/* ---- report a problem */}
        <View style={{ backgroundColor: 'rgba(255,255,255,0.95)', borderRadius: 22, marginBottom: S.md, borderWidth: 1, borderColor: '#E3E8DC', overflow: 'hidden' }}>
          <TouchableOpacity onPress={() => setBugOpen(!bugOpen)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: S.lg, minHeight: 56 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: '#FDECEA', alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
                <Icon name="bug" size={19} color={C.danger} />
              </View>
              <Text style={{ fontSize: 17, fontWeight: '800', color: C.text }}>{t('reportProblem')}</Text>
            </View>
            <Icon name={bugOpen ? 'chevron-up' : 'chevron-down'} size={18} color={C.muted} />
          </TouchableOpacity>
          {bugOpen ? (
            <View style={{ paddingHorizontal: S.lg, paddingBottom: S.lg }}>
              <Muted>{t('bugReportSub')}</Muted>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: S.sm }}>
                {BUG_CATS.map(([code, key]) => (
                  <Chip key={code} label={t(key)} selected={bugCat === code} onPress={() => setBugCat(bugCat === code ? null : code)} />
                ))}
              </View>
              <Input value={bugMsg} onChangeText={setBugMsg} placeholder={t('bugReportMessagePlaceholder')} multiline />
              {bugNote ? <Muted style={{ marginTop: S.sm }}>{bugNote}</Muted> : null}
              <Btn label={t('bugReportSubmit')} onPress={sendBug} busy={bugBusy} style={{ marginTop: S.sm }} />
            </View>
          ) : null}
        </View>

        {/* ---- footer + sign out */}
        <View style={{ alignItems: 'center', marginTop: S.sm, marginBottom: S.md }}>
          <Text style={{ fontSize: 12.5, color: C.muted }}>{`${t('version')} ${Constants.expoConfig?.version}`}</Text>
          <Text style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{API_BASE_URL}</Text>
        </View>
        <TouchableOpacity
          onPress={() => Alert.alert(t('signOut'), t('signOutAsk'), [{ text: t('cancel'), style: 'cancel' }, { text: t('signOut'), style: 'destructive', onPress: signOut }])}
          style={{ minHeight: 56, borderRadius: 16, borderWidth: 2, borderColor: C.danger, alignItems: 'center', justifyContent: 'center' }}
        >
          <Text style={{ fontSize: 17, fontWeight: '800', color: C.danger }}>{t('signOut')}</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}
