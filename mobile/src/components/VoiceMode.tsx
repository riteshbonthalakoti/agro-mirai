import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Easing, Modal, ScrollView, Text, TouchableOpacity, View, useWindowDimensions } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import { ApiError, AskResult, askByVoice } from '../api';
import { playBase64, speakOnDevice, stopAudio } from '../audio';
import { useApp } from '../ctx';
import { errorText } from '../hooks';
import { feedback } from '../feedback';
import { Icon } from '../../icons';
import { C, S } from '../theme';

type VState = 'idle' | 'listening' | 'thinking' | 'speaking';

const ORB = 250;
const GREEN = { a: '#34D399', b: '#A3E635', c: '#22C55E', d: '#2DD4BF' };
// how fast the blobs drift per state (ms per turn): calm -> lively -> busy
const SPIN: Record<VState, [number, number, number]> = {
  idle: [18000, 25000, 32000],
  listening: [9000, 12000, 15000],
  thinking: [3000, 4000, 5200],
  speaking: [7000, 9500, 12000],
};

/** Fluid orb: three translucent blobs orbiting inside a soft glow. Loudness (0..1) swells it
 *  quickly and lets it settle slowly, like the big assistants' voice modes. */
function Orb({ state, level }: { state: VState; level: Animated.Value }) {
  const breath = useRef(new Animated.Value(0)).current;
  const spins = useRef([new Animated.Value(0), new Animated.Value(0), new Animated.Value(0)]).current;

  useEffect(() => {
    const b = Animated.loop(Animated.sequence([
      Animated.timing(breath, { toValue: 1, duration: state === 'speaking' ? 900 : 2600, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      Animated.timing(breath, { toValue: 0, duration: state === 'speaking' ? 900 : 2600, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
    ]));
    b.start();
    return () => b.stop();
  }, [state, breath]);

  useEffect(() => {
    const loops = spins.map((v, k) => {
      v.setValue(0);
      return Animated.loop(Animated.timing(v, { toValue: 1, duration: SPIN[state][k], easing: Easing.linear, useNativeDriver: true }));
    });
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [state, spins]);

  const swell = level.interpolate({ inputRange: [0, 1], outputRange: [0, 0.3] });
  const amp = state === 'speaking' ? 0.07 : state === 'idle' ? 0.035 : 0.05;
  const scale = Animated.add(1, Animated.add(breath.interpolate({ inputRange: [0, 1], outputRange: [0, amp] }), swell));
  const glowScale = Animated.add(1.05, Animated.multiply(level, 0.5));
  const rot = (v: Animated.Value, dir = 1) => v.interpolate({ inputRange: [0, 1], outputRange: dir > 0 ? ['0deg', '360deg'] : ['360deg', '0deg'] });

  const blob = (k: number, color: string, size: number, dx: number, dy: number, dir: number) => (
    <Animated.View key={k} style={{ position: 'absolute', width: ORB, height: ORB, alignItems: 'center', justifyContent: 'center', transform: [{ rotate: rot(spins[k], dir) }] }}>
      <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color, opacity: 0.6, transform: [{ translateX: dx }, { translateY: dy }] }} />
    </Animated.View>
  );

  return (
    <View style={{ width: ORB + 70, height: ORB + 70, alignItems: 'center', justifyContent: 'center' }}>
      <Animated.View style={{ position: 'absolute', width: ORB * 1.15, height: ORB * 1.15, borderRadius: ORB, backgroundColor: GREEN.a, opacity: state === 'idle' ? 0.16 : 0.26, transform: [{ scale: glowScale }] }} />
      <Animated.View style={{ width: ORB, height: ORB, borderRadius: ORB / 2, overflow: 'hidden', backgroundColor: '#1F9D62', alignItems: 'center', justifyContent: 'center', transform: [{ scale }], shadowColor: '#16A34A', shadowOpacity: 0.55, shadowRadius: 40, shadowOffset: { width: 0, height: 12 }, elevation: 16 }}>
        {blob(0, GREEN.b, ORB * 0.66, ORB * 0.16, -ORB * 0.06, 1)}
        {blob(1, GREEN.d, ORB * 0.7, -ORB * 0.15, ORB * 0.1, -1)}
        {blob(2, GREEN.a, ORB * 0.6, ORB * 0.04, ORB * 0.2, 1)}
        {/* soft highlight */}
        <View style={{ position: 'absolute', top: ORB * 0.1, left: ORB * 0.2, width: ORB * 0.42, height: ORB * 0.22, borderRadius: ORB * 0.2, backgroundColor: '#fff', opacity: 0.22, transform: [{ rotate: '-24deg' }] }} />
      </Animated.View>
    </View>
  );
}

/** Full-screen voice mode: a big living orb, live captions, one control. Tapping while it is
 *  talking interrupts it and starts listening again. */
export function VoiceMode({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { t, lang } = useApp();
  const tt = (k: string) => (t as any)(k) as string;
  const { height: h } = useWindowDimensions();
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const rs = useAudioRecorderState(recorder, 80);
  const [state, setState] = useState<VState>('idle');
  const [res, setRes] = useState<AskResult | null>(null);
  const [err, setErr] = useState('');
  const [offline, setOffline] = useState(false);
  const stateRef = useRef<VState>('idle');
  const level = useRef(new Animated.Value(0)).current;
  const lastLevel = useRef(0);
  const heard = useRef(false);
  const lastLoud = useRef(0);
  const capTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setVS = (s: VState) => { stateRef.current = s; setState(s); };

  // mic loudness -> orb (fast attack, slow release)
  useEffect(() => {
    const db = rs.metering;
    const lv = stateRef.current === 'listening' && typeof db === 'number' ? Math.max(0, Math.min(1, (db + 52) / 52)) : 0;
    const up = lv > lastLevel.current;
    lastLevel.current = lv;
    Animated.timing(level, { toValue: lv, duration: up ? 60 : 240, easing: Easing.out(Easing.quad), useNativeDriver: true }).start();
    // a pause of about 2 s after the farmer has spoken sends the question automatically
    if (stateRef.current === 'listening' && typeof db === 'number') {
      if (db > -38) { heard.current = true; lastLoud.current = Date.now(); }
      else if (heard.current && Date.now() - lastLoud.current > 2000) stopAndSend();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rs.metering]);

  const startListening = useCallback(async () => {
    setErr(''); setRes(null); setOffline(false);
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) { setErr(tt('micPerm')); setVS('idle'); return; }
    await stopAudio(); // interrupts the answer if it was still playing
    try {
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      heard.current = false; lastLoud.current = Date.now();
      recorder.record();
      feedback.tap();
      setVS('listening');
      if (capTimer.current) clearTimeout(capTimer.current);
      capTimer.current = setTimeout(() => { if (stateRef.current === 'listening') stopAndSend(); }, 45000);
    } catch {
      setErr(tt('captureFailed')); setVS('idle');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder]);

  const stopAndSend = async () => {
    if (stateRef.current !== 'listening') return;
    if (capTimer.current) clearTimeout(capTimer.current);
    setVS('thinking');
    feedback.select();
    try {
      await recorder.stop();
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      const uri = recorder.uri;
      if (!uri) throw new ApiError(0, 'no recording');
      const r = await askByVoice(uri, 'audio/mp4', lang);
      setRes(r);
      feedback.success();
      setVS('speaking');
      if (r.answer_audio_base64) {
        await playBase64(r.answer_audio_base64, r.answer_audio_mimetype, () => setVS('idle'));
      } else if (r.answer_text) {
        // server voice unavailable: read the answer with the phone's own voice, and say so
        const ok = await speakOnDevice(r.answer_text, lang, () => setVS('idle'));
        if (ok) setOffline(true); else setVS('idle');
      } else setVS('idle');
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.status === 503 ? tt('askUnavailable') : ae.status === -1 ? tt('captureFailed') : errorText(t, ae));
      setVS('idle');
    }
  };

  const onMain = () => {
    if (state === 'idle' || state === 'speaking') startListening();
    else if (state === 'listening') stopAndSend();
  };

  const close = () => {
    if (capTimer.current) clearTimeout(capTimer.current);
    stopAudio().catch(() => {});
    if (stateRef.current === 'listening') recorder.stop().catch(() => {});
    setVS('idle'); setRes(null); setErr(''); setOffline(false);
    onClose();
  };

  // open straight into listening: one tap on the floating mic and the farmer can speak
  useEffect(() => {
    if (visible) startListening();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const status =
    err ? tt('voiceCouldntHear') :
    state === 'idle' ? tt('voiceTapSpeak') :
    state === 'listening' ? tt('voiceListening') :
    state === 'thinking' ? tt('voiceThinking') : tt('voiceSpeaking');
  const sub =
    err ? err :
    state === 'listening' ? tt('voiceListeningHint') :
    state === 'speaking' ? tt('voiceInterrupt') :
    state === 'idle' && !res ? tt('askIdle') : '';

  return (
    <Modal visible={visible} animationType="fade" statusBarTranslucent onRequestClose={close}>
      <View style={{ flex: 1, backgroundColor: '#F1F6EA' }}>
        <Svg width="100%" height="100%" style={{ position: 'absolute' }}>
          <Defs>
            <LinearGradient id="vg" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#F8F4E4" />
              <Stop offset="0.55" stopColor="#EAF3DD" />
              <Stop offset="1" stopColor="#D5EAD0" />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#vg)" />
        </Svg>

        {/* top bar */}
        <View style={{ paddingTop: 52, paddingHorizontal: S.lg, flexDirection: 'row', alignItems: 'center' }}>
          <TouchableOpacity onPress={close} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }} accessibilityLabel={tt('close')} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.85)', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="close" size={20} color={C.text} />
          </TouchableOpacity>
          <Text style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: '800', color: C.text }}>{tt('askTitle')}</Text>
          <View style={{ width: 44 }} />
        </View>

        {/* orb + status */}
        <View style={{ alignItems: 'center', marginTop: res ? 0 : S.lg }}>
          <TouchableOpacity activeOpacity={0.95} onPress={onMain} disabled={state === 'thinking'} style={{ transform: [{ scale: res ? 0.66 : 1 }], marginVertical: res ? -46 : 0 }}>
            <Orb state={state} level={level} />
          </TouchableOpacity>
          <Text style={{ fontSize: 26, fontWeight: '800', color: C.text, marginTop: res ? S.md : 0 }}>{status}</Text>
          {sub ? <Text style={{ fontSize: 16, lineHeight: 23, color: err ? C.danger : C.muted, textAlign: 'center', marginTop: S.xs, paddingHorizontal: S.xl }}>{sub}</Text> : null}
          {offline && state === 'speaking' ? <Text style={{ fontSize: 13, color: C.muted, marginTop: 4 }}>{tt('voiceFallbackToast')}</Text> : null}
        </View>

        {/* captions */}
        <ScrollView style={{ flex: 1, marginTop: S.md }} contentContainerStyle={{ paddingHorizontal: S.lg, paddingBottom: S.lg }} showsVerticalScrollIndicator={false}>
          {res ? (
            <>
              <Text style={{ fontSize: 15, lineHeight: 22, color: C.muted, fontStyle: 'italic', textAlign: 'center' }}>{`“${res.question_text}”`}</Text>
              <View style={{ backgroundColor: 'rgba(255,255,255,0.92)', borderRadius: 22, padding: S.lg, marginTop: S.md, borderWidth: 1, borderColor: '#DDE7D3' }}>
                <Text style={{ fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, color: C.accent, marginBottom: 6 }}>{tt('answer').toUpperCase()}</Text>
                <Text style={{ fontSize: 17.5, lineHeight: 26, color: C.text }}>{res.answer_text}</Text>
              </View>
            </>
          ) : null}
        </ScrollView>

        {/* one control */}
        <View style={{ alignItems: 'center', paddingBottom: 44, paddingTop: S.sm }}>
          <TouchableOpacity
            onPress={onMain}
            disabled={state === 'thinking'}
            activeOpacity={0.85}
            accessibilityLabel={state === 'listening' ? tt('voiceSend') : tt('askTitle')}
            style={{ width: 76, height: 76, borderRadius: 38, backgroundColor: state === 'listening' ? '#fff' : C.accent, borderWidth: state === 'listening' ? 3 : 0, borderColor: C.accent, alignItems: 'center', justifyContent: 'center', opacity: state === 'thinking' ? 0.5 : 1, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 8 }}
          >
            {state === 'listening' ? <View style={{ width: 26, height: 26, borderRadius: 7, backgroundColor: C.accent }} /> : <Icon name="mic" size={34} color="#fff" />}
          </TouchableOpacity>
          <Text style={{ fontSize: 14, color: C.muted, marginTop: S.sm }}>
            {state === 'listening' ? tt('voiceSend') : state === 'speaking' ? tt('voiceInterruptBtn') : res || err ? tt('voiceAskAgain') : ''}
          </Text>
        </View>
      </View>
    </Modal>
  );
}
