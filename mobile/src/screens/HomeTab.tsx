import React, { useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { getDiseaseRiskFull, getIrrigation, getRecommendation, Irrigation, DiseaseAlert, DiseaseDetails } from '../api';
import { cropLabel, diseaseAction, fmtDate, levelLabel, useApp } from '../ctx';
import { errorText, Load, useLoad, useTranslated } from '../hooks';
import { SkeletonCard } from '../skeleton';
import { C, levelColor, S } from '../theme';
import { Badge, Banner, Btn, Card, KV, Muted, st } from '../ui';

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

export function HomeTab() {
  const { field, t, lang } = useApp();
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
  const firstLoad = busy && !c && !i && !d;

  if (firstLoad) {
    return (
      <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
        <SkeletonCard /><SkeletonCard /><SkeletonCard />
      </ScrollView>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={reloadAll} />}
    >
      {today ? (
        <Card title={t('todayTitle')}>
          <Text style={{ fontSize: 18, fontWeight: '700', color: today.color }}>{today.text}</Text>
        </Card>
      ) : null}

      <Card title={t('cropRec')}>
        {c ? (
          <>
            <Text style={{ fontSize: 24, fontWeight: '700', color: C.text }}>{cropLabel(lang, c.recommended_crop)}</Text>
            {c.details?.ranking?.[0] ? (
              <KV k={t('modelConfidence')} v={`${Math.round(c.confidence * 100)}% · ${t(c.details.ranking[0].fit === 'good' ? 'fitGood' : c.details.ranking[0].fit === 'fair' ? 'fitFair' : 'fitWeak')}`} />
            ) : typeof c.confidence === 'number' ? <KV k={t('modelConfidence')} v={`${Math.round(c.confidence * 100)}%`} /> : null}
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
              <TouchableOpacity onPress={() => setKeep(!keep)} style={{ marginTop: S.sm, paddingVertical: S.sm }}>
                <Text style={{ color: C.accent, fontWeight: '600' }}>{`${keep ? '☑' : '☐'} ${t('keepCurrent')}`}</Text>
              </TouchableOpacity>
            ) : null}
          </>
        ) : crop.loading ? <Muted>{t('loading')}</Muted> : !crop.error ? <Muted>{t('notComputed')}</Muted> : null}
        <ErrorBox load={crop} />
      </Card>

      <Card title={t('irrigation')} right={i ? <Badge label={levelLabel(t, i.urgency)} color={levelColor(i.urgency)} /> : undefined}>
        {i ? (
          <>
            <Text style={{ fontSize: 24, fontWeight: '700', color: C.text }}>{`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`}</Text>
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
      </Card>

      <Card title={t('diseaseRisk')} right={d ? <Badge label={levelLabel(t, d.risk_level)} color={levelColor(d.risk_level)} /> : undefined}>
        {d ? (
          <>
            <Text style={{ fontSize: 16, fontWeight: '600', color: C.text }}>{d.disease_translated || d.disease}</Text>
            {dd?.trend === 'rising' ? <Badge label={t('riskRising')} color={levelColor('high')} /> : null}
            <Text style={[st.body, { marginTop: S.sm }]}>{diseaseAction(t, d.risk_level, d.recommended_action)}</Text>
          </>
        ) : dis.loading ? <Muted>{t('loading')}</Muted> : !dis.error ? <Muted>{t('notComputed')}</Muted> : null}
        <ErrorBox load={dis} />
      </Card>

      <Muted>{t('pullToRefresh')}</Muted>
    </ScrollView>
  );
}
