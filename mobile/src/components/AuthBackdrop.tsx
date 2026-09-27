import React from 'react';
import { View, useWindowDimensions } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

/** Soft backdrop for the sign-in page: a pale sunrise-to-cream sky, and faint line-art leaves. Pure vector (no image download, tiny, sharp
 *  on every screen). `pointerEvents="none"` so it never blocks the form. */
const LEAF = 'M0 0 C 10 -14 26 -16 40 -8 C 30 6 12 10 0 0 Z M0 0 L 34 -7';

const LEAVES: { x: number; y: number; r: number; s: number }[] = [
  { x: 0.08, y: 0.1, r: -25, s: 1.1 }, { x: 0.78, y: 0.07, r: 30, s: 0.9 }, { x: 0.9, y: 0.32, r: 70, s: 1.0 },
  { x: 0.05, y: 0.42, r: 15, s: 0.8 }, { x: 0.62, y: 0.5, r: -50, s: 0.7 }, { x: 0.22, y: 0.6, r: 40, s: 0.9 },
];

export function AuthBackdrop() {
  const { width: w, height: h } = useWindowDimensions();
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: w, height: h, backgroundColor: '#F1EEE1' }}>
      <Svg width={w} height={h}>
        <Defs>
          <LinearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#F8F3DF" />
            <Stop offset="0.6" stopColor="#F3F0E3" />
            <Stop offset="1" stopColor="#E4EFD9" />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width={w} height={h} fill="url(#sky)" />

        {/* line-art leaves */}
        {LEAVES.map((l, i) => (
          <Path
            key={i}
            d={LEAF}
            transform={`translate(${l.x * w} ${l.y * h}) rotate(${l.r}) scale(${l.s * 1.4})`}
            stroke="#5E9D5A"
            strokeOpacity={0.4}
            strokeWidth={1.8}
            fill="none"
            strokeLinecap="round"
          />
        ))}

      </Svg>
    </View>
  );
}
