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
  useWindowDimensions,
} from 'react-native';
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import { Advisory, ApiError, AskResult, askByVoice, getAdvisories, sendFeedback } from '../api';
import { playAdvisory, playBase64, stopAudio } from '../audio';
import { Conversation, getConversations } from '../conversations';
import { fmtDate, levelLabel, useApp } from '../ctx';
import { classifyError } from '../errors';
import { logError } from '../errorLog';
import { errorText, useLoad, useTranslated } from '../hooks';
import { formatTime } from '../storage';
import { C, levelColor, S } from '../theme';
import { useToast } from '../toast';
import { Badge, Banner, Btn, Chip, Input, Muted, st } from '../ui';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { Icon, IconName } from '../../icons';
import { VoiceMode } from '../components/VoiceMode';

// ---------------------------------------------------------------------------
// Advisory card
// ---------------------------------------------------------------------------
function AdvisoryCard({ a }: { a: Advisory }) {
  const { t, lang } = useApp();
  const toast = useToast();
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
    const shown = out[1] || plain;
    const how = await playAdvisory(a.id, lang, shown, lang === 'en' || state === 'done', () => setPlay(false));
    if (how === 'device') { setNote(t('voiceFallback')); toast.show(t('voiceFallbackToast')); }
    if (how === 'text-only') { setPlay(false); setNote(t('voiceTextOnly')); toast.show(t('voiceTextOnly'), 'error'); }
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
    } catch (e) {
      const { kind } = classifyError(e);
      if (kind === 'unknown') logError('AdviceTab.sendFeedback', e);
      setFbErr(errorText(t, e as ApiError, { write: true }));
    }
    finally { setFbBusy(false); }
  };

  const sevColor = levelColor(a.severity);
  const paras = (out[1] || plain).split(/\n\s*\n/).map((x) => x.trim()).filter(Boolean);
  const ROW: { icon: IconName; tint: string; cap: string }[] = [
    { icon: 'sprout', tint: '#E8F3E8', cap: t('cropRec') },
    { icon: 'drop', tint: '#E3F1FA', cap: t('irrigation') },
    { icon: 'blight', tint: '#FDF0DC', cap: t('diseaseRisk') },
  ];

  return (
    <View style={{ backgroundColor: '#fff', borderRadius: 26, marginBottom: S.lg, overflow: 'hidden', borderWidth: 1, borderColor: '#E3E8DC', shadowColor: '#000', shadowOpacity: 0.07, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 3 }}>
      {/* severity ribbon */}
      <View style={{ backgroundColor: sevColor, paddingHorizontal: S.lg, paddingVertical: 10, flexDirection: 'row', alignItems: 'center' }}>
        <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: 'rgba(255,255,255,0.92)' }}>{fmtDate(a.created_at, true)}</Text>
        <View style={{ backgroundColor: 'rgba(255,255,255,0.25)', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 4 }}>
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#fff' }}>{levelLabel(t, a.severity)}</Text>
        </View>
      </View>

      <View style={{ padding: S.lg }}>
        <Text style={{ fontSize: 21, lineHeight: 28, fontWeight: '800', color: C.text }}>{out[0] || a.title}</Text>
        {state === 'loading' ? <Muted style={{ marginTop: 4 }}>{t('translating')}</Muted> : null}
        {state === 'failed' ? <Muted style={{ marginTop: 4 }}>{t('translateFailed')}</Muted> : null}

        {paras.length >= 2 ? (
          <View style={{ marginTop: S.md }}>
            {paras.map((p, k) => {
              const r = ROW[k] ?? { icon: 'info' as IconName, tint: '#EEF1E8', cap: '' };
              return (
                <View key={k} style={{ flexDirection: 'row', marginBottom: S.md }}>
                  <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: r.tint, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
                    <Icon name={r.icon} size={22} color={C.accent} />
                  </View>
                  <View style={{ flex: 1 }}>
                    {paras.length === 3 && r.cap ? <Text style={{ fontSize: 12.5, fontWeight: '800', letterSpacing: 0.6, color: C.muted, marginBottom: 2 }}>{r.cap.toUpperCase()}</Text> : null}
                    <Text style={{ fontSize: 16.5, lineHeight: 24, color: C.text }}>{p}</Text>
                  </View>
                </View>
              );
            })}
          </View>
        ) : (
          <Text style={{ fontSize: 16.5, lineHeight: 25, color: C.text, marginTop: S.md }}>{out[1] || plain}</Text>
        )}

        {/* listen */}
        <TouchableOpacity
          onPress={listen}
          activeOpacity={0.85}
          style={{ minHeight: 60, borderRadius: 30, backgroundColor: playing ? '#fff' : C.accent, borderWidth: 2, borderColor: C.accent, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginTop: S.xs }}
        >
          {playing ? <Bars color={C.accent} /> : <Icon name="speaker" size={24} color="#fff" />}
          <Text style={{ fontSize: 18, fontWeight: '800', color: playing ? C.accent : '#fff', marginLeft: S.md }}>{playing ? t('stop') : t('listen')}</Text>
        </TouchableOpacity>
        {note ? <View style={{ marginTop: S.sm, backgroundColor: '#FFF6E0', borderRadius: 12, padding: S.md }}><Text style={{ fontSize: 14, lineHeight: 20, color: '#5C4300' }}>{note}</Text></View> : null}

        {/* feedback */}
        {fbMsg ? <Banner text={fbMsg} kind="ok" /> : null}
        {!fbOpen && !fbMsg ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: S.lg }}>
            <Text style={{ flex: 1, fontSize: 15, color: C.muted }}>{t('feedbackTitle')}</Text>
            <TouchableOpacity onPress={() => { setHelpful(true); setFbOpen(true); }} style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: '#E8F3E8', alignItems: 'center', justifyContent: 'center', marginRight: S.sm }}>
              <Text style={{ fontSize: 22 }}>👍</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setHelpful(false); setFbOpen(true); }} style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: '#FBEAE7', alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ fontSize: 22 }}>👎</Text>
            </TouchableOpacity>
          </View>
        ) : null}
        {fbOpen ? (
          <View style={{ marginTop: S.lg, backgroundColor: '#F6F8F2', borderRadius: 16, padding: S.md }}>
            <View style={{ flexDirection: 'row', justifyContent: 'center' }}>
              {[1, 2, 3, 4, 5].map((n) => (
                <TouchableOpacity key={n} onPress={() => setRating(n)} style={{ padding: 4 }}>
                  <Text style={{ fontSize: 34, color: n <= rating ? C.moderate : C.border }}>★</Text>
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
      </View>
    </View>
  );
}

/** Little equalizer bars shown while advice is being read aloud. */
function Bars({ color }: { color: string }) {
  const vals = useRef([0, 1, 2, 3].map(() => new Animated.Value(0.3))).current;
  useEffect(() => {
    const loops = vals.map((v, k) => Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 320 + k * 90, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      Animated.timing(v, { toValue: 0.25, duration: 320 + k * 90, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
    ])));
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [vals]);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', height: 24 }}>
      {vals.map((v, k) => <Animated.View key={k} style={{ width: 4, height: 22, borderRadius: 2, marginHorizontal: 2, backgroundColor: color, transform: [{ scaleY: v }] }} />)}
    </View>
  );
}

/** Cream page with soft sound-wave arcs radiating from the top-right corner. */
function WaveBackdrop() {
  const { width: w, height: h } = useWindowDimensions();
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: w, height: h }}>
      <Svg width={w} height={h}>
        <Defs>
          <LinearGradient id="wb" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#F6F2E2" />
            <Stop offset="1" stopColor="#E9F0DC" />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width={w} height={h} fill="url(#wb)" />
        {[120, 190, 260, 330, 400].map((r, k) => (
          <Circle key={r} cx={w + 10} cy={70} r={r} stroke="#6FAE5F" strokeOpacity={0.14 - k * 0.02} strokeWidth={2} fill="none" />
        ))}
      </Svg>
    </View>
  );
}

