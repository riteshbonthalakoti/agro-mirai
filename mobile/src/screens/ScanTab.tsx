import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Animated, Easing, Image, Linking, Modal, ScrollView, Text, TouchableOpacity, View,
  useWindowDimensions,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import { File as ExpoFile, Paths } from 'expo-file-system';
import { Icon } from '../../icons';
import { feedback } from '../feedback';
import { ApiError, DiseaseAlert, getDiseaseRisk, scanLeaf } from '../api';
import { diseaseAction, fmtDate, levelLabel, useApp } from '../ctx';
import { useTranslated } from '../hooks';
import { SkeletonCard } from '../skeleton';
import { cacheGet, cacheSet } from '../storage';
import { levelColor, S, C } from '../theme';
import { Badge, Banner, Btn, Card, Muted } from '../ui';
import { ZoomModal } from '../zoom';

type HistoryItem = { id: string; date: string; disease: string; risk: string; source: string | null; confidence: number; action?: string | null };
type Phase = 'home' | 'analyzing' | 'result' | 'notLeaf' | 'error';
type ErrKind = 'network' | 'server' | 'unavailable' | 'file' | 'noField';

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

/** Centre square, max 1024 px, JPEG. The camera guide is that same centre square, so what the
 *  farmer framed is what gets checked; and a ~200 KB upload instead of a 4-5 MB photo matters on
 *  a weak connection. Falls back to the original photo if the image tools fail. */
async function prepareImage(uri: string): Promise<string> {
  try {
    // first pass normalises orientation and tells us the real size
    const base = await manipulateAsync(uri, [], { compress: 0.95, format: SaveFormat.JPEG });
    const side = Math.min(base.width, base.height);
    const out = await manipulateAsync(
      base.uri,
      [
        { crop: { originX: Math.round((base.width - side) / 2), originY: Math.round((base.height - side) / 2), width: side, height: side } },
        { resize: { width: Math.min(side, 1024) } },
      ],
      { compress: 0.85, format: SaveFormat.JPEG },
    );
    return out.uri;
  } catch {
    return uri;
  }
}

