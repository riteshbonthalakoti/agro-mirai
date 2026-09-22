import React, { useState } from 'react';
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { getDiseaseRisk, getIrrigation, getRecommendation } from '../api';
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
  const crop = useLoad(id ? `rec:${id}` : null, () => getRecommendation(id!), [id]);
  const irr = useLoad(id ? `irr:${id}` : null, () => getIrrigation(id!), [id]);
  const dis = useLoad(id ? `dis:${id}:${lang}` : null, () => getDiseaseRisk(id!, lang), [id, lang]);

  const reloadAll = () => { crop.reload(); irr.reload(); dis.reload(); };
  const busy = crop.loading || irr.loading || dis.loading;
  const c = crop.data;
  const i = irr.data;
  const d = dis.data?.[0];
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
      <Card title={t('cropRec')}>
        {c ? (
          <>
            <Text style={{ fontSize: 24, fontWeight: '700', color: C.text }}>{cropLabel(lang, c.recommended_crop)}</Text>
            {c.alternatives && c.alternatives.length ? (
              <KV k={t('alternatives')} v={c.alternatives.map((a) => cropLabel(lang, a)).join(', ')} />
            ) : null}
            {c.out_of_region ? (
              <Banner
                text={`${t('notInRegion')}${c.regional_alternative ? ` ${t('commonInRegion')}: ${cropLabel(lang, c.regional_alternative)}` : ''}`}
              />
            ) : null}
            <Why text={c.rationale_plain || c.rationale} />
          </>
        ) : crop.loading ? <Muted>{t('loading')}</Muted> : !crop.error ? <Muted>{t('notComputed')}</Muted> : null}
        <ErrorBox load={crop} />
      </Card>

      <Card title={t('irrigation')} right={i ? <Badge label={levelLabel(t, i.urgency)} color={levelColor(i.urgency)} /> : undefined}>
        {i ? (
          <>
            <Text style={{ fontSize: 24, fontWeight: '700', color: C.text }}>{`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`}</Text>
            <KV k={t('window')} v={`${fmtDate(i.window_start_at)} – ${fmtDate(i.window_end_at)}`} />
            <Why text={i.rationale_plain || i.rationale} />
          </>
        ) : irr.loading ? <Muted>{t('loading')}</Muted> : !irr.error ? <Muted>{t('notComputed')}</Muted> : null}
        <ErrorBox load={irr} />
      </Card>

      <Card title={t('diseaseRisk')} right={d ? <Badge label={levelLabel(t, d.risk_level)} color={levelColor(d.risk_level)} /> : undefined}>
        {d ? (
          <>
            <Text style={{ fontSize: 16, fontWeight: '600', color: C.text }}>{d.disease_translated || d.disease}</Text>
            <Text style={[st.body, { marginTop: S.sm }]}>{diseaseAction(t, d.risk_level, d.recommended_action)}</Text>
          </>
        ) : dis.loading ? <Muted>{t('loading')}</Muted> : !dis.error ? <Muted>{t('notComputed')}</Muted> : null}
        <ErrorBox load={dis} />
      </Card>

      <Muted>{t('pullToRefresh')}</Muted>
    </ScrollView>
  );
}