/** Round floating mic (bottom-right): one tap opens full-screen voice mode and starts listening. */
function AskFab({ onClosed }: { onClosed?: () => void }) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const ring = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const l = Animated.loop(Animated.timing(ring, { toValue: 1, duration: 2200, easing: Easing.out(Easing.quad), useNativeDriver: true }));
    l.start();
    return () => l.stop();
  }, [ring]);
  return (
    <>
      <View pointerEvents="box-none" style={{ position: 'absolute', right: S.lg, bottom: S.lg, width: 76, height: 76, alignItems: 'center', justifyContent: 'center' }}>
        <Animated.View pointerEvents="none" style={{ position: 'absolute', width: 68, height: 68, borderRadius: 34, backgroundColor: C.accent, opacity: ring.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0] }), transform: [{ scale: ring.interpolate({ inputRange: [0, 1], outputRange: [1, 1.5] }) }] }} />
        <TouchableOpacity
          onPress={() => setOpen(true)}
          activeOpacity={0.85}
          accessibilityLabel={t('askTitle')}
          style={{ width: 68, height: 68, borderRadius: 34, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', shadowColor: '#0B3D24', shadowOpacity: 0.4, shadowRadius: 14, shadowOffset: { width: 0, height: 8 }, elevation: 10 }}
        >
          <Icon name="mic" size={32} color="#fff" />
        </TouchableOpacity>
      </View>
      <VoiceMode visible={open} onClose={() => { setOpen(false); onClosed?.(); }} />
    </>
  );
}