// ---------------------------------------------------------------- camera
function CameraCapture({ onCaptured, onClose, onGallery }: { onCaptured: (uri: string) => void; onClose: () => void; onGallery: () => void }) {
  const { t } = useApp();
  const { width } = useWindowDimensions();
  const [perm, askPerm] = useCameraPermissions();
  const cam = useRef<CameraView>(null);
  const [ready, setReady] = useState(false);
  const [torch, setTorch] = useState(false);
  const [busy, setBusy] = useState(false);

  const shoot = async () => {
    if (!cam.current || !ready || busy) return;
    setBusy(true);
    feedback.shutter();
    try {
      const pic = await cam.current.takePictureAsync({ quality: 0.9, shutterSound: false });
      if (pic?.uri) onCaptured(pic.uri);
    } catch {
      setBusy(false);
    }
  };

  if (!perm) return <View style={{ flex: 1, backgroundColor: '#000' }} />;
  if (!perm.granted) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg, padding: S.xl, justifyContent: 'center' }}>
        <Icon name="camera" size={44} color={C.accent} />
        <Text style={{ fontSize: 22, fontWeight: '700', color: C.text, marginTop: S.lg }}>{t('camAllowTitle')}</Text>
        <Text style={{ color: C.muted, marginTop: S.sm, fontSize: 15 }}>{t('camAllowBody')}</Text>
        <Btn
          label={perm.canAskAgain ? t('camAllow') : t('camSettings')}
          onPress={() => (perm.canAskAgain ? askPerm() : Linking.openSettings())}
          style={{ marginTop: S.xl }}
        />
        <Btn label={t('cancel')} kind="secondary" onPress={onClose} style={{ marginTop: S.md }} />
      </View>
    );
  }

  const boxH = (width * 4) / 3; // portrait 3:4 preview; the guide is the full-width centre square
  const band = (boxH - width) / 2;
  const corner = (pos: object) => <View style={[{ position: 'absolute', width: 28, height: 28, borderColor: '#fff' }, pos]} />;
  return (
    <View style={{ flex: 1, backgroundColor: '#000' }}>
      <View style={{ width, height: boxH, marginTop: 44, alignSelf: 'center' }}>
        <CameraView ref={cam} style={{ flex: 1 }} facing="back" enableTorch={torch} onCameraReady={() => setReady(true)} />
        {/* dim everything outside the square */}
        <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: 0, height: band, backgroundColor: 'rgba(0,0,0,0.55)' }} />
        <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: band, backgroundColor: 'rgba(0,0,0,0.55)' }} />
        <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: band, width, height: width }}>
          {corner({ left: 8, top: 8, borderLeftWidth: 4, borderTopWidth: 4, borderTopLeftRadius: 8 })}
          {corner({ right: 8, top: 8, borderRightWidth: 4, borderTopWidth: 4, borderTopRightRadius: 8 })}
          {corner({ left: 8, bottom: 8, borderLeftWidth: 4, borderBottomWidth: 4, borderBottomLeftRadius: 8 })}
          {corner({ right: 8, bottom: 8, borderRightWidth: 4, borderBottomWidth: 4, borderBottomRightRadius: 8 })}
        </View>
        <Text style={{ position: 'absolute', top: band / 2 - 10, alignSelf: 'center', color: '#fff', fontWeight: '700', fontSize: 15 }}>{t('camGuide')}</Text>
      </View>

      <TouchableOpacity onPress={onClose} accessibilityLabel={t('cancel')} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        style={{ position: 'absolute', top: 48, left: S.lg, width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' }}>
        <Icon name="close" size={20} color="#fff" />
      </TouchableOpacity>

      <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingBottom: S.lg }}>
        <TouchableOpacity onPress={onGallery} accessibilityLabel={t('pickGallery')} style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="gallery" size={26} color="#fff" />
        </TouchableOpacity>
        <TouchableOpacity onPress={shoot} disabled={!ready || busy} accessibilityLabel={t('takePhoto')} activeOpacity={0.7}
          style={{ width: 84, height: 84, borderRadius: 42, borderWidth: 5, borderColor: '#fff', alignItems: 'center', justifyContent: 'center', opacity: ready ? 1 : 0.5 }}>
          {busy ? <ActivityIndicator color="#fff" /> : <View style={{ width: 62, height: 62, borderRadius: 31, backgroundColor: '#fff' }} />}
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setTorch(!torch)} accessibilityLabel="Torch" style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: torch ? '#F5C518' : 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="bolt" size={26} color={torch ? '#000' : '#fff'} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

