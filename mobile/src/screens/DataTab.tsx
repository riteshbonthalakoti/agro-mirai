import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshControl, ScrollView, Text, TouchableOpacity, View, useWindowDimensions } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { ApiError, dataSummary, refreshData, Weather, DataSummary } from '../api';
import { fmtDate, useApp } from '../ctx';
import { errorText, useLoad } from '../hooks';
import { Key } from '../i18n';
import { Icon, IconName } from '../../icons';
import { SegmentedMeter } from '../components/Charts';
import { SkeletonCard } from '../skeleton';
import { cacheGet, cacheSet, formatTime } from '../storage';
import { C, S } from '../theme';
import { Banner, KV, LastUpdated, Muted } from '../ui';
import { FieldMapScreen } from './FieldMapScreen';

const AUTO_REFRESH_MS = 30 * 60 * 1000;

type SubTab = 'insights' | 'history' | 'map';

const num = (v: number | null | undefined, unit = '', digits = 1) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 10 ** digits) / 10 ** digits}${unit}`;

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

function soilHealthLabel(t: (k: Key) => string, ph?: number | null): string {
  if (ph === null || ph === undefined) return '';
  if (ph < 5.5) return t('soilHealthAcid');
  if (ph > 8.0) return t('soilHealthAlk');
  return t('soilHealthGood');
}

function soilHealthColor(ph?: number | null): string {
  if (ph === null || ph === undefined) return C.muted;
  if (ph < 5.5 || ph > 8.0) return C.moderate;
  return C.low;
}

function ndviHealthLabel(t: (k: Key) => string, v: number): string {
  return v < 0.3 ? t('cropsPoor') : v < 0.6 ? t('cropsModerate') : t('cropsHealthy');
}

function ndviHealthColor(v: number): string {
  return v < 0.3 ? C.high : v < 0.6 ? C.moderate : C.low;
}

function humidityBand(t: (k: Key) => string, h?: number | null) {
  if (h === null || h === undefined) return '';
  return h < 40 ? t('humDry') : h > 80 ? t('humHigh') : t('humOk');
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
  const { field, t, lang } = useApp();
  const id = field?.id;
  const sum = useLoad(id ? `sum:${id}` : null, () => dataSummary(id!), [id]);
  const [updating, setUpdating] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [subTab, setSubTab] = useState<SubTab>('insights');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

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

  const { width: w } = useWindowDimensions();

  if (sum.loading && !d) {
    return (
      <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
        <SkeletonCard /><SkeletonCard /><SkeletonCard />
      </ScrollView>
    );
  }

  const hour = new Date().getHours();
  const night = hour >= 19 || hour < 6;
  const ink = night ? '#fff' : C.text;
  const inkSoft = night ? 'rgba(255,255,255,0.78)' : C.muted;
  const rainNow = (cur?.rainfall_mm ?? 0) >= 1;
  const kind: 'rain' | 'cloud' | 'clear' = rainNow ? 'rain' : (cur?.humidity_pct ?? 0) > 78 ? 'cloud' : 'clear';
  const heroW = w - S.lg * 2;
  const heroH = 216;
  const ph = su?.ph ?? soil?.ph;
  const moist = su?.moisture_pct ?? soil?.moisture_pct;

  return (
    <View style={{ flex: 1, backgroundColor: '#F3F0E3' }}>
      <FurrowBackdrop />

      {/* Sub-tab bar */}
      <View style={{ flexDirection: 'row', paddingHorizontal: S.lg, paddingTop: S.md, paddingBottom: 0, gap: S.sm }}>
        {(['insights', 'history', 'map'] as SubTab[]).map((tab) => {
          const labels: Record<SubTab, Key> = { insights: 'tabInsights', history: 'tabHistory', map: 'tabMap' };
          const active = subTab === tab;
          return (
            <TouchableOpacity
              key={tab}
              onPress={() => setSubTab(tab)}
              style={{
                flex: 1, paddingVertical: 10, borderRadius: 14,
                backgroundColor: active ? C.accent : 'rgba(255,255,255,0.6)',
                alignItems: 'center',
                borderWidth: 1,
                borderColor: active ? C.accent : '#D8E2CC',
              }}
            >
              <Text style={{ fontSize: 13, fontWeight: '700', color: active ? '#fff' : C.text }}>{t(labels[tab])}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Map tab — full height */}
      {subTab === 'map' ? (
        <View style={{ flex: 1, marginTop: S.md }}>
          <FieldMapScreen onClose={() => setSubTab('insights')} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: S.xl * 2 }}
          refreshControl={<RefreshControl refreshing={sum.loading || updating} onRefresh={() => doRefresh(false)} />}
        >
          {sum.error ? <Banner text={errorText(t, sum.error)} kind="error" /> : null}
          {msg ? <Banner text={msg} kind="ok" /> : null}
          {err ? <Banner text={err} kind="error" /> : null}

          {subTab === 'insights' ? (
            <>
              {/* Sky hero card */}
              <View style={{ width: heroW, height: heroH, borderRadius: 28, overflow: 'hidden', backgroundColor: night ? '#33456E' : '#CFE8F6' }}>
                <Svg width={heroW} height={heroH} style={{ position: 'absolute' }}>
                  <Defs>
                    <LinearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
                      <Stop offset="0" stopColor={night ? '#1F2C4D' : '#8FCBEB'} />
                      <Stop offset="1" stopColor={night ? '#4C6191' : '#EAF5E6'} />
                    </LinearGradient>
                  </Defs>
                  <Rect x="0" y="0" width={heroW} height={heroH} fill="url(#sky)" />
                  <Circle cx={heroW - 56} cy={54} r={night ? 20 : 26} fill={night ? '#F4F1DC' : '#FFE27A'} opacity={night ? 0.95 : 0.9} />
                  {night ? <Circle cx={heroW - 46} cy={48} r={17} fill="#2A3961" /> : <Circle cx={heroW - 56} cy={54} r={40} fill="#FFE27A" opacity={0.25} />}
                  <Path d={`M0 ${heroH - 46} C ${heroW * 0.25} ${heroH - 74} ${heroW * 0.5} ${heroH - 30} ${heroW * 0.78} ${heroH - 58} S ${heroW} ${heroH - 44} ${heroW} ${heroH - 50} L ${heroW} ${heroH} L 0 ${heroH} Z`} fill={night ? '#1F3B2B' : '#9CCB88'} opacity={0.75} />
                  <Path d={`M0 ${heroH - 22} C ${heroW * 0.3} ${heroH - 44} ${heroW * 0.6} ${heroH - 8} ${heroW} ${heroH - 30} L ${heroW} ${heroH} L 0 ${heroH} Z`} fill={night ? '#173224' : '#7DB56A'} />
                  {kind === 'rain' ? [0.18, 0.3, 0.42, 0.55, 0.66].map((x, k) => (
                    <Path key={k} d={`M${heroW * x} ${70 + (k % 2) * 16} l -5 14`} stroke={night ? '#BFD4FF' : '#5B9BD1'} strokeWidth={2.4} strokeLinecap="round" />
                  )) : null}
                  {kind !== 'clear' ? (
                    <Path d="M60 92 a22 22 0 0 1 40 -10 a18 18 0 0 1 32 6 a15 15 0 0 1 -6 30 H70 a17 17 0 0 1 -10 -26 Z" transform={`translate(${heroW * 0.42} -46) scale(1.15)`} fill="#fff" opacity={night ? 0.55 : 0.95} />
                  ) : null}
                </Svg>
                <View style={{ padding: S.lg, flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Text style={{ flex: 1, fontSize: 13, fontWeight: '800', letterSpacing: 1, color: inkSoft }}>{t('weather').toUpperCase()}</Text>
                    <TouchableOpacity
                      onPress={() => doRefresh(false)}
                      disabled={updating}
                      accessibilityLabel={t('refreshData')}
                      style={{ minHeight: 40, paddingHorizontal: 14, borderRadius: 20, backgroundColor: night ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.75)', flexDirection: 'row', alignItems: 'center' }}
                    >
                      <Text style={{ fontSize: 18, color: ink, marginRight: 6 }}>{updating ? '…' : '↻'}</Text>
                      <Text style={{ fontSize: 13, fontWeight: '700', color: ink }}>{updating ? t('refreshing') : t('refreshData')}</Text>
                    </TouchableOpacity>
                  </View>
                  <LastUpdated at={sum.lastUpdatedAt} stale={!!sum.error} t={t} />
                  {cur ? (
                    <>
                      <Text style={{ fontSize: 64, lineHeight: 72, fontWeight: '800', color: ink, marginTop: 2 }}>{num(cur.temp_c, '°', 0)}</Text>
                      <Text style={{ fontSize: 15, color: inkSoft }}>{`${num(cur.temp_min_c, '°', 0)} – ${num(cur.temp_max_c, '°', 0)}`}</Text>
                    </>
                  ) : <Text style={{ fontSize: 18, color: ink, marginTop: S.lg }}>{t('noData')}</Text>}
                </View>
              </View>

              {/* Three quick facts */}
              {cur ? (
                <View style={{ flexDirection: 'row', gap: S.sm, marginTop: -28, paddingHorizontal: S.sm }}>
                  <Fact icon="drop" value={num(cur.rainfall_mm, ' mm', 0)} label={t('rainName')} tint="#E3F1FA" />
                  <Fact icon="humidity" value={num(cur.humidity_pct, '%', 0)} label={t('humidityName')} tint="#E8F3E8" />
                  <Fact icon="wind" value={num(cur.wind_mps !== null && cur.wind_mps !== undefined ? cur.wind_mps * 3.6 : null, '', 0)} unit="km/h" label={t('wind')} tint="#F6ECD6" />
                </View>
              ) : null}
              {d?.fetched_at ? <Text style={{ fontSize: 12.5, color: C.muted, textAlign: 'center', marginTop: S.sm }}>{`${t('lastChecked')}: ${formatTime(d.fetched_at)}`}</Text> : null}
              {updating ? <View style={{ marginTop: S.sm }}><Banner text={t('updatingNow')} /></View> : null}

              {/* 7-day forecast */}
              {d && d.weather.forecast.length ? (
                <Block title={t('forecast')} icon="list">
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingRight: S.sm }}>
                    {d.weather.forecast.slice(0, 7).map((f, k) => {
                      const rain = f.rainfall_mm ?? 0;
                      return (
                        <View key={k} style={{ width: 80, marginRight: S.sm, borderRadius: 18, backgroundColor: '#fff', borderWidth: 1, borderColor: '#E3E8DC', paddingVertical: S.md, alignItems: 'center' }}>
                          <Text style={{ fontSize: 13, fontWeight: '800', color: C.muted }}>{new Date(f.observed_at).toLocaleDateString(lang, { weekday: 'short' })}</Text>
                          <Text style={{ fontSize: 11, color: C.muted }}>{new Date(f.observed_at).toLocaleDateString(lang, { day: 'numeric', month: 'short' })}</Text>
                          <View style={{ marginVertical: S.sm }}><Glyph kind={rain >= 1 ? 'rain' : 'clear'} /></View>
                          <Text style={{ fontSize: 17, fontWeight: '800', color: C.text }}>{num(f.temp_max_c ?? f.temp_c, '°', 0)}</Text>
                          <Text style={{ fontSize: 13, color: C.muted }}>{num(f.temp_min_c, '°', 0)}</Text>
                          <View style={{ width: 8, height: Math.max(4, Math.min(34, rain * 4)), borderRadius: 4, backgroundColor: '#5B9BD1', opacity: rain >= 1 ? 1 : 0.25, marginTop: S.sm }} />
                          <Text style={{ fontSize: 11.5, color: C.muted, marginTop: 2 }}>{num(rain, ' mm', 0)}</Text>
                        </View>
                      );
                    })}
                  </ScrollView>
                </Block>
              ) : null}

              {/* Soil health — farmer-friendly primary, raw numbers in details */}
              <Block
                title={t('soil')} icon="field"
                details={su || soil ? (
                  <>
                    <KV k={t('phName')} v={`${num(ph, '', 1)} — ${phBand(t, ph)}`} />
                    <KV k={t('nName')} v={num(su?.nitrogen_mg_per_kg, ' mg/kg', 0)} />
                    <KV k={t('pName')} v={su?.phosphorus_mg_per_kg != null ? `${num(su.phosphorus_mg_per_kg, ' mg/kg', 0)} (${t('estimate')})` : '—'} />
                    <KV k={t('kName')} v={su?.potassium_mg_per_kg != null ? `${num(su.potassium_mg_per_kg, ' mg/kg', 0)} (${t('estimate')})` : '—'} />
                    <KV k={t('ocName')} v={num(su?.organic_carbon_pct ?? soil?.organic_carbon_pct, '%', 1)} />
                    <KV k={t('source')} v={sourceName(t, su?.chemistry_source ?? soil?.source)} />
                  </>
                ) : undefined}
              >
                {su || soil ? (
                  <>
                    {/* Primary: farmer-friendly health label */}
                    <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.sm }}>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 22, fontWeight: '800', color: soilHealthColor(ph) }}>{soilHealthLabel(t, ph)}</Text>
                        <Text style={{ fontSize: 14, color: C.muted, marginTop: 2 }}>{`${t('phName')} ${num(ph, '', 1)}`}</Text>
                      </View>
                    </View>
                    <SegmentedMeter value={ph ?? null} min={4} max={9} segments={[[0.4, '#E9A64F'], [0.36, '#6FB26A'], [0.24, '#6FA8D8']]} />
                    {moist != null ? (
                      <>
                        <View style={{ flexDirection: 'row', marginTop: S.lg }}>
                          <Text style={{ flex: 1, fontSize: 15, fontWeight: '700', color: C.text }}>{t('moistName')}</Text>
                          <Text style={{ fontSize: 15, fontWeight: '800', color: C.text }}>{num(moist, '%', 0)}</Text>
                        </View>
                        <View style={{ height: 12, borderRadius: 6, backgroundColor: '#E4EBE0', marginTop: 6, overflow: 'hidden' }}>
                          <View style={{ width: `${Math.max(3, Math.min(100, moist))}%`, height: 12, borderRadius: 6, backgroundColor: '#5B9BD1' }} />
                        </View>
                        {su?.moisture_pct != null ? <Text style={{ fontSize: 12.5, color: C.muted, marginTop: 4 }}>{t('estimate')}</Text> : null}
                      </>
                    ) : null}
                  </>
                ) : <Muted>{t('noData')}</Muted>}
              </Block>

              {/* Crop greenness — farmer-friendly primary */}
              <Block
                title={t('ndviName')} icon="leaf"
                details={ndvi ? (
                  <>
                    <KV k="NDVI" v={num(ndvi.ndvi, '', 2)} />
                    <KV k={t('howOld')} v={fmtDate(ndvi.observed_at, true)} />
                    <KV k={t('cloud')} v={num(ndvi.cloud_cover_pct, '%', 0)} />
                    <KV k={t('source')} v={sourceName(t, ndvi.source)} />
                  </>
                ) : undefined}
              >
                {ndvi ? (
                  <>
                    <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.sm }}>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 22, fontWeight: '800', color: ndviHealthColor(ndvi.ndvi) }}>{ndviHealthLabel(t, ndvi.ndvi)}</Text>
                        <Text style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>{`${t('ndviAge')} ${fmtDate(ndvi.observed_at, true)}`}</Text>
                      </View>
                    </View>
                    <SegmentedMeter value={ndvi.ndvi} min={0} max={1} segments={[[0.3, '#D9776B'], [0.3, '#E9C24F'], [0.4, '#5FAE62']]} />
                  </>
                ) : <Muted>{t('ndviGathering')}</Muted>}
              </Block>
            </>
          ) : (
            /* Farmer-Centric History Sub-Tab */
            <FarmerHistoryView d={d} />
          )}
        </ScrollView>
      )}
    </View>
  );
}

function FarmerHistoryView({ d }: { d: DataSummary | null }) {
  const { t } = useApp();
  const [filter, setFilter] = useState<'all' | 'rain' | 'ndvi'>('all');

  if (!d) return null;

  const recent = d.weather.recent || [];
  const ndviHistory = d.ndvi.history || [];

  // Summary statistics for recent cycle
  const totalRain = recent.reduce((sum, w) => sum + (w.rainfall_mm || 0), 0);
  const maxTemp = recent.length ? Math.max(...recent.map((w) => w.temp_max_c ?? w.temp_c)) : null;
  const minTemp = recent.length ? Math.min(...recent.map((w) => w.temp_min_c ?? w.temp_c)) : null;

  // NDVI vigor trend
  const latestNdvi = ndviHistory.length ? ndviHistory[ndviHistory.length - 1].ndvi : null;

  const reversedRecent = [...recent].reverse();
  const filteredRecent = filter === 'rain'
    ? reversedRecent.filter((w) => (w.rainfall_mm || 0) >= 0.5)
    : reversedRecent;

  return (
    <View style={{ gap: S.md }}>
      {/* 1. Agronomic Weekly Snapshot */}
      <View style={{
        backgroundColor: '#FFFFFF',
        borderRadius: 20,
        padding: S.lg,
        borderWidth: 1,
        borderColor: '#E2DEC8',
        shadowColor: '#000',
        shadowOpacity: 0.05,
        shadowRadius: 6,
        elevation: 2,
      }}>
        <Text style={{ fontSize: 13, fontWeight: '800', letterSpacing: 0.8, color: C.accent, textTransform: 'uppercase', marginBottom: S.xs }}>
          Field Summary (Recent Cycle)
        </Text>
        <Text style={{ fontSize: 18, fontWeight: '800', color: C.text, marginBottom: S.md }}>
          What happened in your field
        </Text>

        <View style={{ flexDirection: 'row', gap: S.sm }}>
          <View style={{ flex: 1, backgroundColor: '#EBF5FB', borderRadius: 14, padding: S.sm, alignItems: 'center' }}>
            <Icon name="drop" size={20} color="#2980B9" />
            <Text style={{ fontSize: 18, fontWeight: '800', color: '#1B4F72', marginTop: 4 }}>
              {Math.round(totalRain * 10) / 10} mm
            </Text>
            <Text style={{ fontSize: 11, color: '#5499C7', fontWeight: '600', textAlign: 'center' }}>
              Total Rainfall
            </Text>
          </View>

          <View style={{ flex: 1, backgroundColor: '#FEF9E7', borderRadius: 14, padding: S.sm, alignItems: 'center' }}>
            <Icon name="thermo" size={20} color="#D4AC0D" />
            <Text style={{ fontSize: 18, fontWeight: '800', color: '#7D6608', marginTop: 4 }}>
              {minTemp !== null && maxTemp !== null ? `${Math.round(minTemp)}°–${Math.round(maxTemp)}°` : '—'}
            </Text>
            <Text style={{ fontSize: 11, color: '#B7950B', fontWeight: '600', textAlign: 'center' }}>
              Temp Range
            </Text>
          </View>

          <View style={{ flex: 1, backgroundColor: '#EAFAF1', borderRadius: 14, padding: S.sm, alignItems: 'center' }}>
            <Icon name="leaf" size={20} color="#27AE60" />
            <Text style={{ fontSize: 18, fontWeight: '800', color: '#145A32', marginTop: 4 }}>
              {latestNdvi !== null ? (latestNdvi >= 0.5 ? 'Good' : 'Fair') : '—'}
            </Text>
            <Text style={{ fontSize: 11, color: '#52BE80', fontWeight: '600', textAlign: 'center' }}>
              Crop Vigor
            </Text>
          </View>
        </View>

        {/* Practical takeaway */}
        <View style={{ marginTop: S.md, paddingTop: S.sm, borderTopWidth: 1, borderTopColor: '#F0ECE0', flexDirection: 'row', alignItems: 'center', gap: S.sm }}>
          <Icon name="info" size={16} color={C.accent} />
          <Text style={{ flex: 1, fontSize: 13, color: C.muted, lineHeight: 18 }}>
            {totalRain >= 15
              ? 'Soil moisture is well recharged. Irrigation needs were naturally reduced.'
              : totalRain > 0
              ? 'Light showers received. Regular monitoring of crop water balance advised.'
              : 'Dry period across this cycle. Follow recommended irrigation depths.'}
          </Text>
        </View>
      </View>

      {/* 2. Filter Pills */}
      <View style={{ flexDirection: 'row', gap: S.xs, marginTop: S.xs }}>
        {[
          { id: 'all', label: 'All Days' },
          { id: 'rain', label: 'Rain Events' },
          { id: 'ndvi', label: 'Satellite Vigor' },
        ].map((btn) => (
          <TouchableOpacity
            key={btn.id}
            onPress={() => setFilter(btn.id as any)}
            style={{
              paddingHorizontal: 12,
              paddingVertical: 6,
              borderRadius: 14,
              backgroundColor: filter === btn.id ? C.accent : '#FFFFFF',
              borderWidth: 1,
              borderColor: filter === btn.id ? C.accent : '#DCE2D6',
            }}
          >
            <Text style={{ fontSize: 12, fontWeight: '700', color: filter === btn.id ? '#FFFFFF' : C.text }}>
              {btn.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* 3. Timeline Items */}
      {filter === 'ndvi' ? (
        <View style={{ gap: S.sm }}>
          {ndviHistory.length ? (
            [...ndviHistory].reverse().map((n, idx) => (
              <View key={idx} style={{
                backgroundColor: '#FFFFFF',
                borderRadius: 16,
                padding: S.md,
                borderWidth: 1,
                borderColor: '#E2DEC8',
              }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: C.text }}>{fmtDate(n.observed_at, true)}</Text>
                  <View style={{ backgroundColor: ndviHealthColor(n.ndvi), paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 }}>
                    <Text style={{ color: '#fff', fontSize: 11, fontWeight: '700' }}>{ndviHealthLabel(t, n.ndvi)}</Text>
                  </View>
                </View>
                <Text style={{ fontSize: 13, color: C.muted }}>
                  Satellite NDVI score: <Text style={{ fontWeight: '700', color: C.text }}>{Math.round(n.ndvi * 100) / 100}</Text>
                  {n.cloud_cover_pct !== null && n.cloud_cover_pct !== undefined ? ` · Cloud: ${Math.round(n.cloud_cover_pct)}%` : ''}
                </Text>
              </View>
            ))
          ) : (
            <View style={{ padding: S.lg, backgroundColor: '#fff', borderRadius: 16, alignItems: 'center' }}>
              <Muted>{t('noData')}</Muted>
            </View>
          )}
        </View>
      ) : (
        <View style={{ gap: S.sm }}>
          {filteredRecent.length ? (
            filteredRecent.map((w, idx) => {
              const rain = w.rainfall_mm ?? 0;
              const hasRain = rain >= 0.5;
              const isHot = (w.temp_max_c ?? w.temp_c) >= 36;
              return (
                <View key={idx} style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: 16,
                  padding: S.md,
                  borderWidth: 1,
                  borderColor: '#E2DEC8',
                  borderLeftWidth: 4,
                  borderLeftColor: hasRain ? '#2980B9' : isHot ? '#E67E22' : '#27AE60',
                }}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: C.text }}>
                      {fmtDate(w.observed_at)}
                    </Text>
                    <View style={{
                      backgroundColor: hasRain ? '#EBF5FB' : isHot ? '#FEF5E7' : '#EAFAF1',
                      paddingHorizontal: 8,
                      paddingVertical: 2,
                      borderRadius: 10,
                    }}>
                      <Text style={{
                        fontSize: 11,
                        fontWeight: '700',
                        color: hasRain ? '#1B4F72' : isHot ? '#935116' : '#145A32',
                      }}>
                        {hasRain ? `Rain: ${Math.round(rain * 10) / 10} mm` : isHot ? 'Heat Alert' : 'Normal Conditions'}
                      </Text>
                    </View>
                  </View>

                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: S.sm, marginTop: 4 }}>
                    <Text style={{ fontSize: 13, color: C.muted }}>
                      🌡️ Temp: <Text style={{ fontWeight: '700', color: C.text }}>{`${num(w.temp_min_c, '°', 0)} – ${num(w.temp_max_c ?? w.temp_c, '°', 0)}`}</Text>
                    </Text>
                    {w.humidity_pct !== null && w.humidity_pct !== undefined ? (
                      <Text style={{ fontSize: 13, color: C.muted }}>
                        💧 Humidity: <Text style={{ fontWeight: '700', color: C.text }}>{`${Math.round(w.humidity_pct)}%`}</Text>
                      </Text>
                    ) : null}
                    {w.wind_mps !== null && w.wind_mps !== undefined ? (
                      <Text style={{ fontSize: 13, color: C.muted }}>
                        💨 Wind: <Text style={{ fontWeight: '700', color: C.text }}>{`${Math.round(w.wind_mps * 3.6)} km/h`}</Text>
                      </Text>
                    ) : null}
                  </View>

                  <Text style={{ fontSize: 12, color: '#7D735B', marginTop: 8, fontStyle: 'italic' }}>
                    {hasRain
                      ? 'Rainfall contributed to soil water. Evaporative demand satisfied.'
                      : isHot
                      ? 'Elevated evaporative demand. Ensure soil moisture is checked.'
                      : 'Moderate weather. Crop transpiring normally.'}
                  </Text>
                </View>
              );
            })
          ) : (
            <View style={{ padding: S.lg, backgroundColor: '#fff', borderRadius: 16, alignItems: 'center' }}>
              <Muted>{t('noData')}</Muted>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

function FurrowBackdrop() {
  const { width: w, height: h } = useWindowDimensions();
  const rows = Array.from({ length: 16 }, (_, k) => k);
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: w, height: h }}>
      <Svg width={w} height={h}>
        <Defs>
          <LinearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#F6F2E2" />
            <Stop offset="1" stopColor="#E7EFD8" />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width={w} height={h} fill="url(#bg)" />
        {rows.map((k) => {
          const y = h * 0.28 + k * (h * 0.05);
          return <Path key={k} d={`M0 ${y} C ${w * 0.3} ${y - 16 - k} ${w * 0.65} ${y + 16 + k} ${w} ${y - 6}`} stroke="#6FAE5F" strokeOpacity={0.09 + k * 0.006} strokeWidth={1.4 + k * 0.15} fill="none" />;
        })}
      </Svg>
    </View>
  );
}

function Glyph({ kind, size = 30 }: { kind: 'rain' | 'cloud' | 'clear'; size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 32 32">
      {kind === 'clear' ? (
        <>
          <Circle cx="16" cy="16" r="6.5" fill="#FFC93C" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <Path key={a} d="M16 3.5 v3.2" stroke="#FFC93C" strokeWidth="2.2" strokeLinecap="round" transform={`rotate(${a} 16 16)`} />
          ))}
        </>
      ) : (
        <>
          <Path d="M9 22 a5.5 5.5 0 0 1 1 -10.9 a7 7 0 0 1 13.4 1.8 a4.6 4.6 0 0 1 -0.9 9.1 Z" fill="#B8C6D6" />
          {kind === 'rain' ? [11, 17, 23].map((x) => <Path key={x} d={`M${x} 24 l-1.6 4`} stroke="#4C8FCB" strokeWidth="2.2" strokeLinecap="round" />) : null}
        </>
      )}
    </Svg>
  );
}

function Fact({ icon, value, unit, label, tint }: { icon: IconName; value: string; unit?: string; label: string; tint: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: '#fff', borderRadius: 18, padding: S.md, borderWidth: 1, borderColor: '#E3E8DC', shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 8, shadowOffset: { width: 0, height: 3 }, elevation: 3 }}>
      <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: tint, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={icon} size={16} color={C.accent} />
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', marginTop: 6 }}>
        <Text style={{ fontSize: 20, fontWeight: '800', color: C.text }} numberOfLines={1}>{value}</Text>
        {unit ? <Text style={{ fontSize: 11.5, color: C.muted, marginLeft: 2 }}>{unit}</Text> : null}
      </View>
      <Text style={{ fontSize: 12.5, color: C.muted }} numberOfLines={1}>{label}</Text>
    </View>
  );
}

function Block({ icon, title, children, details }: { icon: IconName; title: string; children: React.ReactNode; details?: React.ReactNode }) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  return (
    <View style={{ backgroundColor: 'rgba(255,255,255,0.95)', borderRadius: 22, padding: S.lg, marginTop: S.lg, borderWidth: 1, borderColor: '#E3E8DC' }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#E8F3E8', alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
          <Icon name={icon} size={20} color={C.accent} />
        </View>
        <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: C.text }}>{title}</Text>
      </View>
      {children}
      {details ? (
        <View style={{ marginTop: S.md, borderTopWidth: 1, borderTopColor: C.border, paddingTop: S.sm }}>
          <TouchableOpacity onPress={() => setOpen(!open)} style={{ flexDirection: 'row', alignItems: 'center', minHeight: 40 }}>
            <Text style={{ color: C.accent, fontWeight: '700', flex: 1 }}>{open ? t('hideAllData') : t('showAllData')}</Text>
            <Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} color={C.accent} />
          </TouchableOpacity>
          {open ? <View style={{ marginTop: S.sm }}>{details}</View> : null}
        </View>
      ) : null}
    </View>
  );
}