// ---------------------------------------------------------------------------
// "My questions" -- saved Ask-AI conversations
// ---------------------------------------------------------------------------
function QuestionCard({ c }: { c: Conversation }) {
  const { t } = useApp();
  return (
    <View style={{ backgroundColor: '#fff', borderRadius: 22, marginBottom: S.md, padding: S.lg, borderWidth: 1, borderColor: '#E3E8DC' }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.sm }}>
        <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: '#E8F3E8', alignItems: 'center', justifyContent: 'center', marginRight: S.sm }}>
          <Icon name="mic" size={17} color={C.accent} />
        </View>
        <Text style={{ flex: 1, fontSize: 12.5, fontWeight: '800', letterSpacing: 0.6, color: C.muted }}>{formatTime(c.ts)}</Text>
      </View>
      <Text style={{ fontSize: 16, lineHeight: 22, fontWeight: '700', color: C.text, fontStyle: 'italic' }}>{`“${c.question}”`}</Text>
      <Text style={{ fontSize: 12.5, fontWeight: '800', letterSpacing: 0.6, color: C.accent, marginTop: S.md, marginBottom: 4 }}>{t('answer').toUpperCase()}</Text>
      <Text style={{ fontSize: 15.5, lineHeight: 22, color: C.text }}>{c.answer}</Text>
    </View>
  );
}

function QuestionsList({ fieldId, reloadKey }: { fieldId: string; reloadKey: number }) {
  const { t } = useApp();
  const [items, setItems] = useState<Conversation[] | null>(null);
  useEffect(() => {
    let stop = false;
    getConversations(fieldId).then((c) => !stop && setItems(c));
    return () => { stop = true; };
  }, [fieldId, reloadKey]);
  if (items === null) return <Muted style={{ textAlign: 'center', marginTop: S.xl }}>{t('loading')}</Muted>;
  if (items.length === 0) return <Muted style={{ marginTop: S.md }}>{t('noQuestionsYet')}</Muted>;
  return <>{items.map((c) => <QuestionCard key={c.id} c={c} />)}</>;
}

// ---------------------------------------------------------------------------
// Main tab — no auto-load, blank until button tapped
// ---------------------------------------------------------------------------
export function AdviceTab() {
  const { field, t } = useApp();
  const id = field?.id;
  const [subTab, setSubTab] = useState<'recs' | 'questions'>('recs');
  const [questionsReload, setQuestionsReload] = useState(0);
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

  const [showOlder, setShowOlder] = useState(false);
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

  const sorted = [...(advisories || [])].sort((x, y) => (x.created_at < y.created_at ? 1 : -1));
  const older = sorted.slice(1, 6);

  const segTab = (key: 'recs' | 'questions', label: string) => (
    <TouchableOpacity
      key={key}
      onPress={() => setSubTab(key)}
      style={{ flex: 1, minHeight: 44, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: subTab === key ? C.accent : 'transparent' }}
    >
      <Text style={{ fontSize: 14.5, fontWeight: '800', color: subTab === key ? '#fff' : C.text }}>{label}</Text>
    </TouchableOpacity>
  );

  return (
    <View style={{ flex: 1 }}>
      <WaveBackdrop />
      <View style={{ paddingHorizontal: S.lg, paddingTop: S.md }}>
        <View style={{ flexDirection: 'row', backgroundColor: '#E4EFD9', borderRadius: 22, padding: 3 }}>
          {segTab('recs', t('adviceTabRecs'))}
          {segTab('questions', t('adviceTabQuestions'))}
        </View>
      </View>
      {subTab === 'recs' ? (
        <ScrollView
          contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: 120 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loaded && load(false)} />}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={{ fontSize: 13, fontWeight: '800', letterSpacing: 1, color: C.muted, marginBottom: S.sm }}>{t('adviceForToday').toUpperCase()}</Text>
          {createErr ? <Banner text={createErr} kind="error" /> : null}
          {!loaded ? <Muted style={{ textAlign: 'center', marginTop: S.xl }}>{t('loading')}</Muted> : null}
          {loaded && sorted.length === 0 && !creating ? <Muted>{t('noAdvisories')}</Muted> : null}
          {sorted[0] ? <AdvisoryCard key={sorted[0].id} a={sorted[0]} /> : null}

          {/* fresh advice */}
          <TouchableOpacity
            onPress={() => load(true)}
            disabled={creating}
            activeOpacity={0.85}
            style={{ minHeight: 56, borderRadius: 28, borderWidth: 2, borderColor: C.accent, backgroundColor: 'rgba(255,255,255,0.9)', alignItems: 'center', justifyContent: 'center', marginBottom: S.lg, flexDirection: 'row' }}
          >
            <Text style={{ fontSize: 20, color: C.accent, marginRight: S.sm }}>{creating ? '…' : '↻'}</Text>
            <Text style={{ fontSize: 17, fontWeight: '800', color: C.accent }}>{creating ? t('loading') : t('getAdvice')}</Text>
          </TouchableOpacity>

          {older.length ? (
            <>
              <TouchableOpacity onPress={() => setShowOlder(!showOlder)} style={{ minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ color: C.muted, fontWeight: '700', fontSize: 15 }}>{`${showOlder ? t('hideEarlier') : t('showEarlier')} (${older.length})`}</Text>
              </TouchableOpacity>
              {showOlder ? older.map((a) => <AdvisoryCard key={a.id} a={a} />) : null}
            </>
          ) : null}
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: 120 }} keyboardShouldPersistTaps="handled">
          {id ? <QuestionsList fieldId={id} reloadKey={questionsReload} /> : null}
        </ScrollView>
      )}
      <AskFab onClosed={() => setQuestionsReload((n) => n + 1)} />
    </View>
  );
}
