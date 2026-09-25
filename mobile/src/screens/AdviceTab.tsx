import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  Modal,
  RefreshControl,
  ScrollView,
  StatusBar,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import { Advisory, ApiError, AskResult, askByVoice, getAdvisories, sendFeedback } from '../api';
import { playAdvisory, playBase64, stopAudio } from '../audio';
import { fmtDate, levelLabel, useApp } from '../ctx';
import { errorText, useLoad, useTranslated } from '../hooks';
import { C, levelColor, S } from '../theme';
import { Badge, Banner, Btn, Card, Chip, Input, Muted, st } from '../ui';

// ---------------------------------------------------------------------------
// Advisory card
// ---------------------------------------------------------------------------
function AdvisoryCard({ a }: { a: Advisory }) {
  const { t, lang } = useApp();
  const plain = a.body_plain || a.body;
  const { out, state } = useTranslated([a.title, plain], lang);
  const [playing, setPlaying] = useState(false);
  const playingRef = useRef(false);
  const [note, setNote] = useState('');
  const [fbOpen, setFbOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [helpful, setHelpful] = useState<boolean | null>(null);
  const [comment, setComment] = useState('');
  const [fbBusy, setFbBusy] = useState(false);
  const [fbMsg, setFbMsg] = useState('');
  const [fbErr, setFbErr] = useState('');

  const setPlay = (v: boolean) => { playingRef.current = v; setPlaying(v); };

  const start = async () => {
    setNote(''); setPlay(true);
    const how = await playAdvisory(a.id, lang, plain, () => setPlay(false));
    if (how === 'device') setNote(t('voiceFallback'));
    if (how === 'cancelled') return;
  };
  const stop = async () => { setPlay(false); await stopAudio(); };
  const listen = () => (playing ? stop() : start());

  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) { firstRun.current = false; return; }
    if (playingRef.current) start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);
  useEffect(() => () => { if (playingRef.current) stopAudio(); }, []);

  const submitFb = async () => {
    setFbErr('');
    if (!rating || helpful === null) return setFbErr(t('feedbackTitle'));
    setFbBusy(true);
    try {
      await sendFeedback({ advisory_id: a.id, rating, helpful, comment: comment.trim() || undefined });
      setFbMsg(t('feedbackThanks')); setFbOpen(false);
    } catch (e) { setFbErr(errorText(t, e as ApiError)); }
    finally { setFbBusy(false); }
  };

  return (
    <Card title={out[0] || a.title} right={<Badge label={levelLabel(t, a.severity)} color={levelColor(a.severity)} />}>
      <Muted>{fmtDate(a.created_at, true)}</Muted>
      <Text style={[st.body, { marginTop: S.sm }]}>{out[1] || plain}</Text>
      {state === 'loading' ? <Muted style={{ marginTop: 4 }}>{t('translating')}</Muted> : null}
      {state === 'failed' ? <Muted style={{ marginTop: 4 }}>{t('translateFailed')}</Muted> : null}
      <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.md }}>
        <Btn label={playing ? t('stop') : t('listen')} kind="secondary" onPress={listen} style={{ flex: 1 }} />
        <Btn label={t('feedbackTitle')} kind="secondary" onPress={() => setFbOpen(!fbOpen)} style={{ flex: 1 }} />
      </View>
      {note ? <Muted style={{ marginTop: S.sm }}>{note}</Muted> : null}
      {fbMsg ? <Banner text={fbMsg} kind="ok" /> : null}
      {fbOpen ? (
        <View style={{ marginTop: S.md }}>
          <View style={{ flexDirection: 'row' }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <TouchableOpacity key={n} onPress={() => setRating(n)} style={{ padding: 4 }}>
                <Text style={{ fontSize: 28, color: n <= rating ? C.moderate : C.border }}>★</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={{ flexDirection: 'row', marginTop: S.sm }}>
            <Chip label={t('helpful')} selected={helpful === true} onPress={() => setHelpful(true)} />
            <Chip label={t('notHelpful')} selected={helpful === false} onPress={() => setHelpful(false)} />
          </View>
          <Input value={comment} onChangeText={setComment} placeholder={t('commentPlaceholder')} multiline />
          {fbErr ? <Banner text={fbErr} kind="error" /> : null}
          <Btn label={t('sendFeedback')} onPress={submitFb} busy={fbBusy} style={{ marginTop: S.sm }} />
        </View>
      ) : null}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// ChatGPT-style voice orb
// ---------------------------------------------------------------------------
type VoiceState = 'idle' | 'recording' | 'processing' | 'speaking';

const ORB_SIZE = 160;
const ORB_GLOW = 240;

function VoiceOrb({ state, onPress }: { state: VoiceState; onPress: () => void }) {
  const pulse = useRef(new Animated.Value(1)).current;
  const spin = useRef(new Animated.Value(0)).current;
  const glow = useRef(new Animated.Value(0.15)).current;

  useEffect(() => {
    pulse.stopAnimation(); spin.stopAnimation(); glow.stopAnimation();
    if (state === 'recording') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.18, duration: 600, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 0.88, duration: 600, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        ])
      ).start();
      Animated.loop(
        Animated.sequence([
          Animated.timing(glow, { toValue: 0.5, duration: 600, useNativeDriver: true }),
          Animated.timing(glow, { toValue: 0.15, duration: 600, useNativeDriver: true }),
        ])
      ).start();
    } else if (state === 'processing') {
      Animated.loop(
        Animated.timing(spin, { toValue: 1, duration: 1400, easing: Easing.linear, useNativeDriver: true })
      ).start();
      Animated.loop(
        Animated.sequence([
          Animated.timing(glow, { toValue: 0.4, duration: 700, useNativeDriver: true }),
          Animated.timing(glow, { toValue: 0.1, duration: 700, useNativeDriver: true }),
        ])
      ).start();
    } else if (state === 'speaking') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.12, duration: 500, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 0.92, duration: 500, useNativeDriver: true }),
        ])
      ).start();
      Animated.loop(
        Animated.sequence([
          Animated.timing(glow, { toValue: 0.45, duration: 500, useNativeDriver: true }),
          Animated.timing(glow, { toValue: 0.15, duration: 500, useNativeDriver: true }),
        ])
      ).start();
    } else {
      pulse.setValue(1); spin.setValue(0); glow.setValue(0.15);
    }
    return () => { pulse.stopAnimation(); spin.stopAnimation(); glow.stopAnimation(); };
  }, [state]);

  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });

  const orbColor =
    state === 'idle' ? '#22c55e' :
    state === 'recording' ? '#ef4444' :
    state === 'processing' ? '#f97316' :
    '#3b82f6';

  const icon =
    state === 'idle' ? '🎙' :
    state === 'recording' ? '⏹' :
    state === 'processing' ? '···' : '🔊';

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={state === 'processing' ? 1 : 0.85}
      style={{ width: ORB_GLOW, height: ORB_GLOW, alignItems: 'center', justifyContent: 'center' }}
    >
      {/* Outer glow halo */}
      <Animated.View style={{
        position: 'absolute',
        width: ORB_GLOW,
        height: ORB_GLOW,
        borderRadius: ORB_GLOW / 2,
        backgroundColor: orbColor,
        opacity: glow,
        transform: state === 'processing' ? [{ rotate }] : [{ scale: pulse }],
      }} />
      {/* Mid ring */}
      <Animated.View style={{
        position: 'absolute',
        width: ORB_SIZE + 40,
        height: ORB_SIZE + 40,
        borderRadius: (ORB_SIZE + 40) / 2,
        borderWidth: 1.5,
        borderColor: orbColor,
        opacity: state === 'idle' ? 0.25 : 0.5,
        transform: [{ scale: state === 'processing' ? 1 : pulse }],
      }} />
      {/* Core orb */}
      <Animated.View style={{
        width: ORB_SIZE,
        height: ORB_SIZE,
        borderRadius: ORB_SIZE / 2,
        backgroundColor: orbColor,
        alignItems: 'center',
        justifyContent: 'center',
        transform: state === 'processing' ? [{ scale: 1 }] : [{ scale: pulse }],
        shadowColor: orbColor,
        shadowOffset: { width: 0, height: 0 },
        shadowOpacity: 0.9,
        shadowRadius: 28,
        elevation: 20,
      }}>
        <Text style={{ fontSize: state === 'processing' ? 26 : 42, color: '#fff' }}>{icon}</Text>
      </Animated.View>
    </TouchableOpacity>
  );
}