// -------------------------------------------------------------- analysing
function AnalyzingView({ uri, onCancel }: { uri: string; onCancel: () => void }) {
  const { t } = useApp();
  const { width } = useWindowDimensions();
  const size = width - S.lg * 2;
  const y = useRef(new Animated.Value(0)).current;
  const [step, setStep] = useState(0);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(y, { toValue: 1, duration: 1300, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(y, { toValue: 0, duration: 1300, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    const a = setTimeout(() => setStep(1), 2500);
    const b = setTimeout(() => setStep(2), 6000);
    const c = setTimeout(() => setSlow(true), 15000);
    return () => { loop.stop(); clearTimeout(a); clearTimeout(b); clearTimeout(c); };
  }, [y]);

  const label = [t('scanStep1'), t('scanStep2'), t('scanStep3')][step];
  return (
    <View style={{ alignItems: 'center' }}>
      <View style={{ width: size, height: size, borderRadius: 16, overflow: 'hidden', backgroundColor: C.surface }}>
        <Image source={{ uri }} style={{ width: size, height: size }} resizeMode="cover" />
        <Animated.View
          pointerEvents="none"
          style={{ position: 'absolute', left: 0, right: 0, height: 4, backgroundColor: 'rgba(76,175,80,0.95)', transform: [{ translateY: y.interpolate({ inputRange: [0, 1], outputRange: [0, size - 4] }) }] }}
        />
      </View>
      <Text style={{ marginTop: S.lg, fontSize: 18, fontWeight: '700', color: C.text }}>{label}</Text>
      <View style={{ flexDirection: 'row', marginTop: S.sm }}>
        {[0, 1, 2].map((i) => (
          <View key={i} style={{ width: 28, height: 4, borderRadius: 2, marginHorizontal: 3, backgroundColor: i <= step ? C.accent : C.border }} />
        ))}
      </View>
      {slow ? <Muted style={{ marginTop: S.md, textAlign: 'center' }}>{t('scanSlow')}</Muted> : null}
      <Btn label={t('cancel')} kind="secondary" onPress={onCancel} style={{ marginTop: S.xl, alignSelf: 'stretch' }} />
    </View>
  );
}

// ----------------------------------------------------------------- result
/** The server sends one English paragraph: what to do, then optionally "Other possibilities: ..." and
 *  "Note: ...". Split it so each part gets its own place on screen. */
function splitAdvice(raw: string): { steps: string[]; others: string[]; note: string } {
  const steps: string[] = [];
  let others: string[] = [];
  let note = '';
  for (const part of raw.split(/\.\s+/)) {
    const s = part.trim().replace(/\.$/, '');
    if (!s) continue;
    if (note || s.startsWith('Note:')) note = `${note ? `${note}. ` : ''}${s.replace(/^Note:\s*/, '')}`;
    else if (s.startsWith('Other possibilities:')) others = s.replace('Other possibilities:', '').split(';').map((x) => x.trim()).filter(Boolean);
    else s.split(';').forEach((x) => { const y = x.trim(); if (y) steps.push(y.charAt(0).toUpperCase() + y.slice(1)); });
  }
  return { steps, others, note };
}

function sureLevel(c: number): 'High' | 'Medium' | 'Low' {
  return c >= 0.7 ? 'High' : c >= 0.45 ? 'Medium' : 'Low';
}

function ResultView({ result, uri, onRetake, onDone, onZoom }: { result: DiseaseAlert; uri: string; onRetake: () => void; onDone: () => void; onZoom: (u: string) => void }) {
  const { t, lang } = useApp();
  const { width } = useWindowDimensions();
  const size = width - S.lg * 2;
  const unsure = /^Not sure/i.test(result.disease);
  const bestGuess = result.disease.replace(/^Not sure\.\s*Best guess:\s*/i, '');
  const { steps, others, note } = splitAdvice(result.recommended_action || '');
  // the advice is English from the server: translate it into the farmer's language (cached on the device)
  const tr = useTranslated([...steps, note], lang);
  const shownSteps = steps.map((s, i) => tr.out[i] || s);
  const shownNote = tr.out[steps.length] || note;
  const generic = !steps.length ? diseaseAction(t, result.risk_level, result.recommended_action) : '';
  const lvl = sureLevel(result.confidence);
  const lvlColor = lvl === 'High' ? C.low : lvl === 'Medium' ? C.moderate : C.high;
  const bars = lvl === 'High' ? 3 : lvl === 'Medium' ? 2 : 1;

  return (
    <View>
      <TouchableOpacity onPress={() => onZoom(uri)} activeOpacity={0.9}>
        <Image source={{ uri }} style={{ width: size, height: size * 0.62, borderRadius: 16, marginBottom: S.md }} resizeMode="cover" />
      </TouchableOpacity>

      <View style={{ backgroundColor: unsure ? '#FFF6E0' : C.bg, borderWidth: 1, borderColor: unsure ? '#F0DCA8' : C.border, borderRadius: 16, padding: S.lg }}>
        {unsure ? (
          <>
            <Text style={{ fontSize: 13, fontWeight: '700', color: C.warn, letterSpacing: 0.5 }}>{t('resNotSureTitle').toUpperCase()}</Text>
            <Text style={{ fontSize: 22, fontWeight: '700', color: C.text, marginTop: 4 }}>{`${t('resBestGuess')}: ${bestGuess}`}</Text>
          </>
        ) : (
          <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
            <Text style={{ flex: 1, fontSize: 22, fontWeight: '700', color: C.text }}>{result.disease_translated || result.disease}</Text>
            <Badge label={levelLabel(t, result.risk_level)} color={levelColor(result.risk_level)} />
          </View>
        )}

        <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: S.md }}>
          <Text style={{ color: C.muted, fontSize: 14, marginRight: S.sm }}>{t('resHowSure')}</Text>
          {[1, 2, 3].map((i) => (
            <View key={i} style={{ width: 26, height: 8, borderRadius: 4, marginRight: 4, backgroundColor: i <= bars ? lvlColor : C.border }} />
          ))}
          <Text style={{ marginLeft: S.sm, fontWeight: '700', color: lvlColor }}>{t(lvl === 'High' ? 'sureHigh' : lvl === 'Medium' ? 'sureMedium' : 'sureLow')}</Text>
        </View>

        {shownSteps.length || generic ? (
          <>
            <Text style={{ fontSize: 16, fontWeight: '700', color: C.text, marginTop: S.lg }}>{t('resWhatToDo')}</Text>
            {(shownSteps.length ? shownSteps : [generic]).map((s, i) => (
              <View key={i} style={{ flexDirection: 'row', marginTop: S.sm }}>
                <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', marginRight: S.sm, marginTop: 1 }}>
                  <Text style={{ color: '#fff', fontSize: 12, fontWeight: '700' }}>{i + 1}</Text>
                </View>
                <Text style={{ flex: 1, fontSize: 15, lineHeight: 21, color: C.text }}>{s}</Text>
              </View>
            ))}
          </>
        ) : null}

        {others.length ? (
          <>
            <Text style={{ fontSize: 14, fontWeight: '700', color: C.muted, marginTop: S.lg }}>{t('resCouldBe')}</Text>
            {others.map((o, i) => <Text key={i} style={{ fontSize: 14, color: C.text, marginTop: 4 }}>{`• ${o}`}</Text>)}
          </>
        ) : null}

        {shownNote ? (
          <View style={{ flexDirection: 'row', backgroundColor: C.surface, borderRadius: 10, padding: S.md, marginTop: S.lg }}>
            <Icon name="info" size={16} color={C.muted} />
            <Text style={{ flex: 1, marginLeft: S.sm, fontSize: 13, lineHeight: 18, color: C.muted }}>{shownNote}</Text>
          </View>
        ) : null}
      </View>

      <Btn label={unsure ? t('resRetake') : t('resScanAnother')} onPress={onRetake} style={{ marginTop: S.lg }} />
      <Btn label={t('resDone')} kind="secondary" onPress={onDone} style={{ marginTop: S.sm }} />
    </View>
  );
}

