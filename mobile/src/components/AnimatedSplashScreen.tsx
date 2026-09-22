import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Dimensions,
  StyleSheet,
  View,
} from 'react-native';
import { Video, ResizeMode, AVPlaybackStatus } from 'expo-av';

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

  const triggerFinish = useRef(() => {
    if (finishedRef.current) return;
    finishedRef.current = true;

    // 150ms smooth fade transition into existing app screen
    Animated.timing(fadeAnim, {
      toValue: 0,
      duration: 150,
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) {
        onFinish();
      }
    });
  }).current;

  // Fallback safety timer matching ~3.1s duration to guarantee clean transition
  useEffect(() => {
    const timer = setTimeout(() => {
      triggerFinish();
    }, 3200);
    return () => clearTimeout(timer);
  }, [triggerFinish]);

  const handlePlaybackStatusUpdate = (status: AVPlaybackStatus) => {
    if (status.isLoaded) {
      if (!videoLoaded) setVideoLoaded(true);
      if (status.didJustFinish) {
        triggerFinish();
      }
    }
  };

  return (
    <AnimatedView style={[styles.container, { opacity: fadeAnim }]} pointerEvents="none">
      <View style={styles.videoContainer}>
        <Video
          source={require('../../assets/AGR-MIRAI-LOGO-ANIMATION.mp4')}
          style={styles.video}
          resizeMode={ResizeMode.CONTAIN}
          shouldPlay
          isLooping={false}
          useNativeControls={false}
          onPlaybackStatusUpdate={handlePlaybackStatusUpdate}
        />
      </View>
    </AnimatedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    // Warm off-white background (#F4F1E4) matching the video background seamlessly
    backgroundColor: '#F4F1E4',
    alignItems: 'center',
    justifyContent: 'center',
  },
  videoContainer: {
    width: SCREEN_WIDTH,
    // Preserve 16:9 aspect ratio centered in portrait mobile layout
    height: (SCREEN_WIDTH * 9) / 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F4F1E4',
  },
  video: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F4F1E4',
  },
});