function AskCard() {
  const { t, lang } = useApp();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [modalOpen, setModalOpen] = useState(false);
  const [res, setRes] = useState<AskResult | null>(null);
  const [err, setErr] = useState('');
  const voiceStateRef = useRef<VoiceState>('idle');

  const setVS = (s: VoiceState) => { voiceStateRef.current = s; setVoiceState(s); };

  useEffect(() => () => { stopAudio(); }, []);

  const startRecording = async () => {
    setErr('');
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) { setErr(t('micPerm')); return; }
    await stopAudio();
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync();
    recorder.record();
    setVS('recording');
  };

  const stopAndSend = async () => {
    if (voiceStateRef.current !== 'recording') return;
    setVS('processing');
    try {
      await recorder.stop();
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      const uri = recorder.uri;
      if (!uri) throw new ApiError(0, 'no recording');
      const r = await askByVoice(uri, 'audio/mp4', lang);
      setRes(r);
      if (r.answer_audio_base64) {
        setVS('speaking');
        await playBase64(r.answer_audio_base64, r.answer_audio_mimetype, () => setVS('idle'));
      } else {
        setVS('idle');
      }
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.status === 503 ? t('askUnavailable') : ae.status === -1 ? t('captureFailed') : errorText(t, ae));
      setVS('idle');
    }
  };

  const orbPress = () => {
    if (voiceState === 'idle') startRecording();
    else if (voiceState === 'recording') stopAndSend();
    else if (voiceState === 'speaking') { stopAudio(); setVS('idle'); }
    // processing: ignore taps
  };

  const close = () => {
    stopAudio();
    if (voiceStateRef.current === 'recording') {
      recorder.stop().catch(() => {});
    }
    setVS('idle'); setRes(null); setErr(''); setModalOpen(false);
  };

  const hintText =
    voiceState === 'idle' ? t('askIdle') :
    voiceState === 'recording' ? t('askRecording') :
    voiceState === 'processing' ? t('askProcessing') :
    t('askSpeaking');

  return (
    <>
      {/* Entry button */}
      <TouchableOpacity
        onPress={() => { setErr(''); setRes(null); setVS('idle'); setModalOpen(true); }}
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: S.sm,
          backgroundColor: '#2E7D32',
          borderRadius: 16,
          paddingVertical: 16,
          paddingHorizontal: S.lg,
          marginBottom: S.md,
          shadowColor: '#16a34a',
          shadowOffset: { width: 0, height: 4 },
          shadowOpacity: 0.35,
          shadowRadius: 10,
          elevation: 6,
        }}
        activeOpacity={0.85}
      >
        <Text style={{ fontSize: 22 }}>🎙</Text>
        <Text style={{ color: '#fff', fontSize: 17, fontWeight: '700', letterSpacing: 0.3 }}>{t('askTitle')}</Text>
      </TouchableOpacity>

      {/* Full-screen voice modal */}
      <Modal visible={modalOpen} animationType="fade" statusBarTranslucent transparent onRequestClose={close}>
        <StatusBar barStyle="light-content" backgroundColor="#000" />
        <View style={{
          flex: 1,
          backgroundColor: '#050505',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: 64,
          paddingBottom: 48,
          paddingHorizontal: 24,
        }}>

          {/* Header row */}
          <View style={{ width: '100%', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ color: '#fff', fontSize: 20, fontWeight: '700' }}>{t('askTitle')}</Text>
            <TouchableOpacity onPress={close} hitSlop={{ top: 16, bottom: 16, left: 16, right: 16 }}>
              <Text style={{ color: '#888', fontSize: 26, fontWeight: '300' }}>✕</Text>
            </TouchableOpacity>
          </View>

          {/* Spacer */}
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            {/* Orb */}
            <VoiceOrb state={voiceState} onPress={orbPress} />

            {/* Hint beneath orb */}
            <Text style={{
              color: voiceState === 'recording' ? '#fca5a5' : '#888',
              fontSize: 15,
              marginTop: 32,
              textAlign: 'center',
              letterSpacing: 0.2,
              fontWeight: voiceState === 'recording' ? '600' : '400',
            }}>
              {hintText}
            </Text>

            {/* Error */}
            {err ? (
              <View style={{ marginTop: 20, backgroundColor: '#1f0000', borderRadius: 10, padding: 12, width: '100%' }}>
                <Text style={{ color: '#fca5a5', fontSize: 13, textAlign: 'center' }}>{err}</Text>
              </View>
            ) : null}

            {/* Q&A result */}
            {res ? (
              <View style={{ marginTop: 24, width: '100%' }}>
                <View style={{ backgroundColor: '#111', borderRadius: 12, padding: 14, marginBottom: 10 }}>
                  <Text style={{ color: '#6b7280', fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.8 }}>{t('youAsked')}</Text>
                  <Text style={{ color: '#e5e7eb', fontSize: 15, lineHeight: 22 }}>{res.question_text}</Text>
                </View>
                <View style={{ backgroundColor: '#0f1a10', borderRadius: 12, padding: 14, borderLeftWidth: 3, borderLeftColor: '#22c55e' }}>
                  <Text style={{ color: '#6b7280', fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.8 }}>{t('answer')}</Text>
                  <Text style={{ color: '#e5e7eb', fontSize: 15, lineHeight: 22 }}>{res.answer_text}</Text>
                </View>
              </View>
            ) : null}
          </View>
        </View>
      </Modal>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main tab — no auto-load, blank until button tapped
