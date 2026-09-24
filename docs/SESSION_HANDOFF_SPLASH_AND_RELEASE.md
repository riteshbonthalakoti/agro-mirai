# Session Handoff — Video Splash Screen, Release v1.3.0 & Native Plugin Fix

**Date:** 2026-09-23  
**Status:** In Progress / Ready for Final APK Build  
**Key Deliverables:** 
1. Mobile App Video Splash Screen (`AGR-MIRAI-LOGO-ANIMATION.mp4` via `expo-av`)
2. Release Build `v1.3.0` on GitHub Releases
3. Android Gradle JDK 17+ CMake build issue resolved
4. Release crash fix applied (`expo-av` registered in `mobile/app.json`)

---

## 1. Executive Summary & Quick Context for Next Session

If starting a new chat session or handover:
- **What was done:** The brand animation video (`mobile/assets/AGR-MIRAI-LOGO-ANIMATION.mp4`, 1920x1080, 16:9, ~3 sec) was integrated as the mobile app splash screen.
- **Android Gradle build fixes:** Configured JVM `--add-opens` flags in `mobile/android/gradle.properties` and restricted `abiFilters` to `"arm64-v8a"` in `mobile/android/app/build.gradle` to solve CMake compilation errors under JDK 17+.
- **Release v1.3.0 Published:** Created GitHub release `v1.3.0` at `https://github.com/riteshbonthalakoti/agro-mirai/releases/tag/v1.3.0`.
- **CRITICAL DISCOVERY:** The app crashed immediately upon launch on physical devices because `expo-av` was missing from the `plugins` array in `mobile/app.json`! Expo autolinking requires native plugins listed in `app.json` to include native Java/Kotlin bindings in standalone release APKs.
- **Fix Applied:** `"expo-av"` has been added to `mobile/app.json`.
- **NEXT IMMEDIATE STEP:** Re-run `.\gradlew.bat assembleRelease` in `mobile/android` and re-upload the fixed `app-release.apk` to GitHub Release `v1.3.0`.

---

## 2. Video Splash Screen Implementation (`mobile/src/components/AnimatedSplashScreen.tsx`)

### Design & Behavior Requirements
- **Video Asset:** `mobile/assets/AGR-MIRAI-LOGO-ANIMATION.mp4` (1920x1080, 16:9 aspect ratio, ~3s).
- **Presentation:**
  - Portrait mobile orientation containment (`ResizeMode.CONTAIN`).
  - Centered vertically and horizontally.
  - Background color set to `#F4F1E4` matching the video's warm off-white background seamlessly.
  - No borders, cards, rounded corners, or extra UI elements.
- **Lifecycle:**
  - Starts automatically on app boot phase (`App.tsx`).
  - Plays exactly once (`isLooping={false}`).
  - Crossfades smoothly (150ms duration) into the application UI upon completion (`status.didJustFinish`).
  - Includes a 3.2s fallback safety timer in case playback events fail to fire.

### Key Code Structure
```tsx
// mobile/src/components/AnimatedSplashScreen.tsx
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Dimensions, StyleSheet, View } from 'react-native';
import { Video, ResizeMode, AVPlaybackStatus } from 'expo-av';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const AnimatedView = Animated.createAnimatedComponent(View);

export function AnimatedSplashScreen({ onFinish }: AnimatedSplashScreenProps) {
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const finishedRef = useRef(false);

  const triggerFinish = useRef(() => {
    if (finishedRef.current) return;
    finishedRef.current = true;
    Animated.timing(fadeAnim, {
      toValue: 0,
      duration: 150,
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) onFinish();
    });
  }).current;

  // ...
  return (
    <AnimatedView style={[styles.container, { opacity: fadeAnim }]}>
      <View style={styles.videoContainer}>
        <Video
          source={require('../../assets/AGR-MIRAI-LOGO-ANIMATION.mp4')}
          style={styles.video}
          resizeMode={ResizeMode.CONTAIN}
          shouldPlay
          isLooping={false}
          onPlaybackStatusUpdate={handlePlaybackStatusUpdate}
        />
      </View>
    </AnimatedView>
  );
}
```

---

## 3. Android Gradle Build Troubleshooting & Resolution

During release APK compilation (`.\gradlew.bat assembleRelease`), two major build errors occurred:

### Issue A: CMake Configuration Failure under JDK 17+
- **Error:** `Execution failed for task ':app:configureCMakeRelWithDebInfo[armeabi-v7a]'` with `WARNING: A restricted method in java.lang.System has been called`.
- **Root Cause:** JDK 17+ strictly enforces module encapsulation, blocking legacy reflective/System calls made by older CMake Gradle plugins.
- **Fix:** Added JVM module access flags to `mobile/android/gradle.properties`:
  ```properties
  org.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=512m --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED
  ```

### Issue B: CMake Failure on `x86_64` Architecture
- **Error:** `configureCMakeRelWithDebInfo[x86_64]` failed, whereas `arm64-v8a` succeeded.
- **Root Cause:** 32-bit and emulator-oriented native libs had broken toolchain references under JDK 17.
- **Fix:** Modified `mobile/android/app/build.gradle` to target `arm64-v8a` explicitly (covers 99%+ of modern physical Android devices):
  ```groovy
  ndk {
      abiFilters "arm64-v8a"
  }
  ```

---

## 4. Crash Root Cause & Fix (`app.json`)

### Problem Observed
When the APK was installed and opened on a physical phone, the app crashed immediately upon launch.

### Diagnosis
- `expo-av` component `<Video />` requires native C++/Java media player modules (`ExpoAVPackage`).
- In Expo React Native projects, native packages **must** be declared in `mobile/app.json` under `"plugins"`.
- Checking `mobile/app.json` revealed `expo-av` was missing from the `plugins` array.

### Fix Applied
1. Updated `mobile/app.json`:
```json
    "plugins": [
      "expo-av",
      "expo-audio",
      [
        "expo-camera",
        {
          "cameraPermission": "Agro Mirai needs camera access to scan crop leaves for disease detection."
        }
      ],
      "expo-asset",
      "./plugins/withCleartextTraffic",
      "expo-font",
      "@react-native-community/datetimepicker"
    ]
```

2. Added `onError` handler to `<Video />` in `mobile/src/components/AnimatedSplashScreen.tsx` as a fallback safeguard so if any video playback error occurs, it smoothly transitions to main app instead of crashing/hanging.

3. Added `buildFeatures { prefab false }` to `mobile/android/app/build.gradle` to prevent JDK 21 / JBR Prefab CLI reflection warnings during CMake tasks.

---

## 5. Next Steps for Upcoming Session / Rebuild

To complete the release:

1. **Clean & Rebuild Release APK:**
   ```powershell
   cd mobile/android
   .\gradlew.bat assembleRelease
   ```
2. **Update GitHub Release Asset:**
   Upload the freshly compiled `mobile/android/app/build/outputs/apk/release/app-release.apk` to GitHub Release tag `v1.3.0`:
   ```powershell
   gh release upload v1.3.0 "app\build\outputs\apk\release\app-release.apk#AGRO-MIRAI-v1.3.0.apk" --clobber
   ```
3. **Verify on Device:**
   Install on Android phone via `adb install` or direct download link and test splash animation & seamless transition to main screen.

