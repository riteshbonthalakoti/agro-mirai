# AGRO MIRAI v2.3.0 — Farmer Action Cards & Standalone Native Release Build

## 🌾 Highlights & New Features

### 1. Farmer Action Cards (Advice Tab Overhaul)
- **High-Impact Action Callout**: Each advisory category (Crop Recommendation, Irrigation, Disease Risk) now begins with a bold `✓ ACTION` or `⚠️ RECOMMENDED ACTION` box specifying the immediate, practical step for the farmer.
- **Glanceable Metric Chips**: Replaced dense text with quick-glance chips showing critical numbers:
  - 💧 **Soil Moisture:** `%`
  - 💧 **Water Need:** `mm`
  - 🌧️ **Expected Rain:** `mm`
  - 🌡️ **Temperature:** `°C`
  - 💨 **Humidity:** `%`
  - 🌱 **Soil pH:** `X.X`
- **Clean Bulleted Structure**: Secondary advice and rationale are bulleted rather than rendered as dense paragraphs.
- **Audio & Multilingual Support**: Listen button with real-time equalizer bars, multilingual Indic translation (English, Hindi, Kannada, Telugu), and instant feedback rating.

### 2. Action-Oriented AI Model Prompt
- Grounded prompt in `src/agro_mirai/api/voice_client.py` instructs the AI to speak directly to the farmer:
  - Answers specify **WHAT to do, WHEN, and HOW MUCH**.
  - Eliminates academic textbook jargon, filler phrases, and passive voice.
  - Keeps answers short (2–3 clear sentences) optimized for crystal-clear TTS read-aloud.

### 3. Native Android Standalone Release Build
- Full standalone APK compiled with all native Kotlin/Java modules:
  - **Native SMS Retriever API** (`:sms-retriever`): Automatic OTP retrieval and autofill on physical Android devices.
  - **Native MapLibre Vector Engine** (`@maplibre/maplibre-react-native`): Full vector map rendering.
  - **Native Video Player** (`expo-video`): Retains the original brand logo animation (`AGR-MIRAI-LOGO-ANIMATION.mp4`).
- Output APK signed with production release keystore.

### 4. Onboarding & Field Form Improvements
- Added live blinking cursor and digit progress counter (`10/10 digits`) to the phone number entry screen.
- Enhanced location card with pinned GPS coordinates (`lat°N, lon°E`) and reverse-geocoded place names.
- MapLibre safe-mount fallbacks ensuring zero crashes across both standalone release builds and Expo environments.

---

## 📦 Release Assets
- **`app-release.apk`**: Standalone production Android release APK (~58.0 MB), signed and ready to install on Android 8.0+.
