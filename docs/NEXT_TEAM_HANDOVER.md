# AGRO MIRAI — Next Team Handover & Technical Architecture Guide

> **Target Audience:** Engineering team taking over development, maintenance, and deployment of the AGRO MIRAI ecosystem.  
> **Repository:** `riteshbonthalakoti/agro-mirai`  
> **Current Version:** `v2.2.2` (Android `versionCode: 17`)  
> **Last Updated:** October 2026

---

## 1. System Overview & Architecture

AGRO MIRAI is an AI-powered agricultural advisory platform designed for Indian smallholder farmers. The platform comprises:
- **Core Backend (`src/agro_mirai/`):** Python Flask REST API v2 (`auth_v2`, `fields`, `scans`, `advisories`, `voice_v2`, `admin`), backed by Supabase PostgreSQL and Google Earth Engine.
- **Mobile Application (`mobile/`):** React Native (Expo SDK 57, New Architecture enabled) supporting multilingual operation (English, Kannada, Telugu, Hindi) with offline caching and voice interaction.
- **Microservices (`services/`):**
  - `services/cnn`: Standalone plant leaf disease inference container.
  - `services/voice`: AI4Bharat / Piper / IndicTrans2 speech and translation models.
- **Web Admin Dashboard (`web/admin/`):** Single-page application using Alpine.js and Tailwind CSS for field officers and system admins.

---

## 2. Key Modules & Recent Additions

### A. Task 1 — Admin Dashboard: OTP Fallback via Render Service Logs
- **Problem:** In production, OTPs are delivered via the SMS Gateway. In remote rural areas where SMS network delivery may be delayed, field agents needed an emergency lookup mechanism in the admin panel without persisting sensitive OTPs in a separate database table.
- **Solution:**
  1. **Log Emission:** When an OTP is generated (`src/agro_mirai/api/routes/auth_v2.py`), a structured, grep-friendly line is logged:
     ```text
     otp_issued phone=+919876543210 otp=123456 ts=2026-10-13T09:00:00Z
     ```
  2. **Render API Client (`src/agro_mirai/api/render_logs.py`):**
     - Queries Render's REST log API: `GET https://api.render.com/v1/logs?resource={serviceId}&ownerId={ownerId}&limit=300&direction=backward&text=otp_issued`.
     - Automatically sources authentication from environment variables (`RENDER_API_KEY`, `RENDER_OWNER_ID`, `RENDER_SERVICE_ID`), with automatic fallback to the Render CLI session configuration (`~/.render/cli.yaml`).
     - Extracts the latest issued OTP for the requested phone number and calculates the age in seconds.
  3. **Protected Admin Endpoint (`src/agro_mirai/api/routes/admin.py`):**
     - `GET /v2/admin/otps/lookup?phone=<phone>` (protected by `@require_admin` session auth).
     - Returns `{ "phone": "...", "otp": "...", "issued_at": "...", "seconds_old": 42 }` or `404 NOT_FOUND` if not within the lookback window.
  4. **Admin UI (`web/admin/index.html` & `web/admin/admin.js`):**
     - Replaced old 5-second polling with an on-demand **OTP Lookup** view.
     - Allows entering a phone number to fetch the recent code and time elapsed.

---

