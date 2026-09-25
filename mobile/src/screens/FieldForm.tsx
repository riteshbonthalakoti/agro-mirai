import React, { useEffect, useState } from 'react';
import { ScrollView, Text, TouchableOpacity, View } from 'react-native';
import * as Location from 'expo-location';
import { ApiError, Field, createField, patchField } from '../api';
import { cropLabel, soilLabel, useApp } from '../ctx';
import { DateField } from '../datepicker';
import { Icon } from '../../icons';
import { CROP_TYPES, SOIL_TYPES } from '../i18n';
import { C, S } from '../theme';
import { useToast } from '../toast';
import { Banner, Btn, Chip, Input, Label, Muted, st } from '../ui';

// farmers here think in acres and guntas; the backend stores hectares
type Unit = 'acre' | 'gunta' | 'ha';
const HA_PER: Record<Unit, number> = { acre: 0.404686, gunta: 0.0101171, ha: 1 };
const trimNum = (n: number) => String(Math.round(n * 100) / 100);

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Add (no `initial`) or edit a field. Add posts to POST /v2/fields, which
 *  fetches weather + soil synchronously and starts NDVI in the background. */
export function FieldForm({ initial, onDone, onCancel }: { initial?: Field; onDone: (f: Field) => void; onCancel?: () => void }) {
  const { t, lang } = useApp();
  const toast = useToast();
  const [name, setName] = useState(initial?.name ?? '');
  const [unit, setUnit] = useState<Unit>('acre');
  const [area, setArea] = useState(initial ? trimNum(initial.area_ha / HA_PER.acre) : '');
  const [lat, setLat] = useState(initial ? String(initial.latitude) : '');
  const [lon, setLon] = useState(initial ? String(initial.longitude) : '');
  const [soil, setSoil] = useState<string | null>(initial?.soil_type ?? null);
  const [crop, setCrop] = useState<string | null>(initial?.current_crop ?? null);
  const [sown, setSown] = useState(initial?.sown_on ?? today());
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [err, setErr] = useState('');
  const [placeName, setPlaceName] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);

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

  // Fields opened for editing already have coordinates -- show their district
  // right away instead of only after the farmer touches "use my location".
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
      if (perm.status !== 'granted') {
        setErr(t('permLocation'));
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setLat(loc.coords.latitude.toFixed(5));
      setLon(loc.coords.longitude.toFixed(5));
      lookupPlace(loc.coords.latitude, loc.coords.longitude);
    } catch {
      setErr(t('locFailed'));
    } finally {
      setLocating(false);
    }
  };

  // Coordinates can also be typed by hand -- look up the district once both
  // fields hold a plausible value.
  const onCoordsBlur = () => {
    const latN = parseFloat(lat);
    const lonN = parseFloat(lon);
    if (!isNaN(latN) && !isNaN(lonN) && Math.abs(latN) <= 90 && Math.abs(lonN) <= 180) lookupPlace(latN, lonN);
  };

  const submit = async () => {
    setErr('');
    const areaN = Math.round(parseFloat(area) * HA_PER[unit] * 10000) / 10000;
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
      toast.show(initial ? t('fieldUpdated') : t('fieldAdded'), 'ok');
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
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.sm }}>
        {onCancel ? (
          <TouchableOpacity onPress={onCancel} disabled={busy} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }} style={{ marginRight: S.sm }}>
            <Icon name="chevron-back" size={24} color={C.text} />
          </TouchableOpacity>
        ) : null}
        <Text style={[st.h1, { marginBottom: 0 }]}>{initial ? t('editField') : t('addField')}</Text>
      </View>
      {err ? <Banner text={err} kind="error" /> : null}
      {busy && !initial ? <Banner text={t('fetchingFieldData')} /> : null}

      <Label>{t('fieldName')}</Label>
      <Input value={name} onChangeText={setName} />

      <Label>{t('area')}</Label>
      <Input value={area} onChangeText={setArea} keyboardType="decimal-pad" />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: S.sm }}>
        {(['acre', 'gunta', 'ha'] as Unit[]).map((u) => (
          <Chip
            key={u}
            label={t(u === 'acre' ? 'unitAcre' : u === 'gunta' ? 'unitGunta' : 'unitHectare')}
            selected={unit === u}
            onPress={() => {
              // keep the same land size when the unit changes
              const n = parseFloat(area);
              if (n > 0) setArea(trimNum((n * HA_PER[unit]) / HA_PER[u]));
              setUnit(u);
            }}
          />
        ))}
      </View>
      {unit !== 'ha' && parseFloat(area) > 0 ? (
        <Muted>{t('areaAsHa').replace('{ha}', trimNum(parseFloat(area) * HA_PER[unit]))}</Muted>
      ) : null}

      <Label>{t('location')}</Label>
      <Btn label={t('useMyLocation')} kind="secondary" onPress={useMyLocation} busy={locating} />
      <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.sm }}>
        <Input style={{ flex: 1 }} value={lat} onChangeText={setLat} onEndEditing={onCoordsBlur} placeholder={t('latitude')} keyboardType="numbers-and-punctuation" />
        <Input style={{ flex: 1 }} value={lon} onChangeText={setLon} onEndEditing={onCoordsBlur} placeholder={t('longitude')} keyboardType="numbers-and-punctuation" />
      </View>
      {geocoding ? <Muted style={{ marginTop: 4 }}>{t('lookingUpPlace')}</Muted> : null}
      {placeName ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
          <Icon name="location" size={14} color={C.accent} />
          <Text style={{ marginLeft: 4, color: C.accent, fontSize: 13, fontWeight: '600' }}>{placeName}</Text>
        </View>
      ) : null}

      <Label>{t('sownOn')}</Label>
      <View style={{ flexDirection: 'row', gap: S.sm, alignItems: 'center' }}>
        <View style={{ flex: 1 }}>
          <DateField value={sown} onChange={setSown} locale={lang} maxDate={new Date()} doneLabel={t('save')} todayLabel={t('today')} />
        </View>
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
