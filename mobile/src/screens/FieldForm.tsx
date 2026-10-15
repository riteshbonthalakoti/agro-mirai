import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ImageBackground, ScrollView, StyleSheet, Text, TouchableOpacity, View, useWindowDimensions } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import * as Location from 'expo-location';
import { ApiError, Field, createField, patchField, getRecommendation, getIrrigation, getDiseaseRiskFull, dataSummary } from '../api';
import { cropLabel, soilLabel, useApp } from '../ctx';
import { DateField } from '../datepicker';
import { classifyError } from '../errors';
import { logError } from '../errorLog';
import { feedback } from '../feedback';
import { Icon, IconName } from '../../icons';
import { errorText } from '../hooks';
import { CROP_TYPES, SOIL_TYPES } from '../i18n';
import { cacheGet, cacheSet } from '../storage';
import { C, S } from '../theme';
import { useToast } from '../toast';
import { PickGrid, PickItem } from '../components/PickGrid';
import { Banner, Input } from '../ui';

// farmers here think in acres and guntas; the backend stores hectares
type Unit = 'acre' | 'gunta' | 'ha';
const HA_PER: Record<Unit, number> = { acre: 0.404686, gunta: 0.0101171, ha: 1 };
const trimNum = (n: number) => String(Math.round(n * 100) / 100);

const isoOf = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const today = () => isoOf(new Date());
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return isoOf(d); };

// "When did you plant it?" quick answers -> the middle of each range
const PLANTED: { k: string; days: number; key: string }[] = [
  { k: 'w', days: 3, key: 'plantedThisWeek' },
  { k: 'm1', days: 21, key: 'planted2to4' },
  { k: 'm2', days: 45, key: 'planted1to2m' },
  { k: 'old', days: 90, key: 'plantedOlder' },
];
const POPULAR_CROPS = ['rice', 'maize', 'cotton', 'chickpea', 'pigeonpeas', 'banana', 'mango', 'coconut', 'grapes'];
const SOIL_TINT: Record<string, string> = {
  alluvial: '#EFE3CC', black: '#D9D9D6', red: '#F3D9CF', laterite: '#F5DFC8', mountain: '#E5E0D2',
  desert: '#F7ECC9', saline: '#EDEDE8', peaty: '#DCD3C8', unknown: '#EEF4E8',
};
const STEPS = ['place', 'size', 'crop', 'planted', 'soil'] as const;

function Q({ mode, n, title, hint, children }: { mode: 'page' | 'steps'; n: number; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <View style={{ marginTop: mode === 'page' ? S.xl : S.lg }}>
      <View style={fs.qRow}>
        {mode === 'page' ? (
          <View style={fs.qStepBadge}>
            <Text style={fs.qStepBadgeText}>{n}</Text>
          </View>
        ) : null}
        <Text style={{ flex: 1, fontSize: mode === 'page' ? 20 : 26, lineHeight: mode === 'page' ? 26 : 33, fontWeight: '800', color: C.text }}>{title}</Text>
      </View>
      {hint ? <Text style={fs.qHint}>{hint}</Text> : null}
      <View style={fs.qChildren}>{children}</View>
    </View>
  );
}

/** Add (no `initial`) or edit a field. Add posts to POST /v2/fields, which
 *  fetches weather + soil synchronously and starts NDVI in the background.
 *  Two layouts over the same sections: one long page, or one question per screen. */