function ProblemView({ kind, message, uri, onRetry, onRetake, onCancel }: { kind: 'notLeaf' | ErrKind; message: string; uri: string | null; onRetry: () => void; onRetake: () => void; onCancel: () => void }) {
  const { t } = useApp();
  const { width } = useWindowDimensions();
  const size = width - S.lg * 2;
  const notLeaf = kind === 'notLeaf';
  const title = notLeaf ? t('resNotLeafTitle') : t('resErrTitle');
  const body = notLeaf
    ? t('resNotLeafBody')
    : kind === 'network' ? t('scanErrorNetwork')
    : kind === 'unavailable' ? t('scanUnavailable')
    : kind === 'file' ? t('scanErrorFile')
    : kind === 'noField' ? t('scanNeedsField')
    : t('serverBusy');
  return (
    <View>
      {uri ? <Image source={{ uri }} style={{ width: size, height: size * 0.5, borderRadius: 16, marginBottom: S.md, opacity: 0.85 }} resizeMode="cover" /> : null}
      <View style={{ backgroundColor: '#FDECEA', borderWidth: 1, borderColor: '#F5C6C0', borderRadius: 16, padding: S.lg }}>
        <Icon name="alert" size={26} color={C.danger} />
        <Text style={{ fontSize: 20, fontWeight: '700', color: C.text, marginTop: S.sm }}>{title}</Text>
        <Text style={{ fontSize: 15, lineHeight: 21, color: C.text, marginTop: S.sm }}>{body}</Text>
        {message && !notLeaf && kind === 'server' && __DEV__ ? <Muted style={{ marginTop: S.sm }}>{message}</Muted> : null}
      </View>
      {notLeaf ? (
        <Btn label={t('resRetake')} onPress={onRetake} style={{ marginTop: S.lg }} />
      ) : (
        <>
          {uri ? <Btn label={t('retry')} onPress={onRetry} style={{ marginTop: S.lg }} /> : null}
          <Btn label={t('resRetake')} kind="secondary" onPress={onRetake} style={{ marginTop: S.sm }} />
        </>
      )}
      <Btn label={t('cancel')} kind="secondary" onPress={onCancel} style={{ marginTop: S.sm }} />
    </View>
  );
}

