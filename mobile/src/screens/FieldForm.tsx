import React, { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import * as Location from 'expo-location';
import { ApiError, Field, createField, patchField } from '../api';
import { cropLabel, soilLabel, useApp } from '../ctx';
import { CROP_TYPES, SOIL_TYPES } from '../i18n';
import { S } from '../theme';
import { Banner, Btn, Chip, Input, Label, Muted, st } from '../ui';

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Add (no `initial`) or edit a field. Add posts to POST /v2/fields, which
 *  fetches weather + soil synchronously and starts NDVI in the background. */
export function FieldForm({ initial, onDone, onCancel }: { initial?: Field; onDone: (f: Field) => void; onCancel?: () => void }) {
  const { t, lang } = useApp();
  const [name, setName] = useState(initial?.name ?? '');
  const [area, setArea] = useState(initial ? String(initial.area_ha) : '');
  const [lat, setLat] = useState(initial ? String(initial.latitude) : '');
  const [lon, setLon] = useState(initial ? String(initial.longitude) : '');
  const [soil, setSoil] = useState<string | null>(initial?.soil_type ?? null);
  const [crop, setCrop] = useState<string | null>(initial?.current_crop ?? null);
  const [sown, setSown] = useState(initial?.sown_on ?? today());
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [err, setErr] = useState('');

  const useMyLocation = async () => {
    setLocating(true);
    setErr('');
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== 'granted') {
        setErr(t('permLocation'));
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setLat(loc.coords.latitude.toFixed(5));
      setLon(loc.coords.longitude.toFixed(5));
    } catch {
      setErr(t('locFailed'));
    } finally {
      setLocating(false);
    }
  };

  const submit = async () => {
    setErr('');
    const areaN = parseFloat(area);
    const latN = parseFloat(lat);
    const lonN = parseFloat(lon);
    if (!name.trim()) return setErr(t('fieldNameRequired'));
    if (!(areaN > 0)) return setErr(t('areaRequired'));
    if (isNaN(latN) || isNaN(lonN) || Math.abs(latN) > 90 || Math.abs(lonN) > 180) return setErr(t('locationRequired'));
    if (!/^\d{4}-\d{2}-\d{2}$/.test(sown) || isNaN(Date.parse(sown))) return setErr(t('dateInvalid'));

    const payload: Record<string, unknown> = {
      name: name.trim(), latitude: latN, longitude: lonN, area_ha: areaN, sown_on: sown,
    };
    if (soil) payload.soil_type = soil;
    if (crop) payload.current_crop = crop;

    setBusy(true);
    try {
      const saved = initial ? await patchField(initial.id, payload) : await createField(payload);
      onDone(saved);
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.isNetwork ? t('cantReachServer') : ae.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: 48 }} keyboardShouldPersistTaps="handled">
      <Text style={st.h1}>{initial ? t('editField') : t('addField')}</Text>
      {err ? <Banner text={err} kind="error" /> : null}
      {busy && !initial ? <Banner text={t('fetchingFieldData')} /> : null}

      <Label>{t('fieldName')}</Label>
      <Input value={name} onChangeText={setName} />

      <Label>{t('area')}</Label>
      <Input value={area} onChangeText={setArea} keyboardType="decimal-pad" />

      <Label>{t('location')}</Label>
      <Btn label={t('useMyLocation')} kind="secondary" onPress={useMyLocation} busy={locating} />
      <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.sm }}>
        <Input style={{ flex: 1 }} value={lat} onChangeText={setLat} placeholder={t('latitude')} keyboardType="numbers-and-punctuation" />
        <Input style={{ flex: 1 }} value={lon} onChangeText={setLon} placeholder={t('longitude')} keyboardType="numbers-and-punctuation" />
      </View>

      <Label>{t('sownOn')}</Label>
      <View style={{ flexDirection: 'row', gap: S.sm }}>
        <Input style={{ flex: 1 }} value={sown} onChangeText={setSown} placeholder="YYYY-MM-DD" />
        <Btn label={t('today')} kind="secondary" onPress={() => setSown(today())} />
      </View>
      <Muted style={{ marginTop: 4 }}>{t('sownOnHint')}</Muted>

      <Label>{`${t('soilType')} (${t('optional')})`}</Label>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
        {SOIL_TYPES.map((s) => (
          <Chip key={s} label={soilLabel(lang, s)} selected={soil === s} onPress={() => setSoil(soil === s ? null : s)} />
        ))}
      </View>

      <Label>{`${t('currentCrop')} (${t('optional')})`}</Label>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
        {CROP_TYPES.map((c) => (
          <Chip key={c} label={cropLabel(lang, c)} selected={crop === c} onPress={() => setCrop(crop === c ? null : c)} />
        ))}
      </View>

      <Btn label={t('saveField')} onPress={submit} busy={busy} style={{ marginTop: S.xl }} />
      {onCancel ? <Btn label={t('cancel')} kind="secondary" onPress={onCancel} disabled={busy} style={{ marginTop: S.md }} /> : null}
    </ScrollView>
  );
}