### B. Task 2 — Kannada & Telugu Voice Architecture (Free-Tier Safe)
- **Problem:** `agro-mirai-voice-heavy` (IndicTrans2 translation + VITS TTS for Kannada/Telugu) exceeds the 512 MB memory limit of Render's free tier, causing Out-Of-Memory (OOM) crashes.
- **Solution:** A 3-tier resilient fallback chain for Kannada (`kn`) and Telugu (`te`):
  1. **Tier 1 (Primary):** Attempts `agro-mirai-voice-heavy` via `RemoteVoiceService` at `VOICE_SERVICE_HEAVY_URL`.
  2. **Tier 2 (Cloud Fallback):** If Tier 1 times out or returns HTTP 502/5xx, cleanly falls back to Sarvam AI REST API (`src/agro_mirai/api/sarvam_client.py`):
     - STT: `saaras:v3`
     - TTS: `bulbul:v3` (generates high quality Indian language audio in 1–2s)
     - Translation: `sarvam-translate:v1`
     - Rotates across multiple API keys (`SARVAM_API_KEY_1..3`).
  3. **Tier 3 (Honest In-App Message):** If both services are unreachable or quotas are exhausted:
     - Returns text payload without audio.
     - Mobile UI (`VoiceMode.tsx` & `AdviceTab.tsx`) displays an honest, localized message in the farmer's native tongue:
       - **Kannada:** `"ಈಗ ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ — ಮೇಲಿನ ಪಠ್ಯವನ್ನು ಓದಿ."`
       - **Telugu:** `"ఇప్పుడు వాయిస్ అందుబాటులో లేదు — పై టెక్స్ట్ చదవండి."`
       - **Hindi:** `"अभी आवाज़ उपलब्ध नहीं — ऊपर का पाठ पढ़ें।"`
       - **English:** `"Voice unavailable right now — please read the text above."`
  4. **English & Hindi:** Retain their existing lightweight path (`Piper` TTS / local STT) untouched.
  5. **Telemetry:** Structured log lines emitted on every voice request:
     ```text
     voice_tts_tier tier={heavy|sarvam|none} lang={kn|te}
     voice_translate_tier tier={heavy|sarvam|none} {source}->{target}
     ```

---

### C. Task 3 — Mobile UI Enhancements, Leaf Scanner, and Maps
- **UX & Transitions:**
  - Integrated `AnimatedTabPane` in `mobile/App.tsx` providing subtle fade and slide transitions between tabs.
  - Implemented `TabBarButton` with spring scale animations and clear active indicator bars.
  - Migrated navigation and header icons universally to `lucide-react-native` vector icons (`Sprout`, `CloudRain`, `ShieldAlert`, `MapPin`, `Bell`, `FileText`, `Phone`, etc.), removing legacy emoji icons.
  - Notification drawer with smooth slide-up bottom sheet and bell-swing micro-animation.
  - Enhanced `VoiceMode.tsx` to display localized warning badges when fallback text-only answers are returned.
- **Leaf Disease Scanner (`leaf_gate.py` & `ScanTab.tsx`):**
  - Integrated dual-layer biological gate (`src/agro_mirai/models/leaf_gate.py`):
    - Color distribution filter (evaluates chlorophyll/green hue vs. synthetic grayscale).
    - Contour and gradient complexity check rejecting photos of faces, screens, memes, and non-foliage items.
  - Removed confusing crop coverage disclaimers and raw confidence bars in `ScanTab.tsx`; replaced with structured, actionable farmer guidance (disease identification, immediate measures, preventive sprays).
- **Field Map Screen (`MapTab.tsx`):**
  - Upgraded to MapLibre GL with smooth satellite/terrain raster layer caching.
  - Integrated live GPS auto-tracking with pulsing blue beacon dot.
  - Added floating control to toggle camera focus between farmer's live phone GPS and registered field polygon.
- **Farmer Data History (`DataTab.tsx`):**
  - Added farmer-centric weekly summary cards for soil health, root-zone water balance, and NDVI vigor.
  - Chronological agronomic timeline for sensor readings and historical advisories.

---

