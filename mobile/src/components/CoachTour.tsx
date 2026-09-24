import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Dimensions, Easing, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { C, S } from '../theme';

export type TourStep = { key: string; title: string; body: string };
type Rect = { x: number; y: number; w: number; h: number };

const PAD = 6;
const DIM = 'rgba(16,24,16,0.72)';

/** Spotlight coach-mark tour rendered on top of the real app. For each step
 *  it measures the live element registered under `step.key`, dims everything
 *  else, rings the element, and shows a card explaining it. `getTarget`
 *  returns the View to spotlight (or null if it is not mounted). */
export function CoachTour({
  steps, getTarget, onStep, onDone, labels,
}: {
  steps: TourStep[];
  getTarget: (key: string) => View | null;
  onStep?: (key: string) => void;
  onDone: () => void;
  labels: { next: string; back: string; done: string; skip: string };
}) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const root = useRef<View>(null);
  const pulse = useRef(new Animated.Value(0)).current;
  const fade = useRef(new Animated.Value(0)).current;
  const { width: W, height: H } = Dimensions.get('window');
  const step = steps[i];

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ]),
    ).start();
  }, [pulse]);

  const measure = useCallback(() => {
    const target = getTarget(step.key);
    if (!target || !root.current) return;
    // Both measured in window coordinates, so the difference is correct
    // regardless of safe-area insets around the overlay.
    root.current.measureInWindow((ox, oy) => {
      target.measureInWindow((x, y, w, h) => {
        if (!w || !h) return;
        setRect({ x: x - ox, y: y - oy, w, h });
        fade.setValue(0);
        Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }).start();
      });
    });
  }, [getTarget, step.key, fade]);

  useEffect(() => {
    onStep?.(step.key);
    // wait a frame for the tab content behind to settle before measuring
    const id = setTimeout(measure, 80);
    return () => clearTimeout(id);
  }, [step.key, measure, onStep]);

  const last = i === steps.length - 1;
  const r = rect;
  const cardBelow = r ? r.y + r.h / 2 < H / 2 : false;
  const rx = r ? Math.max(0, r.x - PAD) : 0;
  const ry = r ? Math.max(0, r.y - PAD) : 0;
  const rw = r ? r.w + PAD * 2 : 0;
  const rh = r ? r.h + PAD * 2 : 0;

  return (
    <View ref={root} collapsable={false} style={StyleSheet.absoluteFill} pointerEvents="box-none">
      {/* Four dim panels leave a clear window over the target and swallow touches elsewhere. */}
      {r ? (
        <>
          <View style={[st.dim, { left: 0, top: 0, right: 0, height: ry }]} />
          <View style={[st.dim, { left: 0, top: ry + rh, right: 0, bottom: 0 }]} />
          <View style={[st.dim, { left: 0, top: ry, width: rx, height: rh }]} />
          <View style={[st.dim, { left: rx + rw, top: ry, right: 0, height: rh }]} />
          <Animated.View
            pointerEvents="none"
            style={{
              position: 'absolute', left: rx, top: ry, width: rw, height: rh, borderRadius: 16,
              borderWidth: 3, borderColor: '#7BC67E',
              transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.06] }) }],
              opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 0.55] }),
            }}
          />
        </>
      ) : (
        <View style={[StyleSheet.absoluteFill, { backgroundColor: DIM }]} />
      )}

      {r ? (
        <Animated.View
          style={[
            st.card,
            { opacity: fade, width: Math.min(W - S.xl * 2, 420), left: (W - Math.min(W - S.xl * 2, 420)) / 2 },
            cardBelow ? { top: ry + rh + 16 } : { bottom: Math.max(S.lg, H - ry + 16) },
          ]}
        >
          <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.sm }}>
            <View style={{ flexDirection: 'row', flex: 1, gap: 5 }}>
              {steps.map((_, n) => (
                <View key={n} style={{ height: 4, flex: 1, borderRadius: 2, backgroundColor: n <= i ? C.accent : C.border }} />
              ))}
            </View>
            <Text style={{ marginLeft: S.md, fontSize: 12, color: C.muted }}>{i + 1}/{steps.length}</Text>
          </View>
          <Text style={{ fontSize: 18, fontWeight: '700', color: C.text }}>{step.title}</Text>
          <Text style={{ fontSize: 15, lineHeight: 22, color: C.muted, marginTop: S.xs }}>{step.body}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: S.lg }}>
            {!last ? (
              <TouchableOpacity onPress={onDone} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                <Text style={{ color: C.muted, fontSize: 14 }}>{labels.skip}</Text>
              </TouchableOpacity>
            ) : null}
            <View style={{ flex: 1 }} />
            {i > 0 ? (
              <TouchableOpacity onPress={() => setI(i - 1)} style={[st.btn, { borderColor: C.border, marginRight: S.sm }]}>
                <Text style={{ color: C.text, fontWeight: '600' }}>{labels.back}</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity
              onPress={() => (last ? onDone() : setI(i + 1))}
              style={[st.btn, { backgroundColor: C.accent, borderColor: C.accent }]}
            >
              <Text style={{ color: C.accentText, fontWeight: '700' }}>{last ? labels.done : labels.next}</Text>
            </TouchableOpacity>
          </View>
        </Animated.View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  dim: { position: 'absolute', backgroundColor: DIM },
  card: {
    position: 'absolute', backgroundColor: C.bg, borderRadius: 16,
    padding: S.lg, elevation: 8, shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 4 },
  },
  btn: { borderWidth: 1, borderRadius: 10, paddingVertical: 10, paddingHorizontal: S.lg },
});
