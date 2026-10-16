import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Dimensions,
  StyleSheet,
  View,
} from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import * as SplashScreen from 'expo-splash-screen';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const AnimatedView = Animated.createAnimatedComponent(View);

interface AnimatedSplashScreenProps {
  onFinish: () => void;
  serverWaking?: boolean;
}

export function AnimatedSplashScreen({ onFinish, serverWaking = false }: AnimatedSplashScreenProps) {
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const finishedRef = useRef(false);
  const [videoLoaded, setVideoLoaded] = useState(false);

  // Android's expo-video VideoView is backed by a Surface/TextureView;
  // tearing it down on unmount can show one real black frame if the next
  // screen hasn't painted yet underneath it. Fading this component's own
  // opacity out (instead of an instant conditional swap in App.tsx) means
  // there's always something on screen during that teardown instead of
  // the bare window background.
  const triggerFinish = useRef(() => {
    if (finishedRef.current) return;
    finishedRef.current = true;

    Animated.timing(fadeAnim, {
      toValue: 0,
      duration: 220,
      useNativeDriver: true,
    }).start(() => onFinish());
  }).current;

  // Hand off from the native cold-start splash (app.json's expo-splash-
  // screen config) only once this component has actually mounted and can
  // paint the very same cream background + logo -- otherwise the native
  // splash can auto-hide a beat before anything is on screen to replace it.
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      SplashScreen.hideAsync().catch(() => {});
    });
    return () => cancelAnimationFrame(id);
  }, []);

  // Cut off playback at ~2.2s -- before the video author's dark closing fade-out
  // begins -- so the transition directly into the app background is completely seamless.
  // Timer starts only after the video is ready to play so decode latency (300-500ms)
  // does not eat into the animation window.
  useEffect(() => {
    if (!videoLoaded) return;
    const timer = setTimeout(() => {
      triggerFinish();
    }, 2250);
    return () => clearTimeout(timer);
  }, [videoLoaded, triggerFinish]);

  const player = useVideoPlayer(require('../../assets/AGR-MIRAI-LOGO-ANIMATION.mp4'), (p) => {
    p.loop = false;
    p.play();
  });

  useEffect(() => {
    const statusSub = player.addListener('statusChange', ({ status }) => {
      if (status === 'readyToPlay') setVideoLoaded(true);
      if (status === 'error') {
        console.warn('Splash video playback error');
        triggerFinish();
      }
    });
    return () => {
      statusSub.remove();
    };
  }, [player, triggerFinish]);

  return (
    <AnimatedView style={[styles.container, { opacity: fadeAnim }]} pointerEvents="none">
      <View style={styles.videoContainer}>
        <VideoView
          player={player}
          style={styles.video}
          contentFit="contain"
          nativeControls={false}
        />
      </View>
    </AnimatedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    // Warm off-white background (#F4F1E4) matching the video background seamlessly
    backgroundColor: '#F1EEE1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  videoContainer: {
    width: SCREEN_WIDTH,
    // Preserve 16:9 aspect ratio centered in portrait mobile layout
    height: (SCREEN_WIDTH * 9) / 16,
    // The logo only fills ~1/3 of the 16:9 frame; scale up so it reads at a
    // proper size on a portrait screen (frame edges are plain cream, so the
    // cropped sides are invisible).
    transform: [{ scale: 2.1 }],
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F1EEE1',
  },
  video: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F1EEE1',
  },
});
