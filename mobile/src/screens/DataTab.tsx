import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { ApiError, dataSummary, refreshData, Weather } from '../api';
import { fmtDate, useApp } from '../ctx';
import { errorText, useLoad } from '../hooks';
import { Key } from '../i18n';
import { Icon, IconName } from '../../icons';
import { SkeletonCard } from '../skeleton';
import { cacheGet, cacheSet, formatTime } from '../storage';
import { C, S } from '../theme';
import { Banner, Btn, KV, Muted } from '../ui';

const AUTO_REFRESH_MS = 30 * 60 * 1000;

const num = (v: number | null | undefined, unit = '', digits = 1) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 10 ** digits) / 10 ** digits}${unit}`;

/** Friendly names for the technical `source` strings the backend stores. */
function sourceName(t: (k: Key) => string, src?: string | null): string {
  if (!src) return '—';
  const s = src.toLowerCase();
  if (s.includes('open_meteo') || s.includes('open-meteo')) return t('srcOpenMeteo');
  if (s.includes('soilgrids') && s.includes('soil_type')) return `${t('srcSoilGrids')} + ${t('srcSoilType')} (${t('estimate')})`;
  if (s.includes('soil_type')) return `${t('srcSoilType')} (${t('estimate')})`;
  if (s.includes('soilgrids')) return t('srcSoilGrids');
  if (s.includes('gee')) return t('srcSatellite');
  if (s === 'cache') return t('srcSavedSat');
  return src;
}

function phBand(t: (k: Key) => string, ph?: number | null) {
  if (ph === null || ph === undefined) return '';
  return ph < 6 ? t('phAcid') : ph > 7.8 ? t('phAlk') : t('phOk');
}
function humidityBand(t: (k: Key) => string, h?: number | null) {
  if (h === null || h === undefined) return '';
  return h < 40 ? t('humDry') : h > 80 ? t('humHigh') : t('humOk');
}
function ndviBand(t: (k: Key) => string, v: number) {
  return v < 0.3 ? t('ndviLow') : v < 0.6 ? t('ndviMid') : t('ndviHigh');
}

function WeatherRow({ w }: { w: Weather }) {
  const { t } = useApp();
  return (
    <KV
      k={fmtDate(w.observed_at)}
      v={`${num(w.temp_min_c, '°', 0)}–${num(w.temp_max_c ?? w.temp_c, '°', 0)} · ${t('rainName')} ${num(w.rainfall_mm, ' mm', 0)}`}
    />
  );
}

export function DataTab() {
  const { field, t } = useApp();
  const id = field?.id;
  const sum = useLoad(id ? `sum:${id}` : null, () => dataSummary(id!), [id]);
  const [updating, setUpdating] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  // Pull fresh weather/soil/satellite readings from the sources, then reload.
  // Weather and soil come back in a few seconds; the satellite value arrives
  // later from a background job, so look again after 20 s and 45 s.
  const doRefresh = useCallback(async (silent: boolean) => {
    if (!id) return;
    setErr('');
    if (!silent) setMsg('');
    setUpdating(true);
    try {
      await refreshData(id);
      cacheSet(`refreshedAt:${id}`, Date.now());
      if (!silent) setMsg(t('dataRefreshed'));
      sum.reload();
      timers.current.push(setTimeout(sum.reload, 20000), setTimeout(sum.reload, 45000));
    } catch (e) {
      setErr(errorText(t, e as ApiError));
    } finally {
      setUpdating(false);
    }
  }, [id, sum.reload, t]);

  // Data used to sit forever at whatever time the field was created; refresh
  // automatically when the tab opens if the last refresh is over 30 minutes old.
  useEffect(() => {
    if (!id) return;
    (async () => {
      const last = await cacheGet<number>(`refreshedAt:${id}`);
      if (!last || Date.now() - last > AUTO_REFRESH_MS) doRefresh(true);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const d = sum.data;
  const cur = d?.weather.current;
  const su = d?.soil_used;
  const soil = d?.soil;
  const ndvi = d?.ndvi.latest;

  if (sum.loading && !d) {
    return (
      <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
        <SkeletonCard /><SkeletonCard /><SkeletonCard />
      </ScrollView>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}
      refreshControl={<RefreshControl refreshing={sum.loading || updating} onRefresh={() => doRefresh(false)} />}
    >
      {sum.error ? <Banner text={errorText(t, sum.error)} kind="error" /> : null}
      {updating ? <Banner text={t('updatingNow')} /> : null}
      {msg ? <Banner text={msg} kind="ok" /> : null}
      {err ? <Banner text={err} kind="error" /> : null}
      <Btn label={updating ? t('refreshing') : t('refreshData')} onPress={() => doRefresh(false)} busy={updating} style={{ marginBottom: S.md }} />

      <Tile
        icon="thermo" title={t('weather')} empty={!cur ? t('noData') : undefined}
        details={cur ? (
          <>
            <KV k={t('tempName')} v={`${num(cur.temp_c, '°C')}  (${num(cur.temp_min_c, '°', 0)}–${num(cur.temp_max_c, '°', 0)})`} />
            <KV k={t('humidityName')} v={num(cur.humidity_pct, '%', 0)} />
            <KV k={t('rainName')} v={num(cur.rainfall_mm, ' mm')} />
            <KV k={t('wind')} v={num(cur.wind_mps !== null && cur.wind_mps !== undefined ? cur.wind_mps * 3.6 : null, ' km/h', 0)} />
            <KV k={t('howOld')} v={fmtDate(cur.observed_at, true)} />
            <KV k={t('source')} v={sourceName(t, cur.source)} />
            {d?.fetched_at ? <KV k={t('lastChecked')} v={formatTime(d.fetched_at)} /> : null}
          </>
        ) : undefined}
      >
        {cur ? (
          <>
            <Text style={big}>{num(cur.temp_c, '°C', 0)}</Text>
            <Line icon="drop" text={`${t('rainName')}: ${num(cur.rainfall_mm, ' mm', 0)}`} />
            {humidityBand(t, cur.humidity_pct) ? <Line icon="info" text={humidityBand(t, cur.humidity_pct)} /> : null}
          </>
        ) : null}
      </Tile>

      {d && d.weather.forecast.length ? (
        <Tile icon="list" title={t('forecast')}>
          {d.weather.forecast.slice(0, 5).map((w, i) => <WeatherRow key={i} w={w} />)}
        </Tile>
      ) : null}

      <Tile
        icon="field" title={t('soil')} empty={!(su || soil) ? t('noData') : undefined}
        details={su || soil ? (
          <>
            <KV k={t('phName')} v={num(su?.ph ?? soil?.ph, '', 1)} />
            <KV k={t('nName')} v={num(su?.nitrogen_mg_per_kg, ' mg/kg', 0)} />
            <KV k={t('pName')} v={su?.phosphorus_mg_per_kg != null ? `${num(su.phosphorus_mg_per_kg, ' mg/kg', 0)} (${t('estimate')})` : '—'} />
            <KV k={t('kName')} v={su?.potassium_mg_per_kg != null ? `${num(su.potassium_mg_per_kg, ' mg/kg', 0)} (${t('estimate')})` : '—'} />
            <KV k={t('ocName')} v={num(su?.organic_carbon_pct ?? soil?.organic_carbon_pct, '%', 1)} />
            <KV k={t('moistName')} v={su?.moisture_pct != null ? `${num(su.moisture_pct, '%', 0)} (${t('estimate')})` : num(soil?.moisture_pct, '%')} />
            <KV k={t('source')} v={sourceName(t, su?.chemistry_source ?? soil?.source)} />
          </>
        ) : undefined}
      >
        {su || soil ? (
          <Text style={{ fontSize: 17, fontWeight: '600', color: C.text }}>
            {phBand(t, su?.ph ?? soil?.ph) || t('noData')}
          </Text>
        ) : null}
      </Tile>

      <Tile
        icon="leaf" title={t('ndviName')} empty={!ndvi ? t('ndviGathering') : undefined}
        details={ndvi ? (
          <>
            <KV k={t('ndviName')} v={num(ndvi.ndvi, '', 2)} />
            <KV k={t('howOld')} v={fmtDate(ndvi.observed_at, true)} />
            <KV k={t('cloud')} v={num(ndvi.cloud_cover_pct, '%', 0)} />
            <KV k={t('source')} v={sourceName(t, ndvi.source)} />
          </>
        ) : undefined}
      >
        {ndvi ? (
          <Text style={{ fontSize: 17, fontWeight: '600', color: ndvi.ndvi < 0.3 ? C.high : ndvi.ndvi < 0.6 ? C.moderate : C.low }}>
            {ndviBand(t, ndvi.ndvi)}
          </Text>
        ) : null}
      </Tile>
      <View style={{ height: S.xl }} />
    </ScrollView>
  );
}

const big = { fontSize: 36, fontWeight: '700' as const, color: C.text, marginBottom: S.xs };

function Tile({ icon, title, empty, children, details }: { icon: IconName; title: string; empty?: string; children?: React.ReactNode; details?: React.ReactNode }) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  return (
    <View style={{ borderWidth: 1, borderColor: C.border, borderRadius: 12, padding: S.lg, marginBottom: S.md, backgroundColor: C.bg }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.sm }}>
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: C.surface, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
          <Icon name={icon} size={20} color={C.accent} />
        </View>
        <Text style={{ fontSize: 16, fontWeight: '700', color: C.text, flex: 1 }}>{title}</Text>
      </View>
      {empty ? <Muted>{empty}</Muted> : children}
      {details && !empty ? (
        <View style={{ marginTop: S.md, borderTopWidth: 1, borderTopColor: C.border, paddingTop: S.sm }}>
          <TouchableOpacity onPress={() => setOpen(!open)} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 4 }}>
            <Text style={{ color: C.accent, fontWeight: '600', flex: 1 }}>{open ? t('hideAllData') : t('showAllData')}</Text>
            <Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} color={C.accent} />
          </TouchableOpacity>
          {open ? <View style={{ marginTop: S.sm }}>{details}</View> : null}
        </View>
      ) : null}
    </View>
  );
}

function Line({ icon, text }: { icon: IconName; text: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
      <Icon name={icon} size={16} color={C.muted} />
      <Text style={{ marginLeft: S.sm, fontSize: 15, color: C.text, flexShrink: 1 }}>{text}</Text>
    </View>
  );
}