// ------------------------------------------------------------------ screen
export function ScanTab() {
  const { field, t, lang } = useApp();
  const [phase, setPhase] = useState<Phase>('home');
  const [cameraOpen, setCameraOpen] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [result, setResult] = useState<DiseaseAlert | null>(null);
  const [errKind, setErrKind] = useState<ErrKind>('server');
  const [errMsg, setErrMsg] = useState('');
  const [history, setHistory] = useState<HistoryItem[] | null>(null);
  const [photos, setPhotos] = useState<Record<string, string>>({});
  const [zoomUri, setZoomUri] = useState<string | null>(null);
  const [openItem, setOpenItem] = useState<HistoryItem | null>(null);
  const [notice, setNotice] = useState('');
  const runId = useRef(0);

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
    if (!field) { setErrKind('noField'); setPhase('error'); return; }
    const id = ++runId.current;
    setPhotoUri(imageUri);
    setResult(null);
    setPhase('analyzing');
    try {
      // Read the local file through expo-file-system's File (a Blob) instead
      // of fetch(file://): on Android fetch() can "succeed" with a 14-byte
      // "File not found" body that then uploads as the image (Module 34).
      const f = new ExpoFile(imageUri);
      if (!f.exists || !f.size) throw new ApiError(-1, t('scanErrorFile'));
      const r = await scanLeaf(field.id, f as unknown as Blob, lang);
      if (id !== runId.current) return; // cancelled while waiting
      if (r.source !== 'cnn') {
        // The photo model was unreachable and the server answered with a
        // weather-based estimate. That says nothing about THIS leaf, so it is
        // not shown as a diagnosis and not added to scan history.
        setErrKind('unavailable');
        setPhase('error');
        return;
      }
      setResult(r);
      setPhase('result');
      if (/^Not sure/i.test(r.disease)) feedback.warning();
      else feedback.success();
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
      if (id !== runId.current) return;
      const ae = e as ApiError;
      feedback.error();
      if (ae.code === 'NOT_A_LEAF') { setPhase('notLeaf'); return; }
      setErrKind(ae.status === -1 ? 'file' : ae.isNetwork ? 'network' : 'server');
      setErrMsg(ae.message || '');
      setPhase('error');
    }
  };

  /** camera or gallery photo -> centre-square crop -> upload, with no extra screens in between */
  const process = async (rawUri: string) => {
    setPhotoUri(rawUri);
    setPhase('analyzing');
    const prepared = await prepareImage(rawUri);
    await analyze(prepared);
  };

  const openCamera = () => { setNotice(''); setCameraOpen(true); };

  const pickGallery = async () => {
    setCameraOpen(false);
    setNotice('');
    try {
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 1 });
      if (!r.canceled && r.assets?.[0]?.uri) await process(r.assets[0].uri);
    } catch {
      setNotice(t('captureFailed'));
    }
  };

  const cancelScan = () => { runId.current++; setPhase('home'); };
  const backHome = () => { setPhase('home'); setResult(null); };

  return (
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }} keyboardShouldPersistTaps="handled">
      {phase === 'analyzing' && photoUri ? <AnalyzingView uri={photoUri} onCancel={cancelScan} /> : null}

      {phase === 'result' && result && photoUri ? (
        <ResultView result={result} uri={photoUri} onRetake={openCamera} onDone={backHome} onZoom={(u) => setZoomUri(u)} />
      ) : null}

      {phase === 'notLeaf' || phase === 'error' ? (
        <ProblemView
          kind={phase === 'notLeaf' ? 'notLeaf' : errKind}
          message={errMsg}
          uri={photoUri}
          onRetry={() => photoUri && analyze(photoUri)}
          onRetake={openCamera}
          onCancel={backHome}
        />
      ) : null}

      {phase === 'home' ? (
        <>
          <Card>
            <View style={{ alignItems: 'center', paddingVertical: S.sm }}>
              <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: '#E8F3E8', alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="leaf" size={36} color={C.accent} />
              </View>
              <Text style={{ fontSize: 22, fontWeight: '700', color: C.text, marginTop: S.md }}>{t('scanHero')}</Text>
              <Text style={{ fontSize: 14, color: C.muted, textAlign: 'center', marginTop: 4 }}>{t('scanHeroSub')}</Text>
            </View>
            <Btn label={t('takePhoto')} onPress={openCamera} style={{ marginTop: S.md }} />
            <Btn label={t('pickGallery')} kind="secondary" onPress={pickGallery} style={{ marginTop: S.sm }} />
          </Card>

          <Card title={t('scanHowTitle')}>
            {[t('scanHow1'), t('scanHow2'), t('scanHow3')].map((s, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'center', marginTop: i ? S.sm : 0 }}>
                <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
                  <Text style={{ color: '#fff', fontWeight: '700', fontSize: 13 }}>{i + 1}</Text>
                </View>
                <Text style={{ flex: 1, fontSize: 15, color: C.text }}>{s}</Text>
              </View>
            ))}
            <Muted style={{ marginTop: S.md }}>{t('scanCoverage')}</Muted>
          </Card>

          {notice ? <Banner text={notice} kind="error" /> : null}

          <Text style={{ fontSize: 16, fontWeight: '700', marginTop: S.sm, marginBottom: S.sm, color: C.text }}>{t('scanHistory')}</Text>
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
                <Image source={{ uri: photos[h.id] }} style={{ width: 52, height: 52, borderRadius: 10, marginRight: S.md }} />
              ) : (
                <View style={{ width: 52, height: 52, borderRadius: 10, marginRight: S.md, backgroundColor: C.surface, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="leaf" size={22} color={C.muted} />
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '600', color: C.text }} numberOfLines={2}>{h.disease}</Text>
                <Muted>{fmtDate(h.date, true)}</Muted>
              </View>
              <Badge label={levelLabel(t, h.risk)} color={levelColor(h.risk)} />
            </TouchableOpacity>
          ))}
        </>
      ) : null}
      <View style={{ height: S.xl }} />

      <Modal visible={cameraOpen} animationType="slide" statusBarTranslucent onRequestClose={() => setCameraOpen(false)}>
        {cameraOpen ? (
          <CameraCapture
            onClose={() => setCameraOpen(false)}
            onGallery={pickGallery}
            onCaptured={(u) => { setCameraOpen(false); process(u); }}
          />
        ) : null}
      </Modal>

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
