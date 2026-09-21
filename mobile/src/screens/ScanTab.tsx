import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Image, ScrollView, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { File as ExpoFile } from 'expo-file-system';
import { ApiError, DiseaseAlert, getDiseaseRisk, scanLeaf } from '../api';
import { diseaseAction, fmtDate, levelLabel, useApp } from '../ctx';
import { cacheGet, cacheSet } from '../storage';
import { levelColor, S } from '../theme';
import { Badge, Banner, Btn, Card, Muted } from '../ui';
import { FieldPicker } from './HomeTab';

type HistoryItem = { id: string; date: string; disease: string; risk: string; source: string | null; confidence: number };

export function ScanTab() {
  const { field, t, lang } = useApp();
  const [uri, setUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DiseaseAlert | null>(null);
  const [err, setErr] = useState('');
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // History comes from the server (every photo scan is stored there), so it
  // survives reinstalling the app or switching phones. The device cache only
  // paints instantly / covers being offline.
  useEffect(() => {
    let alive = true;
    cacheGet<HistoryItem[]>('scans').then((h) => alive && h && setHistory(h));
    if (!field) return;
    getDiseaseRisk(field.id, lang)
      .then((items) => {
        if (!alive) return;
        const fromServer: HistoryItem[] = items
          .filter((a) => a.source === 'cnn')
          .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
          .slice(0, 30)
          .map((a) => ({
            id: a.id, date: a.created_at, disease: a.disease_translated || a.disease,
            risk: a.risk_level, source: a.source ?? null, confidence: a.confidence,
          }));
        setHistory(fromServer);
        cacheSet('scans', fromServer);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [field?.id, lang]);

  const analyze = async (imageUri: string) => {
    if (!field) return setErr(t('scanNeedsField'));
    setUri(imageUri);
    setResult(null);
    setErr('');
    setBusy(true);
    try {
      // Read the local file through expo-file-system's File (a Blob) instead
      // of fetch(file://): on Android fetch() can "succeed" with a 14-byte
      // "File not found" body that then uploads as the image (Module 34).
      const f = new ExpoFile(imageUri);
      if (!f.exists || !f.size) throw new ApiError(-1, t('scanErrorFile'));
      const r = await scanLeaf(field.id, f as unknown as Blob, lang);
      if (r.source !== 'cnn') {
        // The photo model was unreachable and the server answered with a
        // weather-based estimate. That says nothing about THIS leaf, so it is
        // not shown as a diagnosis and not added to scan history.
        setErr(t('scanUnavailable'));
        return;
      }
      setResult(r);
      const item: HistoryItem = {
        id: r.id, date: new Date().toISOString(), disease: r.disease_translated || r.disease,
        risk: r.risk_level, source: r.source ?? null, confidence: r.confidence,
      };
      const next = [item, ...history].slice(0, 30);
      setHistory(next);
      cacheSet('scans', next);
    } catch (e) {
      const ae = e as ApiError;
      setErr(
        ae.status === -1 ? ae.message
          : ae.isNetwork ? t('scanErrorNetwork')
          : ae.code === 'NOT_A_LEAF' ? t('scanNotLeaf')
          : ae.code === 'NO_WEATHER_DATA' ? t('noWeatherData')
          : `${t('scanErrorServer')}: ${ae.message}`,
      );
    } finally {
      setBusy(false);
    }
  };

  const camera = async () => {
    const p = await ImagePicker.requestCameraPermissionsAsync();
    if (!p.granted) return setErr(t('camPerm'));
    try {
      const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.8 });
      if (!r.canceled && r.assets?.[0]?.uri) await analyze(r.assets[0].uri);
    } catch {
      setErr(t('captureFailed'));
    }
  };

  const gallery = async () => {
    const p = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!p.granted) return setErr(t('galleryPerm'));
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!r.canceled && r.assets?.[0]?.uri) await analyze(r.assets[0].uri);
  };

  return (
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: 48 }}>
      <FieldPicker />
      <Card title={t('scanTitle')}>
        <Muted>{t('scanSub')}</Muted>
        <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.md }}>
          <Btn label={t('takePhoto')} onPress={camera} disabled={busy} style={{ flex: 1 }} />
          <Btn label={t('pickGallery')} kind="secondary" onPress={gallery} disabled={busy} style={{ flex: 1 }} />
        </View>
      </Card>

      {err ? <Banner text={err} kind="error" /> : null}
      {uri ? <Image source={{ uri }} style={{ width: '100%', height: 220, borderRadius: 10, marginBottom: S.md }} resizeMode="cover" /> : null}
      {busy ? (
        <View style={{ alignItems: 'center', padding: S.lg }}>
          <ActivityIndicator />
          <Muted style={{ marginTop: S.sm }}>{t('analyzing')}</Muted>
        </View>
      ) : null}

      {result ? (
        <Card title={t('scanResult')} right={<Badge label={levelLabel(t, result.risk_level)} color={levelColor(result.risk_level)} />}>
          <Text style={{ fontSize: 20, fontWeight: '700' }}>{result.disease_translated || result.disease}</Text>
          <Text style={[{ marginTop: S.sm, fontSize: 14, lineHeight: 20 }]}>{diseaseAction(t, result.risk_level, result.recommended_action)}</Text>
        </Card>
      ) : null}

      <Text style={[{ fontSize: 16, fontWeight: '700', marginTop: S.md, marginBottom: S.sm }]}>{t('scanHistory')}</Text>
      {history.length === 0 ? <Muted>{t('noScans')}</Muted> : null}
      {history.map((h) => (
        <View key={h.id} style={{ paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#DDE1D9' }}>
          <Text style={{ fontSize: 14, fontWeight: '600' }}>{h.disease}</Text>
          <Muted>{`${fmtDate(h.date, true)} · ${levelLabel(t, h.risk)}`}</Muted>
        </View>
      ))}
      <View style={{ height: S.xl }} />
    </ScrollView>
  );
}
