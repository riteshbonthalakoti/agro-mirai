import React, { useEffect, useState } from 'react';
import { Animated, Easing, RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { AuthBackdrop } from '../components/AuthBackdrop';
import { BarMeter, SegmentedMeter } from '../components/Charts';
import { Icon, IconName } from '../../icons';
import { getDiseaseRiskFull, getIrrigation, getRecommendation, Irrigation, DiseaseAlert, DiseaseDetails } from '../api';
import { cropLabel, diseaseAction, fmtDate, levelLabel, useApp } from '../ctx';
import { errorText, Load, useLoad, useTranslated } from '../hooks';
import { feedback } from '../feedback';
import { useNotifications } from '../notifications';
import { getReminderSettings } from '../reminderSettings';
import { SkeletonCard } from '../skeleton';
import { C, H, levelColor, S } from '../theme';
import { Badge, Banner, Btn, KV, LastUpdated, Muted, st } from '../ui';

function ErrorBox({ load }: { load: Load<unknown> }) {
  const { t } = useApp();
  if (!load.error) return null;
  return (
    <>
      <Banner text={errorText(t, load.error)} kind="error" />
      <Btn label={t('retry')} kind="secondary" onPress={load.reload} />
    </>
  );
}

/** One clear thing to do today, worked out from the irrigation and disease answers
 *  that are already on this screen (no extra request). */
function todayLine(
  t: (k: any) => string,
  i?: Irrigation | null,
  d?: DiseaseAlert | null,
  dd?: DiseaseDetails | null,
): { text: string; color: string } | null {
  if (!i && !d) return null;
  const det = i?.details;
  if (i && det?.waiting_for_rain) return { text: t('todayWaitRain'), color: C.accent };
  if (i && i.urgency === 'high') {
    return { text: t('todayWaterNow').replace('{mm}', String(Math.round(i.recommended_depth_mm))), color: levelColor('high') };
  }
  if (d && (d.risk_level === 'high' || d.risk_level === 'severe')) {
    return { text: t('todayCheckLeaves'), color: levelColor(d.risk_level) };
  }
  if (i && i.urgency === 'moderate') {
    const n = det?.days_until_water ?? 3;
    return { text: t('todayWaterSoon').replace('{n}', String(n)), color: levelColor('moderate') };
  }
  return { text: t('todayAllGood'), color: C.accent };
}

function Why({ text }: { text?: string | null }) {
  const { t, lang } = useApp();
  const [open, setOpen] = useState(false);
  // Only translate once the farmer opens it (each translation is a server call).
  const { out, state } = useTranslated([open ? text : ''], lang);
  if (!text) return null;
  return (
    <View style={{ marginTop: S.sm }}>
      <TouchableOpacity onPress={() => setOpen(!open)}>
        <Text style={{ color: C.accent, fontWeight: '600' }}>{open ? t('hide') : t('whyThis')}</Text>
      </TouchableOpacity>
      {open ? (
        <View style={{ marginTop: S.sm }}>
          <Text style={st.body}>{out[0] || text}</Text>
          {state === 'loading' ? <Muted style={{ marginTop: 4 }}>{t('translating')}</Muted> : null}
          {state === 'failed' ? <Muted style={{ marginTop: 4 }}>{t('translateFailed')}</Muted> : null}
        </View>
      ) : null}
    </View>
  );
}

function HeroHeader({ name, crop, greeting, fadeAnim }: {
  name: string; crop: string | null; greeting: string; fadeAnim: Animated.Value;
}) {
  return (
    <Animated.View style={{ opacity: fadeAnim, backgroundColor: H.heroBg, borderRadius: 28, overflow: 'hidden', marginBottom: S.md }}>
      <View style={{ position: 'absolute', right: -40, top: -40, width: 180, height: 180, borderRadius: 90, backgroundColor: 'rgba(255,255,255,0.06)' }} />
      <View style={{ position: 'absolute', left: -20, bottom: -30, width: 130, height: 130, borderRadius: 65, backgroundColor: 'rgba(255,255,255,0.04)' }} />
      <View style={{ padding: S.xl, paddingBottom: S.lg }}>
        <Text style={{ fontSize: 13, fontWeight: '600', letterSpacing: 0.8, color: H.heroMuted, textTransform: 'uppercase' }}>{greeting}</Text>
        <Text style={{ fontSize: 28, fontWeight: '900', color: H.heroText, marginTop: 4, letterSpacing: -0.5 }} numberOfLines={1} adjustsFontSizeToFit>{name || '—'}</Text>
        {crop ? (
          <View style={{ marginTop: S.sm, alignSelf: 'flex-start', backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 20, paddingHorizontal: S.md, paddingVertical: 4 }}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: H.heroAccent }}>{crop}</Text>
          </View>
        ) : null}
      </View>
    </Animated.View>
  );
}