// ---------------------------------------------------------------------------
export function AdviceTab() {
  const { field, t } = useApp();
  const id = field?.id;
  const [advisories, setAdvisories] = useState<Advisory[] | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  // open with real content: show saved advice, and if there is none yet make today's once
  // (before, the tab was blank until the farmer found and pressed the button)
  const autoFor = useRef<string | null>(null);
  useEffect(() => {
    if (!id || autoFor.current === id) return;
    autoFor.current = id;
    (async () => {
      try {
        const data = await getAdvisories(id, false);
        setAdvisories(data);
        setLoaded(true);
        if (data.length === 0) load(true);
      } catch {
        // the button below still works
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const load = async (generate: boolean) => {
    if (!id) return;
    setCreateErr('');
    if (generate) setCreating(true);
    else setRefreshing(true);
    try {
      const data = await getAdvisories(id, generate);
      setAdvisories(data);
      setLoaded(true);
    } catch (e) {
      setCreateErr(errorText(t, e as ApiError));
    } finally {
      setCreating(false);
      setRefreshing(false);
    }
  };

  return (
    <ScrollView
      contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loaded && load(false)} />}
      keyboardShouldPersistTaps="handled"
    >
      <AskCard />
      <Text style={[st.h1, { marginTop: S.sm, marginBottom: S.md }]}>{t('advisories')}</Text>
      <Btn
        label={creating ? t('loading') : t('getAdvice')}
        onPress={() => load(true)}
        busy={creating}
        style={{ marginBottom: S.md }}
      />
      {createErr ? <Banner text={createErr} kind="error" /> : null}
      {loaded && advisories && advisories.length === 0 && !creating ? (
        <Muted>{t('noAdvisories')}</Muted>
      ) : null}
      {!loaded ? (
        <Muted style={{ textAlign: 'center', marginTop: S.xl }}>
          {t('loading')}
        </Muted>
      ) : null}
      {(advisories || []).map((a) => <AdvisoryCard key={a.id} a={a} />)}
      <View style={{ height: S.xl }} />
    </ScrollView>
  );
}
