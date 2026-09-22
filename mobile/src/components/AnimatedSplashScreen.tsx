import React, { useEffect, useRef } from 'react';
import {
  Animated,
  Dimensions,
  Easing,
  Image,
  StyleSheet,
  Text,
  View,
} from 'react-native';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const AnimatedView = Animated.createAnimatedComponent(View);
const AnimatedImage = Animated.createAnimatedComponent(Image);
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

  // --- 0.00s - 0.75s: Seed Energy Glow & Initial Entrance ---
  const seedGlowOpacity = anim.interpolate({
    inputRange: [0.0, 0.2, 0.4, 0.75, 3.0],
    outputRange: [0, 1, 0.8, 0.3, 0],
  });

  const seedScale = anim.interpolate({
    inputRange: [0.0, 0.2, 0.5, 0.75],
    outputRange: [0.3, 1.4, 1.0, 0.7],
    extrapolate: 'clamp',
  });

  // --- 0.30s - 1.45s: Logo Multi-Plane Physics Reveal ---
  // Scale Y stretch during upward launch (1.0 -> 1.15 -> 0.85 -> 1.0)
  const logoScaleY = anim.interpolate({
    inputRange: [0.0, 0.3, 0.65, 0.95, 1.2, 1.45, 3.0],
    outputRange: [0.2, 0.2, 1.16, 0.84, 1.05, 1.0, 1.0],
    extrapolate: 'clamp',
  });

  // Scale X squeeze during upward launch (1.0 -> 0.88 -> 1.12 -> 1.0)
  const logoScaleX = anim.interpolate({
    inputRange: [0.0, 0.3, 0.65, 0.95, 1.2, 1.45, 3.0],
    outputRange: [0.2, 0.2, 0.88, 1.12, 0.96, 1.0, 1.0],
    extrapolate: 'clamp',
  });

  const logoTranslateY = anim.interpolate({
    inputRange: [0.0, 0.3, 0.65, 0.95, 1.2, 1.45, 3.0],
    outputRange: [60, 60, -35, 12, -4, 0, 0],
    extrapolate: 'clamp',
  });

  const logoOpacity = anim.interpolate({
    inputRange: [0.0, 0.3, 0.6, 2.7, 3.0],
    outputRange: [0, 0, 1, 1, 0],
    extrapolate: 'clamp',
  });

  // --- 1.75s - 2.30s: Energy Sweep Beam ---
  const sweepBeamX = anim.interpolate({
    inputRange: [1.75, 2.3],
    outputRange: [-SCREEN_WIDTH * 0.5, SCREEN_WIDTH * 0.5],
    extrapolate: 'clamp',
  });

  const sweepBeamOpacity = anim.interpolate({
    inputRange: [1.75, 1.85, 2.2, 2.3],
    outputRange: [0, 1, 1, 0],
    extrapolate: 'clamp',
  });

  // --- 2.20s - 2.60s: Final Synchronized Pulse Ring & Master Scale ---
  const masterScale = anim.interpolate({
    inputRange: [0.0, 2.2, 2.38, 2.55, 3.0],
    outputRange: [1.0, 1.0, 1.025, 1.0, 1.0],
    extrapolate: 'clamp',
  });

  const pulseRingScale = anim.interpolate({
    inputRange: [2.2, 2.55],
    outputRange: [0.8, 1.3],
    extrapolate: 'clamp',
  });

  const pulseRingOpacity = anim.interpolate({
    inputRange: [2.2, 2.35, 2.55],
    outputRange: [0, 0.5, 0],
    extrapolate: 'clamp',
  });

  // Fade out overall splash screen to transition into app
  const splashFade = anim.interpolate({
    inputRange: [2.7, 3.0],
    outputRange: [1, 0],
    extrapolate: 'clamp',
  });

  return (
    <AnimatedView style={[styles.container, { opacity: splashFade }]}>
      <AnimatedView
        style={[
          styles.emblemWrapper,
          {
            transform: [{ scale: masterScale }],
          },
        ]}
      >
        {/* Ambient Seed Glow */}
        <AnimatedView
          style={[
            styles.seedGlow,
            {
              opacity: seedGlowOpacity,
              transform: [{ scale: seedScale }],
            },
          ]}
        />

        {/* Outer Synchronized Pulse Ring */}
        <AnimatedView
          style={[
            styles.pulseRing,
            {
              opacity: pulseRingOpacity,
              transform: [{ scale: pulseRingScale }],
            },
          ]}
        />

        {/* Actual Official AGRO MIRAI Logo Image with Physics-Based Transforms */}
        <AnimatedImage
          source={require('../../assets/Agro_Mirai_Logo.png')}
          style={[
            styles.logoImage,
            {
              opacity: logoOpacity,
              transform: [
                { translateY: logoTranslateY },
                { scaleY: logoScaleY },
                { scaleX: logoScaleX },
              ],
            },
          ]}
          resizeMode="contain"
        />

        {/* Energy Sweep Beam across logo */}
        <AnimatedView
          style={[
            styles.sweepBeam,
            {
              opacity: sweepBeamOpacity,
              transform: [{ translateX: sweepBeamX }],
            },
          ]}
        />
      </AnimatedView>

      {/* Tagline */}
      <AnimatedText style={[styles.taglineText, { opacity: logoOpacity }]}>
        SEED  •  GROWTH  •  INTELLIGENCE
      </AnimatedText>

      {/* Server wake badge */}
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
    backgroundColor: '#040C08', // Dark tech emerald ambient background
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  emblemWrapper: {
    width: 280,
    height: 280,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoImage: {
    width: 260,
    height: 260,
  },
  seedGlow: {
    position: 'absolute',
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: 'rgba(74, 222, 128, 0.25)',
    shadowColor: '#4ADE80',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 25,
    elevation: 12,
  },
  pulseRing: {
    position: 'absolute',
    width: 250,
    height: 250,
    borderRadius: 125,
    borderWidth: 2,
    borderColor: '#A3E635',
  },
  sweepBeam: {
    position: 'absolute',
    bottom: 25,
    width: 140,
    height: 3,
    backgroundColor: '#A3E635',
    shadowColor: '#4ADE80',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 10,
    borderRadius: 2,
    zIndex: 10,
  },
  taglineText: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 3,
    color: '#86EFAC',
    marginTop: 25,
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