function Section({ icon, tint, title, stripe, right, children }: {
  icon: IconName; tint: string; title: string; stripe: string; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <View style={{ backgroundColor: '#FFFFFF', borderRadius: 20, marginBottom: S.md, overflow: 'hidden', borderWidth: 1, borderColor: H.pillBorder }}>
      <View style={{ height: 4, backgroundColor: stripe }} />
      <View style={{ padding: S.lg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: tint, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
            <Icon name={icon} size={20} color={stripe} />
          </View>
          <Text style={{ flex: 1, fontSize: 16, fontWeight: '700', color: C.text, letterSpacing: 0.1 }}>{title}</Text>
          {right}
        </View>
        {children}
      </View>
    </View>
  );
}

// Color contrast verified: worst case #B3261E bg + white text = 8.5:1 (WCAG AAA)
function ActionBanner({ text, color, icon, pulseAnim }: {
  text: string; color: string; icon: IconName; pulseAnim: Animated.Value;
}) {
  const scale = pulseAnim.interpolate({ inputRange: [0, 1], outputRange: [1, 1.12] });
  return (
    <View style={{ borderRadius: 22, padding: S.lg, backgroundColor: color, overflow: 'hidden', marginBottom: S.md }}>
      <View style={{ position: 'absolute', right: -24, top: -24, width: 140, height: 140, borderRadius: 70, backgroundColor: 'rgba(255,255,255,0.12)' }} />
      <View style={{ position: 'absolute', right: 50, bottom: -44, width: 100, height: 100, borderRadius: 50, backgroundColor: 'rgba(255,255,255,0.08)' }} />
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
        <Animated.View style={{ transform: [{ scale }], width: 46, height: 46, borderRadius: 23, backgroundColor: 'rgba(255,255,255,0.28)', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={icon} size={24} color="#fff" />
        </Animated.View>
        <Text style={{ marginLeft: S.md, fontSize: 11, fontWeight: '800', letterSpacing: 1.2, color: 'rgba(255,255,255,0.85)', textTransform: 'uppercase' }}>Today</Text>
      </View>
      <Text style={{ fontSize: 22, lineHeight: 29, fontWeight: '800', color: '#fff' }}>{text}</Text>
    </View>
  );
}

/** Horizontal stat chip — distinct from DataTab's vertical KV rows */
function StatPill({ icon, value, label }: { icon: IconName; value: string; label: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: H.pillBg, borderRadius: 16, padding: S.md, borderWidth: 1, borderColor: H.pillBorder, alignItems: 'center' }}>
      <Icon name={icon} size={20} color={C.accent} />
      <Text style={{ fontSize: 20, fontWeight: '900', color: C.text, marginTop: 6, letterSpacing: -0.3 }} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
      <Text style={{ fontSize: 11, color: C.muted, marginTop: 2, textAlign: 'center', lineHeight: 14 }} numberOfLines={2}>{label}</Text>
    </View>
  );
}

const greetKey = () => {
  const h = new Date().getHours();
  return h >= 5 && h < 12 ? 'greetMorning' : h >= 12 && h < 17 ? 'greetAfternoon' : 'greetEvening';
};

export function HomeTab() {
  const { field, t, lang, farmer } = useApp();
  const id = field?.id;
  // "advise on my current crop" instead of proposing a switch (backend: ?keep_current=true)
  const [keep, setKeep] = useState(false);
  useEffect(() => { setKeep(false); }, [id]);
  const crop = useLoad(id ? `rec:${id}:${keep}` : null, () => getRecommendation(id!, keep), [id, keep]);
  const irr = useLoad(id ? `irr:${id}` : null, () => getIrrigation(id!), [id]);
  const dis = useLoad(id ? `dis:${id}:${lang}` : null, () => getDiseaseRiskFull(id!, lang), [id, lang]);

  const reloadAll = () => { crop.reload(); irr.reload(); dis.reload(); };
  const busy = crop.loading || irr.loading || dis.loading;
  const c = crop.data;
  const i = irr.data;
  const d = dis.data?.items?.[0];
  const dd = dis.data?.details;
  const today = todayLine(t, i, d, dd);

  const fadeAnim = React.useRef(new Animated.Value(0)).current;
  const pulseAnim = React.useRef(new Animated.Value(0)).current;

  useEffect(() => {
    fadeAnim.setValue(0);
    Animated.timing(fadeAnim, { toValue: 1, duration: 380, useNativeDriver: true }).start();
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 0, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { setDailyReminder } = useNotifications();
  useEffect(() => {
    // tomorrow's daily notification carries the latest advice, even if the app is closed by then
    if (today?.text) {
      (async () => {
        const settings = await getReminderSettings(farmer?.id);
        if (settings.enabled) {
          setDailyReminder(t('notifDailyTitle'), today.text, id, farmer?.id, settings.timeMinutes);
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [today?.text, lang, id]);
  // the server's crop-specific advice is English: translate it (cached), fall back to the generic line
  const diseaseAdvice = useTranslated([d?.recommended_action], lang);
  const firstLoad = busy && !c && !i && !d;

  if (firstLoad) {
    return (
      <View style={{ flex: 1, backgroundColor: H.bg }}>
        <AuthBackdrop />
        <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
          <View style={{ height: 140, backgroundColor: H.heroBg, borderRadius: 28, marginBottom: S.md }} />
          <SkeletonCard /><SkeletonCard /><SkeletonCard />
        </ScrollView>
      </View>
    );
  }

  const first = (farmer?.name || '').split(' ')[0];
  const heroIcon: IconName = !today ? 'leaf' : today.color === C.accent ? 'check' : i && i.urgency !== 'low' && today.text === t('todayWaterNow').replace('{mm}', String(Math.round(i.recommended_depth_mm))) ? 'drop' : 'alert';
  const rain = i?.details && typeof i.details.rain_forecast_7d_mm === 'number' ? `${Math.round(i.details.rain_forecast_7d_mm)} ${t('mm')}` : '–';
  const used = i?.details && typeof i.details.soil_water_used_pct === 'number' ? `${Math.min(i.details.soil_water_used_pct, 100)}%` : '–';

  return (
    <View style={{ flex: 1, backgroundColor: H.bg }}>
      <AuthBackdrop />
      <ScrollView
        contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: S.xl * 2 }}
        refreshControl={<RefreshControl refreshing={busy} onRefresh={reloadAll} />}
      >
        <HeroHeader
          name={field?.name ?? '—'}
          crop={field?.current_crop ? cropLabel(lang, field.current_crop) : null}
          greeting={`${t(greetKey())}${first ? `, ${first}` : ''}`}
          fadeAnim={fadeAnim}
        />

        {!field ? (
          <Muted style={{ textAlign: 'center', marginTop: S.md }}>{t('notComputed')}</Muted>
        ) : (
          <>
            {today ? (
              <Animated.View style={{ opacity: fadeAnim }}>
                <ActionBanner text={today.text} color={today.color} icon={heroIcon} pulseAnim={pulseAnim} />
              </Animated.View>
            ) : null}

            {i ? (
              <Animated.View style={{ opacity: fadeAnim, flexDirection: 'row', gap: S.sm, marginBottom: S.md }}>
                <StatPill icon="drop" value={`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`} label={t('tileWater')} />
                <StatPill icon="thermo" value={rain} label={t('tileRain')} />
                <StatPill icon="field" value={used} label={t('tileSoil')} />
              </Animated.View>
            ) : null}

            <Animated.View style={{ opacity: fadeAnim }}>

        <Section icon="sprout" tint="#E8F3E8" title={t('cropRec')} stripe={H.sectionStripe.crop}>
          <LastUpdated at={crop.lastUpdatedAt} stale={!!crop.error} t={t} />
          {c ? (
            <>
              <Text style={{ fontSize: 26, fontWeight: '800', color: C.text }}>{cropLabel(lang, c.recommended_crop)}</Text>
              {(() => {
                // the fit word must describe the crop shown: in "current crop" mode that is the crop already growing, not the top-ranked one
                const fit = c.details?.mode === 'keep_current' ? c.details.current_crop?.fit : c.details?.ranking?.[0]?.fit;
                if (typeof c.confidence !== 'number') return null;
                const word = fit ? ` · ${t(fit === 'good' ? 'fitGood' : fit === 'fair' ? 'fitFair' : 'fitWeak')}` : '';
                return <KV k={t('modelConfidence')} v={`${Math.round(c.confidence * 100)}%${word}`} />;
              })()}

              {/* Crop suitability scores visualization */}
              {c.details?.ranking && c.details.ranking.length > 1 && (
                <View style={{ marginTop: S.md }}>
                  <Text style={{ fontSize: 13, fontWeight: '600', color: C.muted, marginBottom: S.sm }}>{t('topCrops')}</Text>
                  {c.details.ranking.slice(0, 4).map((r, k) => (
                    <View key={k} style={{ marginBottom: S.sm }}>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text style={{ fontSize: 13, color: C.text }}>{cropLabel(lang, r.crop)}</Text>
                        <Text style={{ fontSize: 12, fontWeight: '600', color: C.muted }}>{Math.round(r.score * 100)}%</Text>
                      </View>
                      <BarMeter value={r.score} min={0} max={1} color={C.accent} showPercent={false} height={8} />
                    </View>
                  ))}
                </View>
              )}

              {c.alternatives && c.alternatives.length ? (
                <KV k={t('alternatives')} v={c.alternatives.map((a) => cropLabel(lang, a)).join(', ')} />
              ) : null}
              {c.out_of_region ? (
                <Banner
                  text={`${t('notInRegion')}${c.regional_alternative ? ` ${t('commonInRegion')}: ${cropLabel(lang, c.regional_alternative)}` : ''}`}
                />
              ) : null}
              <Why text={c.rationale_plain || c.rationale} />
              {field?.current_crop ? (
                <TouchableOpacity onPress={() => { feedback.select(); setKeep(!keep); }} style={{ marginTop: S.sm, paddingVertical: S.sm }}>
                  <Text style={{ color: C.accent, fontWeight: '600' }}>{`${keep ? '☑' : '☐'} ${t('keepCurrent')}`}</Text>
                </TouchableOpacity>
              ) : null}
            </>
          ) : crop.loading ? <Muted>{t('loading')}</Muted> : !crop.error ? <Muted>{t('notComputed')}</Muted> : null}
          <ErrorBox load={crop} />
        </Section>

        <Section icon="drop" tint="#E3F1FA" title={t('irrigation')} stripe={H.sectionStripe.irr} right={i ? <Badge label={levelLabel(t, i.urgency)} color={levelColor(i.urgency)} /> : undefined}>
          <LastUpdated at={irr.lastUpdatedAt} stale={!!irr.error} t={t} />
          {i ? (
            <>
              <Text style={{ fontSize: 26, fontWeight: '800', color: C.text }}>{`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`}</Text>
              <KV k={t('window')} v={`${fmtDate(i.window_start_at)} – ${fmtDate(i.window_end_at)}`} />

              {/* Water balance visualization */}
              {i.details?.method === 'soil_water_balance' && typeof i.details.soil_water_used_pct === 'number' ? (
                <>
                  <View style={{ marginTop: S.md }}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 }}>
                      <Text style={{ fontSize: 13, fontWeight: '600', color: C.text }}>{t('soilWaterUsed')}</Text>
                      <Text style={{ fontSize: 13, fontWeight: '600', color: C.text }}>{Math.min(i.details.soil_water_used_pct, 100)}%</Text>
                    </View>
                    <BarMeter value={i.details.soil_water_used_pct} min={0} max={100} color={levelColor(i.urgency)} showPercent={false} />
                  </View>
                  {typeof i.details.rain_forecast_7d_mm === 'number' ? (
                    <KV k={t('rainNext7')} v={`${Math.round(i.details.rain_forecast_7d_mm)} ${t('mm')}`} />
                  ) : null}
                </>
              ) : null}
              <Why text={i.rationale_plain || i.rationale} />
            </>
          ) : irr.loading ? <Muted>{t('loading')}</Muted> : !irr.error ? <Muted>{t('notComputed')}</Muted> : null}
          <ErrorBox load={irr} />
        </Section>

        <Section icon="blight" tint="#FDF0DC" title={t('diseaseRisk')} stripe={H.sectionStripe.dis} right={d ? <Badge label={levelLabel(t, d.risk_level)} color={levelColor(d.risk_level)} /> : undefined}>
          <LastUpdated at={dis.lastUpdatedAt} stale={!!dis.error} t={t} />
          {d ? (
            <>
              <Text style={{ fontSize: 18, fontWeight: '700', color: C.text }}>{d.disease_translated || d.disease}</Text>

              {/* Disease risk level visualization */}
              <View style={{ marginTop: S.md }}>
                <SegmentedMeter
                  value={d.risk_level === 'low' ? 1 : d.risk_level === 'moderate' ? 2 : d.risk_level === 'high' ? 3 : 4}
                  min={1}
                  max={4}
                  segments={[
                    [0.25, C.low],
                    [0.25, C.moderate],
                    [0.25, C.high],
                    [0.25, C.severe],
                  ]}
                  height={10}
                  markerHeight={20}
                />
              </View>

              {dd?.trend === 'rising' ? <Badge label={t('riskRising')} color={levelColor('high')} /> : null}
              <Text style={[st.body, { marginTop: S.sm }]}>{diseaseAdvice.out[0] || diseaseAction(t, d.risk_level, d.recommended_action)}</Text>
            </>
          ) : dis.loading ? <Muted>{t('loading')}</Muted> : !dis.error ? <Muted>{t('notComputed')}</Muted> : null}
          <ErrorBox load={dis} />
        </Section>

            </Animated.View>
          </>
        )}

        <Muted style={{ textAlign: 'center', marginTop: S.lg }}>{t('pullToRefresh')}</Muted>
      </ScrollView>
    </View>
  );
}
