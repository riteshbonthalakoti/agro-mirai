import React, { useEffect, useRef } from 'react';
import {
  Animated,
  Dimensions,
  Easing,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Svg, {
  Circle,
  Defs,
  LinearGradient,
  Path,
  Stop,
} from 'react-native-svg';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Wrapped Animated components for SVG elements
const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedPath = Animated.createAnimatedComponent(Path);
const AnimatedView = Animated.createAnimatedComponent(View);
const AnimatedText = Animated.createAnimatedComponent(Text);

interface AnimatedSplashScreenProps {
  onFinish: () => void;
  serverWaking?: boolean;
}

export function AnimatedSplashScreen({ onFinish, serverWaking = false }: AnimatedSplashScreenProps) {
  // Master timeline animation value (0.00 to 3.00 seconds)
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(anim, {
      toValue: 3.0,
      duration: 3000,
      easing: Easing.bezier(0.25, 0.1, 0.25, 1.0),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) {
        onFinish();
      }
    });
  }, [anim, onFinish]);

  // --- 0.00s - 0.30s: Seed Point Appearance & Subtle Pulse ---
  const seedOpacity = anim.interpolate({
    inputRange: [0.0, 0.1, 0.3, 0.75, 3.0],
    outputRange: [0, 1, 0.9, 0.4, 0],
  });

  const seedScale = anim.interpolate({
    inputRange: [0.0, 0.15, 0.3, 0.75],
    outputRange: [0.2, 1.3, 1.0, 0.8],
    extrapolate: 'clamp',
  });

  // --- 0.30s - 0.75s: Field Lines & Digital Energy Trail ---
  const fieldLineProgress = anim.interpolate({
    inputRange: [0.3, 0.75],
    outputRange: [320, 0], // strokeDashoffset
    extrapolate: 'clamp',
  });

  const fieldLineOpacity = anim.interpolate({
    inputRange: [0.0, 0.3, 0.4, 2.55, 3.0],
    outputRange: [0, 0, 1, 1, 0],
  });

  // Energy point travelling along lower field arc
  const seedTranslateX = anim.interpolate({
    inputRange: [0.3, 0.75],
    outputRange: [-60, 60],
    extrapolate: 'clamp',
  });

  // --- 0.75s - 1.15s: Stem Growth & Organic Leaf Overshoot ---
  const stemScaleY = anim.interpolate({
    inputRange: [0.75, 0.95],
    outputRange: [0.01, 1.0],
    extrapolate: 'clamp',
  });

  // Left leaf grows first (0.80s - 1.05s) with organic overshoot (0 -> 1.15 -> 1.0)
  const leftLeafScale = anim.interpolate({
    inputRange: [0.8, 0.98, 1.08],
    outputRange: [0.01, 1.15, 1.0],
    extrapolate: 'clamp',
  });

  // Right leaf arrives ~90ms later (0.89s - 1.14s)
  const rightLeafScale = anim.interpolate({
    inputRange: [0.89, 1.07, 1.15],
    outputRange: [0.01, 1.15, 1.0],
    extrapolate: 'clamp',
  });

  // --- 1.15s - 1.45s: Outer Circular Ecosystem Emblem ---
  const circleDashOffset = anim.interpolate({
    inputRange: [1.15, 1.45],
    outputRange: [471, 0], // Circumference = 2 * PI * 75 ≈ 471
    extrapolate: 'clamp',
  });

  const emblemOpacity = anim.interpolate({
    inputRange: [0.0, 0.75, 0.85, 2.7, 3.0],
    outputRange: [0, 0, 1, 1, 0],
  });

  // --- 1.45s - 1.75s: Tech Nodes & Interconnect Pulses ---
  const node1Opacity = anim.interpolate({
    inputRange: [1.45, 1.55, 3.0],
    outputRange: [0.2, 1.0, 1.0],
    extrapolate: 'clamp',
  });

  const node2Opacity = anim.interpolate({
    inputRange: [1.53, 1.63, 3.0],
    outputRange: [0.2, 1.0, 1.0],
    extrapolate: 'clamp',
  });

  const nodePulseScale = anim.interpolate({
    inputRange: [1.45, 1.6, 1.75, 2.2, 2.4, 2.55],
    outputRange: [1.0, 1.4, 1.0, 1.0, 1.3, 1.0],
    extrapolate: 'clamp',
  });

  const circuitDashOffset = anim.interpolate({
    inputRange: [1.55, 1.75],
    outputRange: [120, 0],
    extrapolate: 'clamp',
  });

  // --- 1.75s - 2.20s: AGRO MIRAI Wordmark Energy Sweep ---
  const agroOpacity = anim.interpolate({
    inputRange: [1.75, 1.95],
    outputRange: [0, 1],
    extrapolate: 'clamp',
  });

  const miraiOpacity = anim.interpolate({
    inputRange: [1.84, 2.05],
    outputRange: [0, 1],
    extrapolate: 'clamp',
  });

  const sweepBeamX = anim.interpolate({
    inputRange: [1.75, 2.15],
    outputRange: [-SCREEN_WIDTH * 0.4, SCREEN_WIDTH * 0.4],
    extrapolate: 'clamp',
  });

  const sweepBeamOpacity = anim.interpolate({
    inputRange: [1.75, 1.8, 2.1, 2.2],
    outputRange: [0, 1, 1, 0],
    extrapolate: 'clamp',
  });

  const taglineOpacity = anim.interpolate({
    inputRange: [2.05, 2.25],
    outputRange: [0, 1],
    extrapolate: 'clamp',
  });

  // --- 2.20s - 2.55s: Brand Lock & Settling (100% -> 102% -> 100%) ---
  const brandScale = anim.interpolate({
    inputRange: [0.0, 2.2, 2.38, 2.55, 3.0],
    outputRange: [1.0, 1.0, 1.025, 1.0, 1.0],
    extrapolate: 'clamp',
  });

  const finalPulseRing = anim.interpolate({
    inputRange: [2.2, 2.45, 2.55],
    outputRange: [0.8, 1.2, 1.0],
    extrapolate: 'clamp',
  });

  const finalPulseOpacity = anim.interpolate({
    inputRange: [2.2, 2.35, 2.55],
    outputRange: [0, 0.6, 0],
    extrapolate: 'clamp',
  });

  // Fade out overall splash screen to transition smoothly into app
  const splashFade = anim.interpolate({
    inputRange: [2.7, 3.0],
    outputRange: [1, 0],
    extrapolate: 'clamp',
  });

  return (
    <AnimatedView style={[styles.container, { opacity: splashFade }]}>
      <AnimatedView style={[styles.emblemWrapper, { transform: [{ scale: brandScale }] }]}>
        <Svg width={240} height={240} viewBox="0 0 240 240">
          <Defs>
            <LinearGradient id="emeraldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <Stop offset="0%" stopColor="#86EFAC" stopOpacity="1" />
              <Stop offset="50%" stopColor="#4ADE80" stopOpacity="1" />
              <Stop offset="100%" stopColor="#22C55E" stopOpacity="1" />
            </LinearGradient>
          </Defs>

          {/* --- 1.15s-1.45s: Outer Circular Ecosystem Emblem --- */}
          <AnimatedCircle
            cx={120}
            cy={115}
            r={75}
            stroke="url(#emeraldGrad)"
            strokeWidth={2.5}
            fill="none"
            strokeDasharray={471}
            strokeDashoffset={circleDashOffset as any}
            strokeLinecap="round"
            opacity={emblemOpacity as any}
          />

          {/* Background ambient ring */}
          <Circle
            cx={120}
            cy={115}
            r={75}
            stroke="#15803D"
            strokeWidth={1.2}
            strokeOpacity={0.25}
            fill="none"
          />

          {/* --- 0.30s-0.75s: Lower Agricultural Field Curves --- */}
          <AnimatedPath
            d="M 45 160 C 80 142, 160 142, 195 160"
            stroke="#4ADE80"
            strokeWidth={2}
            strokeLinecap="round"
            fill="none"
            strokeDasharray={320}
            strokeDashoffset={fieldLineProgress as any}
            opacity={fieldLineOpacity as any}
          />
          <AnimatedPath
            d="M 55 174 C 90 158, 150 158, 185 174"
            stroke="#22C55E"
            strokeWidth={1.5}
            strokeLinecap="round"
            fill="none"
            strokeDasharray={320}
            strokeDashoffset={fieldLineProgress as any}
            opacity={fieldLineOpacity as any}
          />

          {/* --- 0.75s-1.15s: Central Stem --- */}
          <AnimatedPath
            d="M 120 160 L 120 80"
            stroke="#4ADE80"
            strokeWidth={2.5}
            strokeLinecap="round"
            fill="none"
            opacity={emblemOpacity as any}
          />

          {/* --- 0.75s-1.15s: Organic Leaves (Left then Right) --- */}
          {/* Left Leaf */}
          <AnimatedPath
            d="M 120 120 C 92 100, 78 112, 88 132 C 102 136, 116 126, 120 120 Z"
            fill="#4ADE80"
            fillOpacity={0.85}
            stroke="#86EFAC"
            strokeWidth={1.2}
            opacity={leftLeafScale as any}
          />

          {/* Right Leaf */}
          <AnimatedPath
            d="M 120 105 C 148 85, 162 97, 152 117 C 138 121, 124 111, 120 105 Z"
            fill="#22C55E"
            fillOpacity={0.85}
            stroke="#4ADE80"
            strokeWidth={1.2}
            opacity={rightLeafScale as any}
          />

          {/* --- 1.45s-1.75s: Interconnecting Technology Circuit Lines --- */}
          <AnimatedPath
            d="M 88 95 L 120 65 L 152 95"
            stroke="#A3E635"
            strokeWidth={1.4}
            strokeDasharray={120}
            strokeDashoffset={circuitDashOffset as any}
            strokeLinecap="round"
            fill="none"
            opacity={node1Opacity as any}
          />

          {/* --- 1.45s-1.75s: Tech Nodes (Node 1, Node 2, Top Node) --- */}
          <AnimatedCircle
            cx={88}
            cy={95}
            r={3.5}
            fill="#A3E635"
            opacity={node1Opacity as any}
          />
          <AnimatedCircle
            cx={152}
            cy={95}
            r={3.5}
            fill="#A3E635"
            opacity={node2Opacity as any}
          />
          <AnimatedCircle
            cx={120}
            cy={65}
            r={4}
            fill="#4ADE80"
            opacity={node2Opacity as any}
          />

          {/* --- 2.20s-2.55s: Synchronized Final Pulse Wave Ring --- */}
          <AnimatedCircle
            cx={120}
            cy={115}
            r={82}
            stroke="#A3E635"
            strokeWidth={2}
            fill="none"
            opacity={finalPulseOpacity as any}
          />
        </Svg>

        {/* --- 0.00s-0.30s: Traveling Seed Energy Point --- */}
        <AnimatedView
          style={[
            styles.seedPoint,
            {
              opacity: seedOpacity,
              transform: [
                { translateX: seedTranslateX },
                { scale: seedScale },
              ],
            },
          ]}
        />
      </AnimatedView>

      {/* --- 1.75s-2.20s: AGRO MIRAI Wordmark Reveal --- */}
      <View style={styles.wordmarkContainer}>
        {/* Horizontal Energy Sweep Indicator */}
        <AnimatedView
          style={[
            styles.sweepBeam,
            {
              opacity: sweepBeamOpacity,
              transform: [{ translateX: sweepBeamX }],
            },
          ]}
        />

        <View style={styles.textRow}>
          <AnimatedText style={[styles.agroText, { opacity: agroOpacity }]}>
            AGRO
          </AnimatedText>
          <AnimatedText style={[styles.miraiText, { opacity: miraiOpacity }]}>
            {' '}MIRAI
          </AnimatedText>
        </View>

        <AnimatedText style={[styles.taglineText, { opacity: taglineOpacity }]}>
          SEED  •  GROWTH  •  INTELLIGENCE
        </AnimatedText>
      </View>

      {/* Server wake indicator during splash hold if server is waking up */}
      {serverWaking ? (
        <AnimatedView style={styles.wakingBadge}>
          <Text style={styles.wakingText}>Connecting to AGRO MIRAI Cloud...</Text>
        </AnimatedView>
      ) : null}
    </AnimatedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0A120A', // Deep luxurious dark tech green
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  emblemWrapper: {
    width: 240,
    height: 240,
    alignItems: 'center',
    justifyContent: 'center',
  },
  seedPoint: {
    position: 'absolute',
    bottom: 60,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#A3E635',
    shadowColor: '#4ADE80',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 10,
    elevation: 8,
  },
  wordmarkContainer: {
    marginTop: 35,
    alignItems: 'center',
    overflow: 'hidden',
    paddingVertical: 10,
  },
  sweepBeam: {
    position: 'absolute',
    top: 15,
    width: 120,
    height: 3,
    backgroundColor: '#A3E635',
    shadowColor: '#4ADE80',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 8,
    borderRadius: 2,
    zIndex: 10,
  },
  textRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  agroText: {
    fontSize: 34,
    fontWeight: '800',
    letterSpacing: 4,
    color: '#ECFDF5',
  },
  miraiText: {
    fontSize: 34,
    fontWeight: '800',
    letterSpacing: 4,
    color: '#4ADE80',
  },
  taglineText: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 3,
    color: '#86EFAC',
    marginTop: 10,
    opacity: 0.9,
  },
  wakingBadge: {
    position: 'absolute',
    bottom: 40,
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(74, 222, 128, 0.3)',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  wakingText: {
    fontSize: 12,
    color: '#86EFAC',
    fontWeight: '500',
  },
});
