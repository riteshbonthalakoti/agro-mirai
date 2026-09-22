import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Image, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { File as ExpoFile, Paths } from 'expo-file-system';
import { ApiError, DiseaseAlert, getDiseaseRisk, scanLeaf } from '../api';
import { diseaseAction, fmtDate, levelLabel, useApp } from '../ctx';
import { SkeletonCard } from '../skeleton';
import { cacheGet, cacheSet } from '../storage';
import { levelColor, S, C } from '../theme';
import { Badge, Banner, Btn, Card, Muted } from '../ui';
import { ZoomModal } from '../zoom';

type HistoryItem = { id: string; date: string; disease: string; risk: string; source: string | null; confidence: number; action?: string | null };

/** Server history has no photo (nothing about the image itself is stored
 *  server-side). Scans made on THIS device get their photo copied into
 *  persistent local storage, keyed by scan id, so past scans stay openable
 *  after the app restarts. A scan made on another device/phone has no local
 *  photo -- its card says so honestly instead of showing a blank/broken image. */
async function savePhotoLocally(id: string, sourceUri: string): Promise<string | null> {
  try {
    const dst = new ExpoFile(Paths.document, 'scans', `${id}.jpg`);
    if (!dst.parentDirectory.exists) dst.parentDirectory.create({ intermediates: true });
    await new ExpoFile(sourceUri).copy(dst, { overwrite: true });
    return dst.uri;
  } catch {
    return null;
  }
}

export function ScanTab() {
  const { field, t, lang } = useApp();
  const [uri, setUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DiseaseAlert | null>(null);
  const [err, setErr] = useState('');
  const [history, setHistory] = useState<HistoryItem[] | null>(null);
  const [photos, setPhotos] = useState<Record<string, string>>({});
  const [zoomUri, setZoomUri] = useState<string | null>(null);
  const [openItem, setOpenItem] = useState<HistoryItem | null>(null);

  useEffect(() => {
    cacheGet<Record<string, string>>('scanPhotos').then((p) => p && setPhotos(p));
  }, []);

  // History comes from the server (every photo scan is stored there), so it
  // survives reinstalling the app or switching phones. The device cache only
  // paints instantly / covers being offline. Photos themselves stay local
  // (see savePhotoLocally) since the server never stores the image.
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
            action: diseaseAction(t, a.risk_level, a.recommended_action),
          }));
        setHistory(fromServer);
        cacheSet('scans', fromServer);
      })
      .catch(() => alive && setHistory((h) => h ?? []));
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
      const localUri = await savePhotoLocally(r.id, imageUri);
      if (localUri) {
        const nextPhotos = { ...photos, [r.id]: localUri };
        setPhotos(nextPhotos);
        cacheSet('scanPhotos', nextPhotos);
      }
      const item: HistoryItem = {
        id: r.id, date: new Date().toISOString(), disease: r.disease_translated || r.disease,
        risk: r.risk_level, source: r.source ?? null, confidence: r.confidence,
        action: diseaseAction(t, r.risk_level, r.recommended_action),
      };
      const next = [item, ...(history ?? [])].slice(0, 30);
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
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
      <Card title={t('scanTitle')}>
        <Muted>{t('scanSub')}</Muted>
        <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.md }}>
          <Btn label={t('takePhoto')} onPress={camera} disabled={busy} style={{ flex: 1 }} />
          <Btn label={t('pickGallery')} kind="secondary" onPress={gallery} disabled={busy} style={{ flex: 1 }} />
        </View>
      </Card>

      {err ? <Banner text={err} kind="error" /> : null}
      {uri ? (
        <TouchableOpacity onPress={() => setZoomUri(uri)} activeOpacity={0.9}>
          <Image source={{ uri }} style={{ width: '100%', height: 220, borderRadius: 10, marginBottom: S.md }} resizeMode="cover" />
          <Muted style={{ marginTop: -S.sm, marginBottom: S.md }}>{t('tapToZoom')}</Muted>
        </TouchableOpacity>
      ) : null}
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
      {history === null ? <SkeletonCard /> : null}
      {history !== null && history.length === 0 ? <Muted>{t('noScans')}</Muted> : null}
      {history?.map((h) => (
        <TouchableOpacity
          key={h.id}
          onPress={() => setOpenItem(h)}
          activeOpacity={0.7}
          style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: S.sm, borderBottomWidth: 1, borderBottomColor: C.border }}
        >
          {photos[h.id] ? (
            <Image source={{ uri: photos[h.id] }} style={{ width: 48, height: 48, borderRadius: 8, marginRight: S.md }} />
          ) : (
            <View style={{ width: 48, height: 48, borderRadius: 8, marginRight: S.md, backgroundColor: C.surface }} />
          )}
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600' }}>{h.disease}</Text>
            <Muted>{`${fmtDate(h.date, true)} · ${levelLabel(t, h.risk)}`}</Muted>
          </View>
        </TouchableOpacity>
      ))}
      <View style={{ height: S.xl }} />

      <ZoomModal uri={zoomUri} visible={!!zoomUri} onClose={() => setZoomUri(null)} />

      {openItem ? (
        <ScanDetailModal
          item={openItem}
          photoUri={photos[openItem.id] ?? null}
          onClose={() => setOpenItem(null)}
          onZoom={(u) => setZoomUri(u)}
        />
      ) : null}
    </ScrollView>
  );
}

function ScanDetailModal({ item, photoUri, onClose, onZoom }: { item: HistoryItem; photoUri: string | null; onClose: () => void; onZoom: (uri: string) => void }) {
  const { t } = useApp();
  return (
    <View style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' }}>
      <View style={{ backgroundColor: C.bg, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: S.lg, paddingBottom: S.xl }}>
        {photoUri ? (
          <TouchableOpacity onPress={() => onZoom(photoUri)} activeOpacity={0.9}>
            <Image source={{ uri: photoUri }} style={{ width: '100%', height: 200, borderRadius: 10, marginBottom: S.sm }} resizeMode="cover" />
            <Muted style={{ marginBottom: S.md }}>{t('tapToZoom')}</Muted>
          </TouchableOpacity>
        ) : (
          <View style={{ backgroundColor: C.surface, borderRadius: 10, padding: S.lg, marginBottom: S.md, alignItems: 'center' }}>
            <Muted>{t('scanPhotoNotOnDevice')}</Muted>
          </View>
        )}
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Text style={{ fontSize: 20, fontWeight: '700', flex: 1 }}>{item.disease}</Text>
          <Badge label={levelLabel(t, item.risk)} color={levelColor(item.risk)} />
        </View>
        <Muted style={{ marginTop: 4 }}>{fmtDate(item.date, true)}</Muted>
        {item.action ? <Text style={{ marginTop: S.md, fontSize: 14, lineHeight: 20 }}>{item.action}</Text> : null}
        <Btn label={t('close')} kind="secondary" onPress={onClose} style={{ marginTop: S.lg }} />
      </View>
    </View>
  );
}
