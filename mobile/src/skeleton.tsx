import React, { useEffect, useRef } from 'react';
import { Animated, Easing, View, ViewStyle } from 'react-native';
import { C, S } from './theme';

/** A pulsing placeholder block -- used everywhere a screen is waiting on a
 *  network response, so the app reads as "loading" instead of "frozen" or
 *  "broken" during Render's cold start / slow requests. */
export function Skeleton({ width = '100%', height = 16, radius = 6, style }: { width?: number | `${number}%`; height?: number; radius?: number; style?: ViewStyle }) {
  const opacity = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.85, duration: 650, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.35, duration: 650, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);
  return <Animated.View style={[{ width, height, borderRadius: radius, backgroundColor: C.border, opacity }, style]} />;
}

/** Skeleton shape of a Card: title bar + a couple of lines -- used while a
 *  tab's first data fetch is in flight. */
export function SkeletonCard() {
  return (
    <View style={{ borderWidth: 1, borderColor: C.border, borderRadius: 12, padding: S.lg, marginBottom: S.md, backgroundColor: C.bg }}>
      <Skeleton width="45%" height={14} style={{ marginBottom: S.md }} />
      <Skeleton width="70%" height={22} style={{ marginBottom: S.sm }} />
      <Skeleton width="90%" height={14} style={{ marginBottom: 6 }} />
      <Skeleton width="60%" height={14} />
    </View>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </>
  );
}
