import React, { useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { AuthBackdrop } from '../components/AuthBackdrop';
import { Icon, IconName } from '../../icons';
import { getDiseaseRiskFull, getIrrigation, getRecommendation, Irrigation, DiseaseAlert, DiseaseDetails } from '../api';
import { cropLabel, diseaseAction, fmtDate, levelLabel, useApp } from '../ctx';
import { errorText, Load, useLoad, useTranslated } from '../hooks';
import { feedback } from '../feedback';
import { useNotifications } from '../notifications';
import { SkeletonCard } from '../skeleton';
import { C, levelColor, S } from '../theme';
import { Badge, Banner, Btn, KV, Muted, st } from '../ui';

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

/** White rounded section with a coloured icon badge, replacing the plain Card on Home. */
function Section({ icon, tint, title, right, children }: { icon: IconName; tint: string; title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <View style={{ backgroundColor: 'rgba(255,255,255,0.94)', borderRadius: 22, padding: S.lg, marginBottom: S.md, borderWidth: 1, borderColor: '#E3E8DC' }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
        <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: tint, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
          <Icon name={icon} size={22} color={C.accent} />
        </View>
        <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: C.text }}>{title}</Text>
        {right}
      </View>
      {children}
    </View>
  );
}

function Tile({ icon, tint, value, label }: { icon: IconName; tint: string; value: string; label: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: 'rgba(255,255,255,0.94)', borderRadius: 18, padding: S.md, borderWidth: 1, borderColor: '#E3E8DC' }}>
      <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: tint, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={icon} size={18} color={C.accent} />
      </View>
      <Text style={{ fontSize: 22, fontWeight: '800', color: C.text, marginTop: S.sm }} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
      <Text style={{ fontSize: 12.5, lineHeight: 16, color: C.muted, marginTop: 2 }} numberOfLines={2}>{label}</Text>
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
  const { setDailyReminder } = useNotifications();
  useEffect(() => {
    // tomorrow's 7:00 notification carries the latest advice, even if the app is closed by then
    if (today?.text) setDailyReminder(t('notifDailyTitle'), today.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [today?.text, lang]);
  // the server's crop-specific advice is English: translate it (cached), fall back to the generic line
  const diseaseAdvice = useTranslated([d?.recommended_action], lang);
  const firstLoad = busy && !c && !i && !d;

  if (firstLoad) {
    return (
      <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
        <SkeletonCard /><SkeletonCard /><SkeletonCard />
      </ScrollView>
    );
  }

  const first = (farmer?.name || '').split(' ')[0];
  const heroIcon: IconName = !today ? 'leaf' : today.color === C.accent ? 'check' : i && i.urgency !== 'low' && today.text === t('todayWaterNow').replace('{mm}', String(Math.round(i.recommended_depth_mm))) ? 'drop' : 'alert';
  const rain = i?.details && typeof i.details.rain_forecast_7d_mm === 'number' ? `${Math.round(i.details.rain_forecast_7d_mm)} ${t('mm')}` : '–';
  const used = i?.details && typeof i.details.soil_water_used_pct === 'number' ? `${Math.min(i.details.soil_water_used_pct, 100)}%` : '–';

  return (
    <View style={{ flex: 1, backgroundColor: '#F3F0E3' }}>
      <AuthBackdrop />
      <ScrollView
        contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: S.xl * 2 }}
        refreshControl={<RefreshControl refreshing={busy} onRefresh={reloadAll} />}
      >
        {/* greeting + today's one clear thing to do */}
        <Text style={{ fontSize: 15, color: C.muted, fontWeight: '600' }}>{`${t(greetKey())}${first ? `, ${first}` : ''}`}</Text>
        <Text style={{ fontSize: 26, fontWeight: '800', color: C.text, marginTop: 2 }} numberOfLines={1}>
          {field?.name}{field?.current_crop ? ` · ${cropLabel(lang, field.current_crop)}` : ''}
        </Text>

        {today ? (
          <View style={{ marginTop: S.md, borderRadius: 26, padding: S.lg, backgroundColor: today.color, overflow: 'hidden' }}>
            <View style={{ position: 'absolute', right: -30, top: -30, width: 150, height: 150, borderRadius: 75, backgroundColor: 'rgba(255,255,255,0.14)' }} />
            <View style={{ position: 'absolute', right: 40, bottom: -50, width: 110, height: 110, borderRadius: 55, backgroundColor: 'rgba(255,255,255,0.10)' }} />
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.25)', alignItems: 'center', justifyContent: 'center' }}>
                <Icon name={heroIcon} size={24} color="#fff" />
              </View>
              <Text style={{ marginLeft: S.md, fontSize: 14, fontWeight: '800', letterSpacing: 1, color: 'rgba(255,255,255,0.9)' }}>{t('todayTitle').toUpperCase()}</Text>
            </View>
            <Text style={{ fontSize: 24, lineHeight: 31, fontWeight: '800', color: '#fff', marginTop: S.md }}>{today.text}</Text>
          </View>
        ) : null}

        {/* three numbers at a glance */}
        {i ? (
          <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.md }}>
            <Tile icon="drop" tint="#E3F1FA" value={`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`} label={t('tileWater')} />
            <Tile icon="thermo" tint="#E8F3E8" value={rain} label={t('tileRain')} />
            <Tile icon="field" tint="#F6ECD6" value={used} label={t('tileSoil')} />
          </View>
        ) : null}

        <View style={{ height: S.md }} />

        <Section icon="sprout" tint="#E8F3E8" title={t('cropRec')}>
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

        <Section icon="drop" tint="#E3F1FA" title={t('irrigation')} right={i ? <Badge label={levelLabel(t, i.urgency)} color={levelColor(i.urgency)} /> : undefined}>
          {i ? (
            <>
              <Text style={{ fontSize: 26, fontWeight: '800', color: C.text }}>{`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`}</Text>
              <KV k={t('window')} v={`${fmtDate(i.window_start_at)} – ${fmtDate(i.window_end_at)}`} />
              {i.details?.method === 'soil_water_balance' && typeof i.details.soil_water_used_pct === 'number' ? (
                <>
                  <KV k={t('soilWaterUsed')} v={`${Math.min(i.details.soil_water_used_pct, 100)}%`} />
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

        <Section icon="blight" tint="#FDF0DC" title={t('diseaseRisk')} right={d ? <Badge label={levelLabel(t, d.risk_level)} color={levelColor(d.risk_level)} /> : undefined}>
          {d ? (
            <>
              <Text style={{ fontSize: 18, fontWeight: '700', color: C.text }}>{d.disease_translated || d.disease}</Text>
              {dd?.trend === 'rising' ? <Badge label={t('riskRising')} color={levelColor('high')} /> : null}
              <Text style={[st.body, { marginTop: S.sm }]}>{diseaseAdvice.out[0] || diseaseAction(t, d.risk_level, d.recommended_action)}</Text>
            </>
          ) : dis.loading ? <Muted>{t('loading')}</Muted> : !dis.error ? <Muted>{t('notComputed')}</Muted> : null}
          <ErrorBox load={dis} />
        </Section>

        <Muted style={{ textAlign: 'center' }}>{t('pullToRefresh')}</Muted>
      </ScrollView>
    </View>
  );
}