### D. Task 4 — Direct APK Distribution Pipeline & Edge CDN
- **Problem:** GitHub Releases APK download links often fail or stall at 99% in Android web views and mobile browsers (e.g., Xiaomi Mi Browser, Chrome Data Saver) due to gzip transformation and connection resets.
- **Solution:**
  1. **Direct CDN Hosting (`web/`):**
     - Release APK hosted directly at `https://agromirai.vercel.app/app-release.apk`.
     - Vercel configuration (`vercel.json`) applies strict cache and binary delivery headers:
       - `Content-Type: application/vnd.android.package-archive`
       - `Content-Disposition: attachment; filename="app-release.apk"`
       - `Cache-Control: public, max-age=31536000, immutable, no-transform`
       - The `no-transform` directive guarantees mobile ISP middleboxes and proxy accelerators do not modify or buffer the stream, resolving the 99% download stall.
  2. **Landing & Download Page (`web/download/index.html`):**
     - Clean, responsive download page with auto-download trigger on mobile.
     - Displays version badge (`v2.2.2`), release date, SHA-256 integrity hash, and step-by-step sideloading instructions.

---

### E. Task 5 — Native SMS OTP Autofill
- **Android SMS Retriever API Integration:**
  - Automated detection of incoming verification SMS messages without requesting high-risk `READ_SMS` runtime permissions.
  - Formatted outbound SMS template in `src/agro_mirai/auth/otp_providers.py`:
    ```text
    <#> Your AGRO MIRAI verification code is: 123456
    ```
  - Cleaned template to omit trailing hash strings that triggered carrier spam filtering or confused farmers during manual entry.

---

## 3. Build & Compilation Instructions

### Android Release APK Build
1. **Prerequisites:**
   - Eclipse Adoptium JDK 17 (`C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`)
   - Android SDK / NDK installed.
2. **Environment Variables:**
   - Clean user-level Java options (AGP Prefab/CMake fails if `java` emits "Picked up JDK_JAVA_OPTIONS" to stderr):
     ```powershell
     Remove-Item env:JDK_JAVA_OPTIONS -ErrorAction SilentlyContinue
     Remove-Item env:JAVA_TOOL_OPTIONS -ErrorAction SilentlyContinue
     ```
   - Set the release keystore password:
     ```powershell
     $env:RELEASE_KEYSTORE_PASSWORD = "85uJaE9Z4umpVIQINlmFSshM"
     ```
3. **Execute Build:**
   ```powershell
   cd mobile\android
   .\gradlew.bat clean
   .\gradlew.bat assembleRelease
   ```
4. **Artifact Location:**
   - Output APK: `mobile\android\app\build\outputs\apk\release\app-release.apk`
   - Verified release-signed with PKCS12 keystore `agro-mirai-release`.
   - Universal APK (`versionCode: 17`, `versionName: 2.2.2`) supporting arm64-v8a, armeabi-v7a, x86, and x86_64.

---

## 4. Key Configuration Files & Credentials Reference

| File | Purpose | Notes |
|------|---------|-------|
| `mobile/app.json` | Expo application manifest | Tracks `version` (2.2.2), `versionCode` (17), config plugins. |
| `mobile/plugins/withReleaseSigning.js` | Expo Config Plugin | Injects release signing config into `build.gradle` on prebuild. |
| `mobile/release-keys/credentials.txt` | Keystore metadata | Contains store password, alias, and key passwords. |
| `src/agro_mirai/api/render_logs.py` | Render log extractor | Queries service logs for OTP retrieval. |
| `src/agro_mirai/api/sarvam_client.py` | Sarvam AI REST client | Multilingual STT/TTS/Translation fallbacks. |
| `src/agro_mirai/api/voice_client.py` | Voice routing orchestrator | Implements tiered fallback logic. |
| `src/agro_mirai/models/leaf_gate.py` | Biological leaf gate | Rejects non-foliage images before CNN / Gemini inference. |
| `vercel.json` | Vercel routing & headers | Direct APK CDN delivery with `no-transform` header. |
| `.env` | Backend environment secrets | Supabase, Weather, Gemini, Sarvam credentials. |

---

## 5. Summary of Recent Milestones & Git Commits

- `06a8dd0`: `add cli.yaml session fallback for render otp lookup`
- `5ccf919`: `add voice text fallback and smooth tab transitions`
- `v2.2.2`: `v2.2.2 Universal release with Edge CDN distribution, SMS retriever autofill, MapLibre GPS, and leaf validation gate`