export function FieldForm({ initial, onDone, onCancel }: { initial?: Field; onDone: (f: Field) => void; onCancel?: () => void }) {
  const { t: tRaw, lang } = useApp();
  const t = (k: string) => (tRaw as any)(k) as string;
  const toast = useToast();
  const { width: w } = useWindowDimensions();
  const [name, setName] = useState(initial?.name ?? '');
  const [unit, setUnit] = useState<Unit>('acre');
  const [area, setArea] = useState(initial ? trimNum(initial.area_ha / HA_PER.acre) : '');
  const [lat, setLat] = useState(initial ? String(initial.latitude) : '');
  const [lon, setLon] = useState(initial ? String(initial.longitude) : '');
  const [soil, setSoil] = useState<string | null>(initial?.soil_type ?? null);
  const [crop, setCrop] = useState<string | null>(initial?.current_crop ?? null);
  const [sown, setSown] = useState(initial?.sown_on ?? daysAgo(21));
  const [quick, setQuick] = useState<string | null>(initial?.sown_on ? null : 'm1');
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [err, setErr] = useState('');
  const [placeName, setPlaceName] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);
  const [allCrops, setAllCrops] = useState(false);
  const [cropQ, setCropQ] = useState('');
  const [mode, setMode] = useState<'page' | 'steps'>('steps');
  const [step, setStep] = useState(0);
  const [savedField, setSavedField] = useState<Field | null>(null);

  useEffect(() => { cacheGet<'page' | 'steps'>('fieldFormMode').then((m) => m ? setMode(m) : setMode('steps')); }, []);
  const chooseMode = (m: 'page' | 'steps') => { feedback.select(); setMode(m); setStep(0); setErr(''); cacheSet('fieldFormMode', m); };

  const lookupPlace = async (latN: number, lonN: number) => {
    setGeocoding(true);
    try {
      const [hit] = await Location.reverseGeocodeAsync({ latitude: latN, longitude: lonN });
      const district = hit?.subregion || hit?.district || hit?.city;
      const region = hit?.region;
      setPlaceName([district, region].filter(Boolean).join(', ') || null);
    } catch {
      setPlaceName(null);
    } finally {
      setGeocoding(false);
    }
  };

  // Fields opened for editing already have coordinates -- show their district right away.
  useEffect(() => {
    if (initial) lookupPlace(initial.latitude, initial.longitude);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const useMyLocation = async () => {
    setLocating(true);
    setErr('');
    setPlaceName(null);
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== 'granted') { setErr(t('permLocation')); return; }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setLat(loc.coords.latitude.toFixed(5));
      setLon(loc.coords.longitude.toFixed(5));
      feedback.success();
      lookupPlace(loc.coords.latitude, loc.coords.longitude);
    } catch {
      setErr(t('locFailed'));
    } finally {
      setLocating(false);
    }
  };

  const onCoordsBlur = () => {
    const latN = parseFloat(lat);
    const lonN = parseFloat(lon);
    if (!isNaN(latN) && !isNaN(lonN) && Math.abs(latN) <= 90 && Math.abs(lonN) <= 180) lookupPlace(latN, lonN);
  };

  const hasLocation = !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon));

  /** '' when this part is fine, else the message to show. */
  const validate = (which: (typeof STEPS)[number] | 'all'): string => {
    const areaN = Math.round(parseFloat(area) * HA_PER[unit] * 10000) / 10000;
    const latN = parseFloat(lat);
    const lonN = parseFloat(lon);
    if (which === 'place' || which === 'all') {
      if (isNaN(latN) || isNaN(lonN) || Math.abs(latN) > 90 || Math.abs(lonN) > 180) return t('locationRequired');
    }
    if (which === 'size' || which === 'all') {
      if (!name.trim()) return t('fieldNameRequired');
      if (!(areaN > 0)) return t('areaRequired');
    }
    if (which === 'planted' || which === 'all') {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(sown) || isNaN(Date.parse(sown))) return t('dateInvalid');
    }
    return '';
  };

  const submit = async () => {
    const bad = validate('all');
    if (bad) {
      setErr(bad);
      if (mode === 'steps') setStep(STEPS.findIndex((s) => validate(s) !== '') || 0);
      return;
    }
    setErr('');
    const areaN = Math.round(parseFloat(area) * HA_PER[unit] * 10000) / 10000;
    const payload: Record<string, unknown> = {
      name: name.trim(), latitude: parseFloat(lat), longitude: parseFloat(lon), area_ha: areaN, sown_on: sown,
    };
    if (soil) payload.soil_type = soil;
    if (crop) payload.current_crop = crop;

    setBusy(true);
    try {
      const saved = initial ? await patchField(initial.id, payload) : await createField(payload);
      toast.show(initial ? t('fieldUpdated') : t('fieldAdded'), 'ok');
      if (initial) {
        onDone(saved); // editing an existing field: no need for the new-field ready screen
      } else {
        feedback.success();
        // Warm up and pre-seed the caches so Home and Data tabs load immediately without empty states
        Promise.all([
          getRecommendation(saved.id, false).then((r) => cacheSet(`rec:${saved.id}:false`, r)).catch(() => {}),
          getIrrigation(saved.id).then((i) => cacheSet(`irr:${saved.id}`, i)).catch(() => {}),
          getDiseaseRiskFull(saved.id, lang).then((d) => cacheSet(`dis:${saved.id}:${lang}`, d)).catch(() => {}),
          dataSummary(saved.id).then((s) => cacheSet(`summary:${saved.id}`, s)).catch(() => {}),
        ]).catch(() => {});
        setSavedField(saved);
      }
    } catch (e) {
      const { kind } = classifyError(e);
      if (kind === 'unknown') logError('FieldForm.submit', e);
      setErr(errorText(t, e as ApiError, { write: true }));
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    const bad = validate(STEPS[step]);
    if (bad) { feedback.error(); return setErr(bad); }
    setErr('');
    if (step < STEPS.length - 1) { feedback.tap(); setStep(step + 1); } else submit();
  };
  const back = () => { setErr(''); if (step > 0) setStep(step - 1); else onCancel?.(); };

  // ------------------------------------------------------------------ pieces
  const bigInput = { fontSize: 16, fontWeight: '600' as const, minHeight: 52, borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 12, backgroundColor: '#FFFFFF', paddingHorizontal: S.md, color: C.text };
  const pill = (label: string, on: boolean, onPress: () => void, key?: string) => (
    <TouchableOpacity
      key={key ?? label}
      onPress={() => { feedback.select(); onPress(); }}
      style={{
        minHeight: 38,
        paddingHorizontal: 14,
        borderRadius: 19,
        borderWidth: 1,
        borderColor: on ? '#2D6A4F' : '#E5E7EB',
        backgroundColor: on ? '#F0FDF4' : '#FFFFFF',
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: S.sm,
        marginBottom: S.sm,
      }}
    >
      <Text style={{ fontSize: 14, fontWeight: on ? '700' : '500', color: on ? '#1B4332' : '#4B5563' }}>{label}</Text>
    </TouchableOpacity>
  );

  const placeQ = (
    <Q mode={mode} n={1} title={t('qPlace')} hint={t('qPlaceHint')}>
      <TouchableOpacity
        onPress={useMyLocation}
        disabled={locating}
        activeOpacity={0.85}
        style={{ minHeight: 76, borderRadius: 14, borderWidth: 1, borderColor: hasLocation ? '#2D6A4F' : '#E5E7EB', backgroundColor: hasLocation ? '#F0FDF4' : '#FFFFFF', flexDirection: 'row', alignItems: 'center', padding: S.md }}
      >
        <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: hasLocation ? '#2D6A4F' : '#F3F4F6', alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
          {locating ? <ActivityIndicator size="small" color={hasLocation ? '#FFFFFF' : '#2D6A4F'} /> : <Icon name={hasLocation ? 'check' : 'location'} size={22} color={hasLocation ? '#FFFFFF' : '#4B5563'} />}
        </View>
        <View style={fs.flex1}>
          <Text style={{ fontSize: 18, fontWeight: '800', color: C.text }}>
            {locating ? t('locating') : hasLocation ? (placeName || (geocoding ? t('lookingUpPlace') : t('locationFound'))) : t('findMyLocation')}
          </Text>
          <Text style={{ fontSize: 14, color: C.muted, marginTop: 2 }}>{hasLocation ? t('locationTapAgain') : t('locationStandInField')}</Text>
        </View>
      </TouchableOpacity>

      {hasLocation ? (
        <View style={fs.locationFoundBox}>
          <View style={fs.locationFoundHeader}>
            <View style={fs.locationFoundHeaderLeft}>
              <Text style={{ fontSize: 16 }}>📍</Text>
              <Text style={{ fontSize: 14, fontWeight: '800', color: '#1B4332' }}>Exact Location Pin</Text>
            </View>
            <View style={fs.pinnedBadge}>
              <Text style={{ fontSize: 11, fontWeight: '700', color: '#fff' }}>PINNED</Text>
            </View>
          </View>
          <Text style={fs.coordsText}>
            {`${parseFloat(lat).toFixed(5)}°N, ${parseFloat(lon).toFixed(5)}°E`}
          </Text>
          {placeName ? (
            <Text style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
              {placeName}
            </Text>
          ) : null}
        </View>
      ) : null}

      <View style={fs.coordsSection}>
        <Text style={fs.coordsLabel}>
          {t('enterCoords')} (Latitude / Longitude)
        </Text>
        <View style={fs.coordsRow}>
          <Input style={[bigInput, { flex: 1 }]} value={lat} onChangeText={setLat} onEndEditing={onCoordsBlur} placeholder={t('latitude')} keyboardType="numbers-and-punctuation" />
          <Input style={[bigInput, { flex: 1 }]} value={lon} onChangeText={setLon} onEndEditing={onCoordsBlur} placeholder={t('longitude')} keyboardType="numbers-and-punctuation" />
        </View>
      </View>
    </Q>
  );

  const sizeQ = (
    <Q mode={mode} n={2} title={t('qSize')}>
      <Text style={fs.sizeLabel}>{t('fieldName')}</Text>
      <Input value={name} onChangeText={setName} placeholder={t('fieldNameHint')} style={bigInput} />
      <Text style={fs.areaLabel}>{t('areaQ')}</Text>
      <View style={fs.areaRow}>
        <Input value={area} onChangeText={setArea} keyboardType="decimal-pad" placeholder="0" style={[bigInput, { width: 120, marginRight: S.md, textAlign: 'center' }]} />
        <View style={fs.unitRow}>
          {(['gunta', 'acre', 'ha'] as Unit[]).map((u) => pill(
            t(u === 'acre' ? 'unitAcre' : u === 'gunta' ? 'unitGunta' : 'unitHectare'), unit === u,
            () => {
              const n = parseFloat(area);
              if (n > 0) setArea(trimNum((n * HA_PER[unit]) / HA_PER[u]));
              setUnit(u);
            }, u,
          ))}
        </View>
      </View>
      {unit !== 'ha' && parseFloat(area) > 0 ? (
        <Text style={{ fontSize: 14, color: C.muted }}>{t('areaAsHa').replace('{ha}', trimNum(parseFloat(area) * HA_PER[unit]))}</Text>
      ) : null}
    </Q>
  );

  const cropItems: PickItem[] = (() => {
    const q = cropQ.trim().toLowerCase();
    let keys = q
      ? CROP_TYPES.filter((c) => c.includes(q) || cropLabel(lang, c).toLowerCase().includes(q))
      : allCrops ? [...CROP_TYPES] : [...POPULAR_CROPS];
    if (!q && !allCrops && crop && !keys.includes(crop)) keys = [crop, ...keys];
    return keys.map((c) => ({ key: c, label: cropLabel(lang, c), icon: 'sprout' as IconName }));
  })();
  const cropQn = (
    <Q mode={mode} n={3} title={t('qCrop')} hint={t('qCropHint')}>
      <Input value={cropQ} onChangeText={setCropQ} placeholder={t('searchCrop')} style={[bigInput, { marginBottom: S.md }]} />
      <PickGrid prefix="crop" items={cropItems} selected={crop} onSelect={setCrop} columns={3} />
      {!cropQ.trim() ? (
        <TouchableOpacity onPress={() => setAllCrops(!allCrops)} style={fs.showMoreBtn}>
          <Text style={fs.showMoreText}>{allCrops ? t('showFewerCrops') : t('showAllCrops')}</Text>
        </TouchableOpacity>
      ) : null}
      <View style={fs.noPillRow}>{pill(t('nothingPlanted'), crop === null, () => setCrop(null), 'none')}</View>
    </Q>
  );

  const plantedQ = (
    <Q mode={mode} n={4} title={t('sownOn')} hint={t('sownOnHint')}>
      <View style={fs.plantedRow}>
        {PLANTED.map((p) => pill(t(p.key), quick === p.k, () => { setQuick(p.k); setSown(daysAgo(p.days)); }, p.k))}
      </View>
      <Text style={fs.orExactDateText}>{t('orExactDate')}</Text>
      <DateField value={sown} onChange={(d) => { setSown(d); setQuick(null); }} locale={lang} maxDate={new Date()} doneLabel={t('save')} todayLabel={t('today')} />
      <Text style={fs.plantedAroundText}>
        {t('plantedAround').replace('{d}', new Date(sown + 'T00:00:00').toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' }))}
      </Text>
    </Q>
  );

  const soilItems: PickItem[] = SOIL_TYPES.map((s) => ({
    key: s, label: s === 'unknown' ? t('soilUnknown') : soilLabel(lang, s), desc: t(`soilDesc_${s}`),
    icon: (s === 'unknown' ? 'info' : 'field') as IconName, tint: SOIL_TINT[s],
  }));
  const soilQ = (
    <Q mode={mode} n={5} title={t('qSoil')} hint={t('qSoilHint')}>
      <PickGrid prefix="soil" items={soilItems} selected={soil} onSelect={setSoil} columns={2} />
    </Q>
  );

  // ------------------------------------------------------------------ frame
  const heroH = mode === 'steps' ? 120 : 176;
  const hero = (
    <ImageBackground source={require('../../assets/field-hero.jpg')} resizeMode="cover" style={{ width: w, height: heroH }}>
      <Svg width={w} height={heroH} style={{ position: 'absolute' }}>
        <Defs>
          <LinearGradient id="hs" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#0E240E" stopOpacity="0.55" />
            <Stop offset="1" stopColor="#0E240E" stopOpacity="0.8" />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width={w} height={heroH} fill="url(#hs)" />
      </Svg>
      <View style={fs.heroContent}>
        <View style={fs.heroHeaderRow}>
          {onCancel || mode === 'steps' ? (
            <TouchableOpacity onPress={mode === 'steps' ? back : onCancel} disabled={busy} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }} style={fs.heroBackBtn}>
              <Icon name="chevron-back" size={22} color="#fff" />
            </TouchableOpacity>
          ) : null}
          <Text style={fs.heroTitle}>{initial ? t('editField') : t('addField')}</Text>
        </View>
        {mode === 'page' ? <Text style={{ fontSize: 16, lineHeight: 22, color: 'rgba(255,255,255,0.9)' }}>{t('fieldHeroSub')}</Text> : null}
      </View>
    </ImageBackground>
  );

  const modeSwitch = (
    <View style={fs.modeSwitchRow}>
      {([['page', t('viewOnePage')], ['steps', t('viewSteps')]] as ['page' | 'steps', string][]).map(([m, label]) => (
        <TouchableOpacity key={m} onPress={() => chooseMode(m)} style={{ paddingVertical: 8, paddingHorizontal: 16, borderRadius: 19, backgroundColor: mode === m ? C.accent : 'transparent' }}>
          <Text style={{ fontSize: 14, fontWeight: '700', color: mode === m ? '#fff' : C.text }}>{label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  const errBox = err ? <View style={fs.errBox}><Banner text={err} kind="error" /></View> : null;

  const primary = (label: string, onPress: () => void, kind: 'primary' | 'secondary' = 'primary', flex?: number) => (
    <TouchableOpacity
      onPress={() => { feedback.tap(); onPress(); }}
      disabled={busy}
      activeOpacity={0.85}
      style={{
        flex,
        minHeight: 52,
        borderRadius: 12,
        backgroundColor: kind === 'primary' ? '#1B4332' : '#FFFFFF',
        borderWidth: kind === 'primary' ? 0 : 1,
        borderColor: '#E5E7EB',
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: S.lg,
        opacity: busy ? 0.6 : 1,
      }}
    >
      <Text style={{ fontSize: 16, fontWeight: '700', color: kind === 'primary' ? '#FFFFFF' : '#374151' }}>{label}</Text>
    </TouchableOpacity>
  );

  // New-field save/fetch: a dedicated screen, not the form, so nothing here can
  // be edited mid-fetch and the user has a deliberate confirmation step before
  // landing on the new field's advice (module-47 UX feedback -- editable
  // form + auto-jump felt jarring).
  if (!initial && (busy || savedField)) {
    const ready = !!savedField;
    return (
      <View style={fs.rootView}>
        {hero}
        <View style={fs.readyCenter}>
          <View style={{ width: 88, height: 88, borderRadius: 44, backgroundColor: ready ? C.accent : '#E4EFD9', alignItems: 'center', justifyContent: 'center', marginBottom: S.lg }}>
            {ready ? <Icon name="check" size={44} color="#fff" /> : <ActivityIndicator size="large" color={C.accent} />}
          </View>
          <Text style={fs.readyTitle}>
            {ready ? t('fieldReadyTitle') : t('fieldAdded')}
          </Text>
          <Text style={fs.readySubtitle}>
            {ready ? t('fieldReadySub') : t('fetchingFieldData')}
          </Text>
        </View>
        {ready ? (
          <View style={{ padding: S.lg, paddingBottom: S.xl }}>
            {primary(t('continue'), () => onDone(savedField!))}
          </View>
        ) : null}
      </View>
    );
  }

  if (mode === 'steps') {
    const cur = [placeQ, sizeQ, cropQn, plantedQ, soilQ][step];
    const last = step === STEPS.length - 1;
    return (
      <View style={fs.rootView}>
        {hero}
        <View style={fs.progressBarRow}>
          {STEPS.map((_, i) => <View key={i} style={{ flex: 1, height: 5, borderRadius: 3, backgroundColor: i <= step ? '#1B4332' : '#E5E7EB' }} />)}
        </View>
        <Text style={fs.stepCountText}>
          {t('stepOf').replace('{n}', String(step + 1)).replace('{m}', String(STEPS.length))}
        </Text>
        <ScrollView contentContainerStyle={{ paddingHorizontal: S.lg, paddingBottom: S.xl }} keyboardShouldPersistTaps="handled">
          {cur}
          {errBox}
        </ScrollView>
        <View style={fs.stepsNavBar}>
          {step > 0 || onCancel ? primary(t('wizBack'), back, 'secondary', 1) : null}
          {primary(last ? t('saveField') : t('wizNext'), next, 'primary', 2)}
        </View>
      </View>
    );
  }

  return (
    <View style={fs.rootView}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: S.xl * 2 }}>
        {hero}
        <View style={fs.pageContent}>
          {modeSwitch}
          {placeQ}
          {sizeQ}
          {cropQn}
          {plantedQ}
          {soilQ}
          {errBox}
          <View style={fs.saveBtnWrapper}>{primary(t('saveField'), submit)}</View>
          {onCancel ? <View style={fs.cancelBtnWrapper}>{primary(t('cancel'), onCancel, 'secondary')}</View> : null}
        </View>
      </ScrollView>
    </View>
  );
}

const fs = StyleSheet.create({
  flex1: { flex: 1 },
  rootView: { flex: 1, backgroundColor: C.bg },
  // Q component
  qRow: { flexDirection: 'row', alignItems: 'center' },
  qStepBadge: { width: 30, height: 30, borderRadius: 15, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', marginRight: S.sm },
  qStepBadgeText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  qHint: { fontSize: 15, lineHeight: 22, color: C.muted, marginTop: S.xs },
  qChildren: { marginTop: S.md },
  // placeQ
  locationFoundBox: { marginTop: S.md, padding: S.md, backgroundColor: '#F1F7EE', borderRadius: 16, borderWidth: 1.5, borderColor: '#C4DFC0' },
  locationFoundHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  locationFoundHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  pinnedBadge: { backgroundColor: '#2E7D32', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  coordsText: { fontSize: 13, color: '#2D6A4F', fontWeight: '600' },
  coordsSection: { marginTop: S.md },
  coordsLabel: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 6 },
  coordsRow: { flexDirection: 'row', gap: S.sm },
  // sizeQ
  sizeLabel: { fontSize: 16, fontWeight: '700', color: C.text, marginBottom: S.sm },
  areaLabel: { fontSize: 16, fontWeight: '700', color: C.text, marginTop: S.lg, marginBottom: S.sm },
  areaRow: { flexDirection: 'row', alignItems: 'center' },
  unitRow: { flex: 1, flexDirection: 'row', flexWrap: 'wrap' },
  // cropQn
  showMoreBtn: { minHeight: 48, justifyContent: 'center', alignItems: 'center' },
  showMoreText: { color: C.accent, fontWeight: '800', fontSize: 16 },
  noPillRow: { flexDirection: 'row', marginTop: S.xs },
  // plantedQ
  plantedRow: { flexDirection: 'row', flexWrap: 'wrap' },
  orExactDateText: { fontSize: 15, color: C.muted, marginTop: S.xs, marginBottom: S.sm },
  plantedAroundText: { fontSize: 15, color: C.accent, fontWeight: '700', marginTop: S.sm },
  // hero
  heroContent: { flex: 1, paddingTop: 44, paddingHorizontal: S.lg, justifyContent: 'space-between', paddingBottom: S.md },
  heroHeaderRow: { flexDirection: 'row', alignItems: 'center' },
  heroBackBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.22)', alignItems: 'center', justifyContent: 'center', marginRight: S.md },
  heroTitle: { flex: 1, fontSize: 26, fontWeight: '800', color: '#fff' },
  // modeSwitch
  modeSwitchRow: { flexDirection: 'row', backgroundColor: '#E4EFD9', borderRadius: 22, padding: 3, alignSelf: 'flex-start', marginTop: S.md },
  // errBox
  errBox: { marginTop: S.md },
  // loading/ready screen
  readyCenter: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: S.xl },
  readyTitle: { fontSize: 22, fontWeight: '800', color: C.text, textAlign: 'center' },
  readySubtitle: { fontSize: 16, lineHeight: 23, color: C.muted, textAlign: 'center', marginTop: S.sm },
  // steps mode
  progressBarRow: { flexDirection: 'row', gap: 6, paddingHorizontal: S.lg, marginTop: S.md },
  stepCountText: { paddingHorizontal: S.lg, marginTop: S.sm, fontSize: 13, color: C.muted, fontWeight: '600' },
  stepsNavBar: { flexDirection: 'row', gap: S.md, padding: S.lg, paddingBottom: S.xl, borderTopWidth: 1, borderTopColor: '#E5E7EB', backgroundColor: C.bg },
  // page mode
  pageContent: { paddingHorizontal: S.lg },
  saveBtnWrapper: { marginTop: S.xl },
  cancelBtnWrapper: { marginTop: S.md },
});
