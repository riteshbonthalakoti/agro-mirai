import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text as RNText,
  TextInput as RNTextInput,
  View,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  StatusBar,
  Image,
  Modal,
  useWindowDimensions,
  TextProps,
  TextInputProps,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Speech from 'expo-speech';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { createAudioPlayer, AudioPlayer } from 'expo-audio';
import { CameraView, useCameraPermissions, FlashMode } from 'expo-camera';
import { BlurView } from 'expo-blur';
import {
  useFonts,
  Poppins_400Regular,
  Poppins_500Medium,
  Poppins_600SemiBold,
  Poppins_700Bold,
} from '@expo-google-fonts/poppins';
// Module 31: Fraunces (serif display, for headlines/titles) and IBM Plex
// Mono (for numbers/timestamps/units) loaded via @expo-google-fonts, the
// same mechanism the existing Poppins load already uses -- confirmed
// against https://docs.expo.dev/versions/v57.0.0/sdk/font/ that
// useFonts()'s API is unchanged in SDK 57. Poppins/system stays the
// default body font; these two are opt-in via styles.fraunces /
// styles.plexMono below, not a global replacement.
import { Fraunces_600SemiBold, Fraunces_700Bold } from '@expo-google-fonts/fraunces';
import { IBMPlexMono_400Regular, IBMPlexMono_500Medium } from '@expo-google-fonts/ibm-plex-mono';

import AsyncStorage from '@react-native-async-storage/async-storage';

import { API_BASE_URL } from './src/config';
import { Icon } from './icons';

// Brand typeface (Module 31): Poppins for Latin/numeric text. Indic
// scripts (Telugu/Kannada/Hindi) stay on the system font -- Poppins (like
// almost every Latin display face) has no glyphs for those scripts, and
// Android/iOS both already render them correctly via system fallback, so
// forcing Poppins everywhere would either show tofu boxes or silently
// fall back anyway. Rather than hand-edit every one of this file's Text
// usages, Text/TextInput are shadowed here so every existing call site
// picks up the right static Poppins weight automatically, based on
// whatever fontWeight it already declares.
function pickPoppinsFamily(fontWeight: unknown): string {
  const w = typeof fontWeight === 'number' ? String(fontWeight) : fontWeight;
  if (w === 'bold' || w === '700' || w === '800' || w === '900') return 'Poppins_700Bold';
  if (w === '600') return 'Poppins_600SemiBold';
  if (w === '500') return 'Poppins_500Medium';
  return 'Poppins_400Regular';
}

function Text(props: TextProps) {
  const flat = StyleSheet.flatten(props.style) || {};
  const fontFamily = pickPoppinsFamily(flat.fontWeight);
  return <RNText {...props} style={[{ fontFamily }, props.style]} />;
}

function TextInput(props: TextInputProps) {
  const flat = StyleSheet.flatten(props.style) || {};
  const fontFamily = pickPoppinsFamily(flat.fontWeight);
  return <RNTextInput {...props} style={[{ fontFamily }, props.style]} />;
}

// Pre-require logo assets for instant Metro bundling
const FULL_LOGO_WITH_NAME = require('./assets/Agro_Mirai_Logo.png');
const CROPPED_LOGO_WITHOUT_NAME = require('./assets/Logo.png');

// Matches specs/core/openapi.yaml FieldCreate.soil_type / current_crop enums
// exactly -- kept as the raw enum values (not translated) so the value the
// app sends the backend can never drift from what the schema accepts.
const SOIL_TYPES = ['alluvial', 'black', 'red', 'laterite', 'mountain', 'desert', 'saline', 'peaty', 'unknown'];
const CROP_TYPES = ['rice', 'maize', 'chickpea', 'kidneybeans', 'pigeonpeas', 'mothbeans', 'mungbean', 'blackgram', 'lentil', 'pomegranate', 'banana', 'mango', 'grapes', 'watermelon', 'muskmelon', 'apple', 'orange', 'papaya', 'coconut', 'cotton', 'jute', 'coffee'];

// --- Module 31: "Field & Grain" light-only palette ---
// Values below are the exact hex codes given in this module's own source
// brief (Claude outputs/module-31-redesign-onboarding-audit-prompt.md,
// section 1): grain-cream ground, deep field-green structure, one wheat
// accent, and severity colors kept strictly separate from brand color.
// No dark-mode variant exists anywhere in this file (grep-verified), and
// none is added here -- a field tool read outdoors in direct sun is hurt
// by a dark UI, per that same brief.
//
// Key NAMES are kept as the existing brand900/ink500/statusUrgent/etc
// aliases rather than renamed, because dozens of call sites across this
// file already reference them (THEME.brand900 alone: 43 sites) -- remapping
// values in place is the low-risk path; a renamed key set would require
// touching every one of those call sites for no behavioral gain.
const THEME = {
  brand900: '#16301F', // deep field-green (darkest)
  brand800: '#21492E', // deep field-green (mid)
  brand700: '#3E7A50', // deep field-green (lightest structural)
  brand600: '#3E7A50',
  brand500: '#5B9A6D',
  brand400: '#8FBD9B',
  brand100: '#E4EEE3',
  accentGold: '#C99A3E', // wheat accent -- held to one interactive moment/screen
  accentGoldSoft: '#EFDFB8',
  grainCream: '#FBF7EC',
  grainCardBg: '#FFFFFF',
  glassCardBg: 'rgba(255, 255, 255, 0.94)',
  glassBorder: 'rgba(22, 48, 31, 0.12)',
  soilBrown: '#6B4E31',
  ink900: '#1C1F1B',
  ink700: '#3A3F38',
  ink600: '#4A5048',
  ink500: '#6B7268',
  ink300: '#D8D2C2',
  statusGood: '#2F7D4F',
  statusCaution: '#B9791F',
  statusUrgent: '#B23A2E',
  shadowColor: '#16301F',
  screenBg: '#F2EBDA', // secondary ground tone (cards/sections on cream)
};

// --- Complete 4-Language Native Script i18n ---
type LangKey = 'kn' | 'te' | 'hi' | 'en';

const LANG_DISPLAY_NAMES: Record<LangKey, string> = {
  kn: 'ಕನ್ನಡ (Kannada)',
  te: 'తెలుగు (Telugu)',
  hi: 'हिंदी (Hindi)',
  en: 'English'
};

const TRANSLATIONS: Record<LangKey, Record<string, string>> = {
  kn: {
    splashTagline: 'ಸ್ಮಾರ್ಟ್ AI ಕೃಷಿ ಸಲಹೆಗಾರ',
    getStarted: 'ಪ್ರಾರಂಭಿಸಿ',
    selectLang: 'ಭಾಷೆಯನ್ನು ಆಯ್ಕೆ ಮಾಡಿ',
    continue: 'ಮುಂದುವರಿಸಿ',
    back: '← ಭಾಷೆ',
    loginTitle: 'ರೈತರ ಲಾಗಿನ್',
    nameLabel: 'ಪೂರ್ಣ ಹೆಸರು',
    namePlaceholder: 'ಉದಾ: ರವಿ ಕುಮಾರ್',
    phoneLabel: 'ದೂರವಾಣಿ ಸಂಖ್ಯೆ',
    phonePlaceholder: 'ಉದಾ: 9876543210',
    sendOtpBtn: 'OTP ಕಳುಹಿಸಿ',
    otpLabel: 'OTP ನಮೂದಿಸಿ',
    otpPlaceholder: '6-ಅಂಕಿಯ ಕೋಡ್',
    otpSentHint: 'OTP ಕಳುಹಿಸಲಾಗಿದೆ (ಪ್ರಸ್ತುತ ಸರ್ವರ್ ಲಾಗ್‌ಗಳಲ್ಲಿ ಮಾತ್ರ — SMS ಇನ್ನೂ ಸಂಪರ್ಕಗೊಂಡಿಲ್ಲ).',
    verifyOtpBtn: 'ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಪ್ರವೇಶಿಸಿ',
    resendOtpBtn: 'OTP ಮರುಕಳುಹಿಸಿ',
    changeNumberBtn: '← ಸಂಖ್ಯೆ ಬದಲಾಯಿಸಿ',
    invalidOtp: 'ತಪ್ಪು ಅಥವಾ ಅವಧಿ ಮೀರಿದ OTP.',
    pleaseWait: 'ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯ ಕಾಯಿರಿ.',
    todayAdvisory: 'ಇಂದಿನ ಕೃಷಿ ಸಲಹೆ ಕೇಳಿ',
    playingAudio: 'ಧ್ವನಿ ಸಲಹೆ ಪ್ಲೇ ಆಗುತ್ತಿದೆ...',
    listenVoice: 'ಧ್ವನಿ ಸಲಹೆ ಆಲಿಸಿ',
    fieldActions: 'ಕ್ಷೇತ್ರ ನಿರ್ವಹಣೆ',
    irrigation: 'ನೀರು ನೀಡುವುದು',
    disease: 'ರೋಗ ಸ್ಕ್ಯಾನ್',
    crop: 'ಬೆಳೆ ಆರೋಗ್ಯ',
    history: 'ಇತಿಹಾಸ',
    actionAdvisories: 'ಇಂದಿನ ಮುಖ್ಯ ಸಲಹೆಗಳು',
    logout: 'ನಿರ್ಗಮಿಸಿ',
    selectField: 'ಹೊಲವನ್ನು ಆಯ್ಕೆ ಮಾಡಿ',
    urgentPriority: 'ಪ್ರಮುಖ ಸಲಹೆ',
    todayAction: 'ಇಂದಿನ ಕೃಷಿ ಕಾರ್ಯ',
    listen: 'ಕೇಳಿ',
    scanLeaf: 'ಎಲೆ ಫೋಟೋ ತೆಗೆದು ರೋಗ ತಪಾಸಣೆ ಮಾಡಿ',
    scanTitle: 'ಎಲೆ ರೋಗ ತಪಾಸಣೆ (AI Scan)',
    pickGallery: 'ಗ್ಯಾಲರಿಯಿಂದ ಆಯ್ಕೆ ಮಾಡಿ',
    takePhoto: 'ಕ್ಯಾಮೆರಾದಿಂದ ಫೋಟೋ ತೆಗೆಯಿರಿ',
    analyzing: 'AI ಎಲೆ ರೋಗ ತಪಾಸಣೆ ನಡೆಸುತ್ತಿದೆ...',
    confirmLangTitle: 'ಸ್ಥಳೀಯ ಭಾಷೆ ದೃಢೀಕರಣ',
    detectedLangPrefix: 'ಪತ್ತೆಯಾಗಿದೆ:',
    confirmLangBtn: 'ದೃಢೀಕರಿಸಿ ಮುಂದುವರಿಸಿ',
    profileSetupTitle: 'ಸ್ವಾಗತ!',
    profileSetupSub: 'ನಿಮ್ಮ ಭಾಷೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ',
    profileSetupContinue: 'ಮುಂದುವರಿಸಿ',
    changeLangBtn: 'ಭಾಷೆಯನ್ನು ಬದಲಾಯಿಸಿ',
    tabHome: 'ಮುಖ್ಯ ಪುಟ',
    tabScan: 'ಎಲೆ ಸ್ಕ್ಯಾನ್',
    tabHistory: 'ಇತಿಹಾಸ',
    tabAdvisories: 'ಸಲಹೆಗಳು',
    tabRecords: 'ದಾಖಲೆಗಳು',
    tabSettings: 'ಸಂಯೋಜನೆಗಳು',
    recordsSubtitle: 'ಸಲಹೆಗಳು ಮತ್ತು ಸ್ಕ್ಯಾನ್ ಇತಿಹಾಸ ಒಂದೇ ಕಡೆ',
    recordsFilterAll: 'ಎಲ್ಲಾ',
    recordsFilterIrrigation: 'ನೀರಾವರಿ',
    recordsFilterDisease: 'ರೋಗ',
    emptyRecords: 'ಇನ್ನೂ ಯಾವುದೇ ದಾಖಲೆಗಳಿಲ್ಲ.',
    settingsFieldsGroup: 'ಹೊಲಗಳು',
    settingsActiveFieldLabel: 'ಸಕ್ರಿಯ ಹೊಲ',
    settingsAddFieldRow: 'ಹೊಸ ಹೊಲ ಸೇರಿಸಿ',
    settingsPreferencesGroup: 'ಆದ್ಯತೆಗಳು',
    settingsLanguageRow: 'ಭಾಷೆ',
    settingsNoFieldYet: 'ಇನ್ನೂ ಹೊಲ ಸೇರಿಸಿಲ್ಲ',
    homeNoFieldTitle: 'ಪ್ರಾರಂಭಿಸಲು ಹೊಲ ಸೇರಿಸಿ',
    homeNoFieldSub: 'ಸಲಹೆ ಪಡೆಯಲು ನಿಮ್ಮ ಮೊದಲ ಹೊಲವನ್ನು ಸೇರಿಸಿ',
    aiMatchLabel: 'AI ಹೊಂದಾಣಿಕೆ',
    onboard1Title: 'ನಿಮ್ಮ ಹೊಲಕ್ಕಾಗಿ ದೈನಂದಿನ ಸಲಹೆ',
    onboard1Body: 'ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಮಾತನಾಡುವ ಇಂದಿನ ನೀರಾವರಿ ಮತ್ತು ರೋಗ ಸಲಹೆ ಪಡೆಯಿರಿ.',
    onboard2Title: 'ಎಲೆ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ, ತಕ್ಷಣ ತಿಳಿಯಿರಿ',
    onboard2Body: 'ಒಂದು ಫೋಟೋದಿಂದ ರೋಗವನ್ನು ಪತ್ತೆಹಚ್ಚಿ ಮತ್ತು ಧ್ವನಿಯಲ್ಲಿ ಸಲಹೆ ಪಡೆಯಿರಿ.',
    onboardDoneBtn: 'ಪ್ರಾರಂಭಿಸೋಣ',
    onboardSkip: 'ಬಿಟ್ಟುಬಿಡಿ',
    embeddedCamTitle: 'ಕ್ಯಾಮೆರಾ ವೀಕ್ಷಣೆ',
    closeCam: 'ಮುಚ್ಚಿ',
    scanLeafSub: 'ಎಲೆಯ ಫೋಟೋ ತೆಗೆದು ರೋಗ ಪರೀಕ್ಷಿಸಿ',
    scanTabSub: 'ಎಲೆಯ ಮೇಲಿನ ರೋಗ ಗುರುತಿಸುವಿಕೆ',
    embeddedCamSub: 'ಎಲೆಯನ್ನು ಚೌಕದ ಒಳಗೆ ಇರಿಸಿ',
    gridSubIrrigation: 'ಇಂದಿನ ಶಿಫಾರಸು',
    gridSubDisease: 'ಎಲೆ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ',
    gridSubCrop: 'ಪ್ರಸ್ತುತ ಸ್ಥಿತಿ',
    historyTabSub: 'ಹಿಂದಿನ ಸ್ಕ್ಯಾನ್ ಮತ್ತು ಸಲಹೆಗಳು',
    emptyHistory: 'ಇನ್ನೂ ಸ್ಕ್ಯಾನ್ ಮಾಡಿಲ್ಲ. ಎಲೆಯ ಫೋಟೋ ತೆಗೆದು ಪ್ರಾರಂಭಿಸಿ.',
    emptyFields: 'ಇನ್ನೂ ಯಾವುದೇ ಹೊಲ ಸೇರಿಸಿಲ್ಲ.',
    emptyAdvisories: 'ಇನ್ನೂ ಯಾವುದೇ ಸಲಹೆಗಳಿಲ್ಲ. ಹೊಲದ ಡೇಟಾ ಬಂದ ನಂತರ ಇಲ್ಲಿ ಕಾಣಿಸುತ್ತದೆ.',
    noFieldTitle: 'ಹೊಲ ಸೇರಿಸಿಲ್ಲ',
    noFieldBody: 'ಸ್ಕ್ಯಾನ್ ಮಾಡುವ ಮೊದಲು ದಯವಿಟ್ಟು ಒಂದು ಹೊಲ ಸೇರಿಸಿ.',
    galleryPermTitle: 'ಅನುಮತಿ ಅಗತ್ಯ',
    galleryPermBody: 'ಬೆಳೆ ಎಲೆ ಚಿತ್ರಗಳನ್ನು ಆಯ್ಕೆ ಮಾಡಲು ಗ್ಯಾಲರಿ ಅನುಮತಿ ಅಗತ್ಯವಿದೆ.',
    cameraPermTitle: 'ಅನುಮತಿ ಅಗತ್ಯ',
    cameraPermBody: 'ಬೆಳೆ ಎಲೆ ಫೋಟೋಗಳನ್ನು ಸ್ಕ್ಯಾನ್ ಮಾಡಲು ಕ್ಯಾಮೆರಾ ಅನುಮತಿ ಅಗತ್ಯವಿದೆ.',
    captureFailedTitle: 'ಸೆರೆಹಿಡಿಯುವಿಕೆ ವಿಫಲವಾಗಿದೆ',
    captureFailedBody: 'ಫೋಟೋ ಸೆರೆಹಿಡಿಯಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    advisoriesSubtitle: 'ದೈನಂದಿನ ಕೃಷಿ ಮತ್ತು ಪರಿಸರ ಮಾರ್ಗದರ್ಶನ',
    diseaseNameFallback: 'ಎಲೆ ರೋಗ',
    profileTitle: 'ನನ್ನ ಪ್ರೊಫೈಲ್',
    profileNameLabel: 'ಪೂರ್ಣ ಹೆಸರು',
    profilePhoneLabel: 'ಫೋನ್ ಸಂಖ್ಯೆ',
    changePhotoBtn: 'ಫೋಟೋ ಬದಲಾಯಿಸಿ',
    saveProfileBtn: 'ಉಳಿಸಿ',
    homeAddFieldCta: '+ ಹೊಲ ಸೇರಿಸಿ',
    addFieldTitle: 'ಹೊಸ ಹೊಲ ಸೇರಿಸಿ',
    addFieldNameLabel: 'ಹೊಲದ ಹೆಸರು',
    addFieldAreaLabel: 'ವಿಸ್ತೀರ್ಣ (ಹೆಕ್ಟೇರ್)',
    addFieldSoilLabel: 'ಮಣ್ಣಿನ ಪ್ರಕಾರ (ಐಚ್ಛಿಕ)',
    addFieldCropLabel: 'ಪ್ರಸ್ತುತ ಬೆಳೆ (ಐಚ್ಛಿಕ)',
    addFieldLocationLabel: 'ಹೊಲದ ಸ್ಥಳ',
    addFieldUseLocationBtn: 'ಪ್ರಸ್ತುತ ಸ್ಥಳ ಬಳಸಿ',
    addFieldLocationCaptured: 'ಸ್ಥಳ ಸೆರೆಹಿಡಿಯಲಾಗಿದೆ',
    addFieldSubmitBtn: 'ಹೊಲ ಸೇರಿಸಿ',
    addFieldCancelBtn: 'ರದ್ದುಮಾಡಿ',
    addFieldNameRequired: 'ದಯವಿಟ್ಟು ಹೊಲದ ಹೆಸರು ನಮೂದಿಸಿ.',
    addFieldAreaRequired: 'ದಯವಿಟ್ಟು ಸರಿಯಾದ ವಿಸ್ತೀರ್ಣ ನಮೂದಿಸಿ.',
    addFieldLocationRequired: 'ದಯವಿಟ್ಟು ಹೊಲದ ಸ್ಥಳವನ್ನು ಸೆರೆಹಿಡಿಯಿರಿ.',
    addFieldGenericError: 'ಹೊಲ ಸೇರಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    locationPermissionDenied: 'ಸ್ಥಳ ಅನುಮತಿ ಅಗತ್ಯ.',
    locationCaptureFailed: 'ಸ್ಥಳ ಪಡೆಯಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.',
    modalIrrigationTitle: 'ನೀರಾವರಿ ವಿವರಗಳು',
    modalCropTitle: 'ಬೆಳೆ ಆರೋಗ್ಯ',
    modalHistoryTitle: 'ಸಲಹೆ ಇತಿಹಾಸ',
    recommendedDepth: 'ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಿನ ಪ್ರಮಾಣ',
    soilMoisture: 'ಮಣ್ಣಿನ ತೇವಾಂಶ',
    weatherForecast: 'ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ',
    cropTypeLabel: 'ಬೆಳೆ ಪ್ರಕಾರ',
    fieldAreaLabel: 'ಹೊಲದ ವಿಸ್ತೀರ್ಣ',
    growthPhaseLabel: 'ಬೆಳವಣಿಗೆ ಹಂತ',
    scanErrorTitle: 'ಸ್ಕ್ಯಾನ್ ವಿಫಲವಾಗಿದೆ',
    scanErrorBody: 'ಫೋಟೋ ಸರ್ವರ್‌ಗೆ ಕಳುಹಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ನಿಮ್ಮ ಇಂಟರ್ನೆಟ್ ಸಂಪರ್ಕ ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    retryBtn: 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
  },
  te: {
    splashTagline: 'స్మార్ట్ AI వ్యవసాయ సలహాదారు',
    getStarted: 'ప్రారంభించండి',
    selectLang: 'భాషను ఎంచుకోండి',
    continue: 'కొనసాగించండి',
    back: '← వెనుకకు',
    loginTitle: 'రైతు ప్రవేశం',
    nameLabel: 'పూర్తి పేరు',
    namePlaceholder: 'ఉదా: రవి కుమార్',
    phoneLabel: 'ఫోన్ సంఖ్య',
    phonePlaceholder: 'ఉదా: 9876543210',
    sendOtpBtn: 'OTP పంపండి',
    otpLabel: 'OTP నమోదు చేయండి',
    otpPlaceholder: '6-అంకెల కోడ్',
    otpSentHint: 'OTP పంపబడింది (ప్రస్తుతం సర్వర్ లాగ్‌లలో మాత్రమే — SMS ఇంకా అనుసంధానించబడలేదు).',
    verifyOtpBtn: 'ధృవీకరించి ప్రవేశించండి',
    resendOtpBtn: 'OTP మళ్ళీ పంపండి',
    changeNumberBtn: '← సంఖ్యను మార్చండి',
    invalidOtp: 'తప్పు లేదా గడువు ముగిసిన OTP.',
    pleaseWait: 'దయచేసి కొంత సమయం నిరీక్షించండి.',
    todayAdvisory: 'నేటి వ్యవసాయ సలహా వినండి',
    playingAudio: 'సలహా ప్రసారమవుతోంది...',
    listenVoice: 'సలహా వినండి',
    fieldActions: 'పొలం నిర్వహణ',
    irrigation: 'నీటి పారుదల',
    disease: 'ఆకు వ్యాధి తనిఖీ',
    crop: 'పంట ఆరోగ్యం',
    history: 'గత సలహాలు',
    actionAdvisories: 'నేటి ముఖ్యమైన సలహాలు',
    logout: 'నిష్క్రమించండి',
    selectField: 'మీ పొలాన్ని ఎంచుకోండి',
    urgentPriority: 'అత్యవసర సలహా',
    todayAction: 'నేటి ముఖ్యమైన పని',
    listen: 'వినండి',
    scanLeaf: 'ఆకు ఫోటో తీసి వ్యాధి తనిఖీ చేయండి',
    scanTitle: 'ఆకు తెగులు విశ్లేషణ (AI Scan)',
    pickGallery: 'గ్యాలరీ నుండి ఎంచుకోండి',
    takePhoto: 'కెమెరాతో ఫోటో తీయండి',
    analyzing: 'కృత్రిమ మేధ (AI) ఆకు తెగులును విశ్లేషిస్తోంది...',
    confirmLangTitle: 'ప్రాంతీయ భాష నిర్ధారణ',
    detectedLangPrefix: 'గుర్తించబడింది:',
    confirmLangBtn: 'నిర్ధారించి కొనసాగించండి',
    profileSetupTitle: 'స్వాగతం!',
    profileSetupSub: 'మీ భాషను ఎంచుకోండి',
    profileSetupContinue: 'కొనసాగించండి',
    changeLangBtn: 'వేరే భాషను ఎంచుకోండి',
    tabHome: 'హోమ్',
    tabScan: 'లీఫ్ స్కాన్',
    tabHistory: 'చరిత్ర',
    tabAdvisories: 'సలహాలు',
    tabRecords: 'రికార్డులు',
    tabSettings: 'సెట్టింగ్‌లు',
    recordsSubtitle: 'సలహాలు మరియు స్కాన్ చరిత్ర ఒకే చోట',
    recordsFilterAll: 'అన్నీ',
    recordsFilterIrrigation: 'నీటిపారుదల',
    recordsFilterDisease: 'వ్యాధి',
    emptyRecords: 'ఇంకా రికార్డులు లేవు.',
    settingsFieldsGroup: 'పొలాలు',
    settingsActiveFieldLabel: 'యాక్టివ్ పొలం',
    settingsAddFieldRow: 'కొత్త పొలం జోడించండి',
    settingsPreferencesGroup: 'ప్రాధాన్యతలు',
    settingsLanguageRow: 'భాష',
    settingsNoFieldYet: 'ఇంకా పొలం జోడించలేదు',
    homeNoFieldTitle: 'ప్రారంభించడానికి పొలం జోడించండి',
    homeNoFieldSub: 'సలహా పొందడానికి మీ మొదటి పొలాన్ని జోడించండి',
    aiMatchLabel: 'AI మ్యాచ్',
    onboard1Title: 'మీ పొలం కోసం రోజువారీ సలహా',
    onboard1Body: 'మీ భాషలో మాట్లాడే నేటి నీటిపారుదల మరియు వ్యాధి సలహా పొందండి.',
    onboard2Title: 'ఆకు స్కాన్ చేయండి, వెంటనే తెలుసుకోండి',
    onboard2Body: 'ఒక ఫోటోతో వ్యాధిని గుర్తించి వాయిస్‌లో సలహా పొందండి.',
    onboardDoneBtn: 'ప్రారంభిద్దాం',
    onboardSkip: 'దాటవేయండి',
    embeddedCamTitle: 'కెమెరా వీక్షణ',
    closeCam: 'మూసివేయి',
    scanLeafSub: 'ఆకు ఫోటో తీసి వ్యాధిని తనిఖీ చేయండి',
    scanTabSub: 'ఆకుపై వ్యాధి గుర్తింపు',
    embeddedCamSub: 'ఆకును ఫ్రేమ్ లోపల ఉంచండి',
    gridSubIrrigation: 'నేటి సూచన',
    gridSubDisease: 'ఆకును స్కాన్ చేయండి',
    gridSubCrop: 'ప్రస్తుత స్థితి',
    historyTabSub: 'గత స్కాన్‌లు మరియు సలహాలు',
    emptyHistory: 'ఇంకా స్కాన్ చేయలేదు. ఆకు ఫోటో తీసి ప్రారంభించండి.',
    emptyFields: 'ఇంకా ఏ పొలం జోడించలేదు.',
    emptyAdvisories: 'ఇంకా సలహాలు లేవు. పొలం డేటా వచ్చిన తర్వాత ఇక్కడ కనిపిస్తాయి.',
    noFieldTitle: 'పొలం జోడించలేదు',
    noFieldBody: 'స్కాన్ చేసే ముందు దయచేసి ఒక పొలం జోడించండి.',
    galleryPermTitle: 'అనుమతి అవసరం',
    galleryPermBody: 'పంట ఆకు చిత్రాలను ఎంచుకోవడానికి గ్యాలరీ అనుమతి అవసరం.',
    cameraPermTitle: 'అనుమతి అవసరం',
    cameraPermBody: 'పంట ఆకు ఫోటోలను స్కాన్ చేయడానికి కెమెరా అనుమతి అవసరం.',
    captureFailedTitle: 'క్యాప్చర్ విఫలమైంది',
    captureFailedBody: 'ఫోటో తీయలేకపోయాము. దయచేసి మళ్ళీ ప్రయత్నించండి.',
    advisoriesSubtitle: 'రోజువారీ వ్యవసాయ మరియు పర్యావరణ మార్గదర్శకత్వం',
    diseaseNameFallback: 'ఆకు వ్యాధి',
    profileTitle: 'నా ప్రొఫైల్',
    profileNameLabel: 'పూర్తి పేరు',
    profilePhoneLabel: 'ఫోన్ నంబర్',
    changePhotoBtn: 'ఫోటో మార్చండి',
    saveProfileBtn: 'సేవ్ చేయండి',
    homeAddFieldCta: '+ పొలం జోడించండి',
    addFieldTitle: 'కొత్త పొలం జోడించండి',
    addFieldNameLabel: 'పొలం పేరు',
    addFieldAreaLabel: 'విస్తీర్ణం (హెక్టార్లు)',
    addFieldSoilLabel: 'నేల రకం (ఐచ్ఛికం)',
    addFieldCropLabel: 'ప్రస్తుత పంట (ఐచ్ఛికం)',
    addFieldLocationLabel: 'పొలం స్థానం',
    addFieldUseLocationBtn: 'ప్రస్తుత స్థానం వాడండి',
    addFieldLocationCaptured: 'స్థానం సంగ్రహించబడింది',
    addFieldSubmitBtn: 'పొలం జోడించండి',
    addFieldCancelBtn: 'రద్దు చేయండి',
    addFieldNameRequired: 'దయచేసి పొలం పేరు నమోదు చేయండి.',
    addFieldAreaRequired: 'దయచేసి సరైన విస్తీర్ణం నమోదు చేయండి.',
    addFieldLocationRequired: 'దయచేసి పొలం స్థానాన్ని సంగ్రహించండి.',
    addFieldGenericError: 'పొలం జోడించలేకపోయాము. మళ్ళీ ప్రయత్నించండి.',
    locationPermissionDenied: 'స్థాన అనుమతి అవసరం.',
    locationCaptureFailed: 'స్థానం పొందలేకపోయాము.',
    modalIrrigationTitle: 'నీటి పారుదల వివరాలు',
    modalCropTitle: 'పంట ఆరోగ్యం',
    modalHistoryTitle: 'సలహా చరిత్ర',
    recommendedDepth: 'సూచించిన నీటి పరిమాణం',
    soilMoisture: 'నేల తేమ',
    weatherForecast: 'వాతావరణ సూచన',
    cropTypeLabel: 'పంట రకం',
    fieldAreaLabel: 'పొలం విస్తీర్ణం',
    growthPhaseLabel: 'పెరుగుదల దశ',
    scanErrorTitle: 'స్కాన్ విఫలమైంది',
    scanErrorBody: 'ఫోటోను సర్వర్‌కు పంపలేకపోయాము. మీ ఇంటర్నెట్ కనెక్షన్‌ను చూసి, మళ్ళీ ప్రయత్నించండి.',
    retryBtn: 'మళ్ళీ ప్రయత్నించండి',
  },
  hi: {
    splashTagline: 'स्मार्ट AI कृषि सलाहकार',
    getStarted: 'शुरू करें',
    selectLang: 'भाषा चुनें',
    continue: 'आगे बढ़ें',
    back: '← वापस',
    loginTitle: 'किसान प्रवेश',
    nameLabel: 'पूरा नाम',
    namePlaceholder: 'उदा: रवि कुमार',
    phoneLabel: 'फोन नंबर',
    phonePlaceholder: 'उदा: 9876543210',
    sendOtpBtn: 'OTP भेजें',
    otpLabel: 'OTP दर्ज करें',
    otpPlaceholder: '6-अंकों का कोड',
    otpSentHint: 'OTP भेजा गया (अभी सिर्फ सर्वर लॉग में — SMS अभी जुड़ा नहीं है)।',
    verifyOtpBtn: 'सत्यापित करें और प्रवेश करें',
    resendOtpBtn: 'OTP दोबारा भेजें',
    changeNumberBtn: '← नंबर बदलें',
    invalidOtp: 'गलत या समय-समाप्त OTP।',
    pleaseWait: 'कृपया कुछ समय प्रतीक्षा करें।',
    todayAdvisory: 'आज की सलाह सुनें',
    playingAudio: 'सलाह प्रसारित हो रही है...',
    listenVoice: 'सलाह सुनें',
    fieldActions: 'खेत प्रबंधन',
    irrigation: 'सिंचाई',
    disease: 'रोग जांच',
    crop: 'फसल स्वास्थ्य',
    history: 'पिछली सलाह',
    actionAdvisories: 'आज की महत्वपूर्ण सलाह',
    logout: 'लॉगआउट',
    selectField: 'खेत चुनें',
    urgentPriority: 'अत्यंत महत्वपूर्ण सलाह',
    todayAction: 'आज का कार्य',
    listen: 'सुनें',
    scanLeaf: 'पत्ती का फोटो लेकर रोग जांच करें',
    scanTitle: 'पत्ती रोग विश्लेषण (AI Scan)',
    pickGallery: 'गैलरी से चुनें',
    takePhoto: 'कैमरा से फोटो लें',
    analyzing: 'AI पत्ती के रोग की जांच कर रहा है...',
    confirmLangTitle: 'स्थानीय भाषा पुष्टि',
    detectedLangPrefix: 'पहचानी गई:',
    confirmLangBtn: 'पुष्टि करें और आगे बढ़ें',
    profileSetupTitle: 'स्वागत है!',
    profileSetupSub: 'अपनी भाषा चुनें',
    profileSetupContinue: 'आगे बढ़ें',
    changeLangBtn: 'दूसरी भाषा चुनें',
    tabHome: 'मुख्य पृष्ठ',
    tabScan: 'पत्ती स्कैन',
    tabHistory: 'इतिहास',
    tabAdvisories: 'सलाहें',
    tabRecords: 'रिकॉर्ड',
    tabSettings: 'सेटिंग्स',
    recordsSubtitle: 'सलाह और स्कैन इतिहास एक ही जगह',
    recordsFilterAll: 'सभी',
    recordsFilterIrrigation: 'सिंचाई',
    recordsFilterDisease: 'रोग',
    emptyRecords: 'अभी तक कोई रिकॉर्ड नहीं है।',
    settingsFieldsGroup: 'खेत',
    settingsActiveFieldLabel: 'सक्रिय खेत',
    settingsAddFieldRow: 'नया खेत जोड़ें',
    settingsPreferencesGroup: 'प्राथमिकताएं',
    settingsLanguageRow: 'भाषा',
    settingsNoFieldYet: 'अभी तक कोई खेत नहीं जोड़ा गया',
    homeNoFieldTitle: 'शुरू करने के लिए खेत जोड़ें',
    homeNoFieldSub: 'सलाह पाने के लिए अपना पहला खेत जोड़ें',
    aiMatchLabel: 'AI मिलान',
    onboard1Title: 'आपके खेत के लिए रोज़ाना सलाह',
    onboard1Body: 'अपनी भाषा में बोली जाने वाली आज की सिंचाई और रोग सलाह पाएं।',
    onboard2Title: 'पत्ती स्कैन करें, तुरंत जानें',
    onboard2Body: 'एक फोटो से रोग पहचानें और आवाज़ में सलाह पाएं।',
    onboardDoneBtn: 'शुरू करें',
    onboardSkip: 'छोड़ें',
    embeddedCamTitle: 'कैमरा दृश्य',
    closeCam: 'बंद करें',
    scanLeafSub: 'पत्ती की फोटो लेकर रोग जांचें',
    scanTabSub: 'पत्ती पर रोग की पहचान',
    embeddedCamSub: 'पत्ती को फ्रेम के भीतर रखें',
    gridSubIrrigation: 'आज की सलाह',
    gridSubDisease: 'पत्ती स्कैन करें',
    gridSubCrop: 'वर्तमान स्थिति',
    historyTabSub: 'पिछले स्कैन और सलाह',
    emptyHistory: 'अभी तक कोई स्कैन नहीं। पत्ती की फोटो लेकर शुरू करें।',
    emptyFields: 'अभी तक कोई खेत नहीं जोड़ा गया।',
    emptyAdvisories: 'अभी तक कोई सलाह नहीं। खेत का डेटा आने के बाद यहां दिखेगी।',
    noFieldTitle: 'कोई खेत नहीं जोड़ा गया',
    noFieldBody: 'स्कैन करने से पहले कृपया एक खेत जोड़ें।',
    galleryPermTitle: 'अनुमति आवश्यक',
    galleryPermBody: 'फसल पत्ती की तस्वीरें चुनने के लिए गैलरी अनुमति आवश्यक है।',
    cameraPermTitle: 'अनुमति आवश्यक',
    cameraPermBody: 'फसल पत्ती की तस्वीरें स्कैन करने के लिए कैमरा अनुमति आवश्यक है।',
    captureFailedTitle: 'कैप्चर विफल',
    captureFailedBody: 'फोटो कैप्चर नहीं हो सका। कृपया फिर से प्रयास करें।',
    advisoriesSubtitle: 'दैनिक कृषि एवं पर्यावरण मार्गदर्शन',
    diseaseNameFallback: 'पत्ती रोग',
    profileTitle: 'मेरी प्रोफ़ाइल',
    profileNameLabel: 'पूरा नाम',
    profilePhoneLabel: 'फ़ोन नंबर',
    changePhotoBtn: 'फोटो बदलें',
    saveProfileBtn: 'सेव करें',
    homeAddFieldCta: '+ खेत जोड़ें',
    addFieldTitle: 'नया खेत जोड़ें',
    addFieldNameLabel: 'खेत का नाम',
    addFieldAreaLabel: 'क्षेत्रफल (हेक्टेयर)',
    addFieldSoilLabel: 'मिट्टी का प्रकार (वैकल्पिक)',
    addFieldCropLabel: 'वर्तमान फसल (वैकल्पिक)',
    addFieldLocationLabel: 'खेत का स्थान',
    addFieldUseLocationBtn: 'वर्तमान स्थान उपयोग करें',
    addFieldLocationCaptured: 'स्थान कैप्चर किया गया',
    addFieldSubmitBtn: 'खेत जोड़ें',
    addFieldCancelBtn: 'रद्द करें',
    addFieldNameRequired: 'कृपया खेत का नाम दर्ज करें।',
    addFieldAreaRequired: 'कृपया सही क्षेत्रफल दर्ज करें।',
    addFieldLocationRequired: 'कृपया खेत का स्थान कैप्चर करें।',
    addFieldGenericError: 'खेत जोड़ा नहीं जा सका। फिर से प्रयास करें।',
    locationPermissionDenied: 'स्थान अनुमति आवश्यक है।',
    locationCaptureFailed: 'स्थान प्राप्त नहीं हो सका।',
    modalIrrigationTitle: 'सिंचाई विवरण',
    modalCropTitle: 'फसल स्वास्थ्य',
    modalHistoryTitle: 'सलाह इतिहास',
    recommendedDepth: 'सुझाई गई पानी की मात्रा',
    soilMoisture: 'मिट्टी की नमी',
    weatherForecast: 'मौसम पूर्वानुमान',
    cropTypeLabel: 'फसल प्रकार',
    fieldAreaLabel: 'खेत का क्षेत्र',
    growthPhaseLabel: 'बढ़वार चरण',
    scanErrorTitle: 'स्कैन विफल',
    scanErrorBody: 'फोटो सर्वर तक नहीं पहुंच पाई। कृपया अपना इंटरनेट कनेक्शन जांचें और फिर से प्रयास करें।',
    retryBtn: 'फिर से प्रयास करें',
  },
  en: {
    splashTagline: 'Smart AI Agricultural Companion',
    getStarted: 'Get Started',
    selectLang: 'Select Language',
    continue: 'Continue',
    back: '← Back',
    loginTitle: 'Farmer Login',
    nameLabel: 'Full Name',
    namePlaceholder: 'e.g. Ravi Kumar',
    phoneLabel: 'Phone Number',
    phonePlaceholder: 'e.g. 9876543210',
    sendOtpBtn: 'Send OTP',
    otpLabel: 'Enter OTP',
    otpPlaceholder: '6-digit code',
    otpSentHint: 'OTP sent (currently server logs only — SMS delivery not wired up yet).',
    verifyOtpBtn: 'Verify & Login',
    resendOtpBtn: 'Resend OTP',
    changeNumberBtn: '← Change number',
    invalidOtp: 'Invalid or expired OTP.',
    pleaseWait: 'Please wait a moment before trying again.',
    todayAdvisory: "Today's Voice Advisory",
    playingAudio: 'Playing Voice Advisory...',
    listenVoice: 'Listen to Voice Advisory',
    fieldActions: 'Field Actions',
    irrigation: 'Irrigation',
    disease: 'Disease Risk',
    crop: 'Crop Health',
    history: 'History',
    actionAdvisories: 'Recent Action Advisories',
    logout: 'Logout',
    selectField: 'Select Field',
    urgentPriority: 'HIGH PRIORITY',
    todayAction: "Today's Action",
    listen: 'Listen',
    scanLeaf: 'Scan Leaf Image (AI Disease Scanner)',
    scanTitle: 'AI Leaf Disease Scanner',
    pickGallery: 'Choose from Gallery',
    takePhoto: 'Take Camera Photo',
    analyzing: 'Analyzing leaf image with AI model...',
    confirmLangTitle: 'Confirm Local Language',
    detectedLangPrefix: 'Detected:',
    confirmLangBtn: 'Confirm & Proceed',
    profileSetupTitle: 'Welcome!',
    profileSetupSub: 'Choose your language',
    profileSetupContinue: 'Continue',
    changeLangBtn: 'Choose Different Language',
    tabHome: 'Home',
    tabScan: 'AI Scan',
    tabHistory: 'History',
    tabAdvisories: 'Advisories',
    tabRecords: 'Records',
    tabSettings: 'Settings',
    recordsSubtitle: 'Advisories and scan history in one place',
    recordsFilterAll: 'All',
    recordsFilterIrrigation: 'Irrigation',
    recordsFilterDisease: 'Disease',
    emptyRecords: 'No records yet.',
    settingsFieldsGroup: 'Fields',
    settingsActiveFieldLabel: 'Active field',
    settingsAddFieldRow: 'Add a field',
    settingsPreferencesGroup: 'Preferences',
    settingsLanguageRow: 'Language',
    settingsNoFieldYet: 'No field added yet',
    homeNoFieldTitle: 'Add a field to get started',
    homeNoFieldSub: 'Add your first field to start getting advice',
    aiMatchLabel: 'AI Match',
    onboard1Title: "Daily advice for your field",
    onboard1Body: "Get today's irrigation and disease advice, spoken in your language.",
    onboard2Title: 'Scan a leaf, know right away',
    onboard2Body: 'Spot disease from one photo and hear the advice out loud.',
    onboardDoneBtn: "Let's go",
    onboardSkip: 'Skip',
    embeddedCamTitle: 'Camera View',
    closeCam: 'Close',
    scanLeafSub: 'Take a photo of the leaf to check for disease',
    scanTabSub: 'Disease detection on a leaf photo',
    embeddedCamSub: 'Position the leaf inside the frame',
    gridSubIrrigation: "Today's recommendation",
    gridSubDisease: 'Scan a leaf',
    gridSubCrop: 'Current status',
    historyTabSub: 'Past scans and advisories',
    emptyHistory: 'No scans yet. Take a leaf photo to get started.',
    emptyFields: 'No fields added yet.',
    emptyAdvisories: 'No advisories yet. They will appear here once field data comes in.',
    noFieldTitle: 'No Field Added',
    noFieldBody: 'Please add a field before scanning.',
    galleryPermTitle: 'Permission Required',
    galleryPermBody: 'Gallery permission is needed to pick crop leaf images.',
    cameraPermTitle: 'Permission Required',
    cameraPermBody: 'Camera permission is needed to scan crop leaf photos.',
    captureFailedTitle: 'Capture Failed',
    captureFailedBody: 'Could not capture the photo. Please try again.',
    advisoriesSubtitle: 'Daily Agronomist & Environmental Guidance',
    diseaseNameFallback: 'Leaf Disease',
    profileTitle: 'My Profile',
    profileNameLabel: 'Full Name',
    profilePhoneLabel: 'Phone Number',
    changePhotoBtn: 'Change Photo',
    saveProfileBtn: 'Save',
    homeAddFieldCta: '+ Add Field',
    addFieldTitle: 'Add New Field',
    addFieldNameLabel: 'Field Name',
    addFieldAreaLabel: 'Area (hectares)',
    addFieldSoilLabel: 'Soil Type (optional)',
    addFieldCropLabel: 'Current Crop (optional)',
    addFieldLocationLabel: 'Field Location',
    addFieldUseLocationBtn: 'Use Current Location',
    addFieldLocationCaptured: 'Location Captured',
    addFieldSubmitBtn: 'Add Field',
    addFieldCancelBtn: 'Cancel',
    addFieldNameRequired: 'Please enter a field name.',
    addFieldAreaRequired: 'Please enter a valid area.',
    addFieldLocationRequired: 'Please capture the field location.',
    addFieldGenericError: 'Could not add the field. Please try again.',
    locationPermissionDenied: 'Location permission is required.',
    locationCaptureFailed: 'Could not get your location.',
    modalIrrigationTitle: 'Irrigation Details',
    modalCropTitle: 'Crop Health',
    modalHistoryTitle: 'Advisory History',
    recommendedDepth: 'Recommended Water Depth',
    soilMoisture: 'Soil Moisture',
    weatherForecast: 'Weather Forecast',
    cropTypeLabel: 'Crop Type',
    fieldAreaLabel: 'Field Area',
    growthPhaseLabel: 'Growth Phase',
    scanErrorTitle: "Scan Couldn't Complete",
    scanErrorBody: "We couldn't reach the server to analyze this photo. Check your internet connection and try again.",
    retryBtn: 'Try Again',
  },
};

// --- Clean TTS Helper to prevent English accent in Native Speech ---
const getCleanTtsText = (rawText: string, lang: LangKey): string => {
  if (!rawText) return '';
  let clean = rawText.replace(/\(.*?\)/g, '').trim();
  if (lang !== 'en') {
    clean = clean.replace(/[A-Za-z]/g, '').trim();
  }
  return clean || rawText;
};

// --- AGRO MIRAI Logo Component ---
const AgroMiraiLogo = ({ size = 120, useCropped = false }: { size?: number; useCropped?: boolean }) => {
  return (
    <View style={[logoStyles.container, { width: size, height: useCropped ? size : size * 0.85 }]}>
      <Image 
        source={useCropped ? CROPPED_LOGO_WITHOUT_NAME : FULL_LOGO_WITH_NAME} 
        style={{ width: '100%', height: '100%', resizeMode: 'contain' }} 
      />
    </View>
  );
};

const logoStyles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default function App() {
  const [fontsLoaded] = useFonts({
    Poppins_400Regular,
    Poppins_500Medium,
    Poppins_600SemiBold,
    Poppins_700Bold,
    Fraunces_600SemiBold,
    Fraunces_700Bold,
    IBMPlexMono_400Regular,
    IBMPlexMono_500Medium,
  });

  if (!fontsLoaded) {
    // Deliberately RNText/plain View here, not the Poppins-shadowing Text
    // -- the font isn't loaded yet, so there's nothing for it to apply.
    return (
      <SafeAreaProvider>
        <View style={{ flex: 1, backgroundColor: '#FAF7F2', justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#2D6A4F" />
        </View>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <MainApp />
    </SafeAreaProvider>
  );
}

function MainApp() {
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  
  const scale = Math.min(windowWidth / 380, 1.2);
  const isSmallDevice = windowWidth < 360;

  const [screen, setScreen] = useState<'SPLASH' | 'LANG_PICKER' | 'ONBOARD_1' | 'ONBOARD_2' | 'AUTH' | 'PROFILE_SETUP' | 'HOME'>('SPLASH');
  // Module 31: has the 2-screen first-run onboarding sequence already been
  // shown on this device? Read once on mount from AsyncStorage; cold-start
  // routing below only inserts ONBOARD_1/ONBOARD_2 into the flow when this
  // is still false, so a returning farmer skips straight to AUTH/HOME as
  // before -- see the AsyncStorage.getItem('onboardingSeen') effect.
  const [onboardingSeen, setOnboardingSeen] = useState<boolean | null>(null);
  const [isNewFarmerPending, setIsNewFarmerPending] = useState(false);
  const [profileSetupLang, setProfileSetupLang] = useState<LangKey>('en');
  const [profileSetupSubmitting, setProfileSetupSubmitting] = useState(false);
  const [language, setLanguage] = useState<LangKey>('te');
  // Module 27: farmer identity/session now comes from the backend's
  // Name+Phone+OTP /v2/auth/* endpoints (signed session cookie), not
  // Supabase Auth -- see decisions/0023-name-phone-otp-auth.md.
  const [farmer, setFarmer] = useState<{ id: string; name: string; phone: string | null; photo_url?: string | null } | null>(null);

  // Profile screen state
  const [profileVisible, setProfileVisible] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profilePhotoUri, setProfilePhotoUri] = useState<string | null>(null);
  const [profilePhotoDataUri, setProfilePhotoDataUri] = useState<string | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState('');

  // Location & Permission State
  const [locationName, setLocationName] = useState<string>('Andhra Pradesh / Telangana');
  const [detectedLang, setDetectedLang] = useState<LangKey>('te');
  const [isDetectingLocation, setIsDetectingLocation] = useState<boolean>(false);
  const [langConfirmVisible, setLangConfirmVisible] = useState(false);
  const [detectedCoords, setDetectedCoords] = useState<{ latitude: number; longitude: number } | null>(null);

  // Add Field form state -- the app has no fields until the farmer adds one
  // for real (no more fake demo field), so this modal is the only way in.
  const [addFieldVisible, setAddFieldVisible] = useState(false);
  const [addFieldSubmitting, setAddFieldSubmitting] = useState(false);
  const [addFieldName, setAddFieldName] = useState('');
  const [addFieldAreaHa, setAddFieldAreaHa] = useState('');
  const [addFieldSoilType, setAddFieldSoilType] = useState<string | null>(null);
  const [addFieldCrop, setAddFieldCrop] = useState<string | null>(null);
  const [addFieldCoords, setAddFieldCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [addFieldLocating, setAddFieldLocating] = useState(false);
  const [addFieldError, setAddFieldError] = useState('');

  // Auth state: two-step Name+Phone+OTP flow
  const [authStep, setAuthStep] = useState<'ENTER_PHONE' | 'ENTER_OTP'>('ENTER_PHONE');
  const [nameInput, setNameInput] = useState('');
  const [phoneInput, setPhoneInput] = useState('');
  const [otpInput, setOtpInput] = useState('');
  const [authError, setAuthError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);

  // Navigation & Tab state
  const [activeTab, setActiveTab] = useState<'home' | 'scan' | 'records' | 'settings'>('home');
  const [recordsFilter, setRecordsFilter] = useState<'all' | 'irrigation' | 'disease'>('all');
  const [embeddedCameraVisible, setEmbeddedCameraVisible] = useState(false);
  const [cameraFlash, setCameraFlash] = useState<FlashMode>('off');
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  // Real scan history only -- populated from actual disease-scan results as
  // the farmer runs them this session. No seeded/fake entries: a farmer who
  // hasn't scanned anything yet has scanned nothing.
  const [scanHistory, setScanHistory] = useState<any[]>([]);

  // Home State
  const [fields, setFields] = useState<any[]>([]);
  const [selectedField, setSelectedField] = useState<any>(null);
  const [advisories, setAdvisories] = useState<any[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [playingAdvisoryId, setPlayingAdvisoryId] = useState<string | null>(null);
  const [sound, setSound] = useState<AudioPlayer | null>(null);

  // Leaf Disease Image Scan Modal State
  const [selectedImageUri, setSelectedImageUri] = useState<string | null>(null);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  const [scanResult, setScanResult] = useState<any>(null);
  const [scanError, setScanError] = useState(false);

  // Active Category Detail Modal
  const [activeModal, setActiveModal] = useState<'irrigation' | 'crop' | null>(null);

  const t = TRANSLATIONS[language] || TRANSLATIONS.en;

  // Stop any playing audio (on-device TTS preview or an advisory's voice
  // clip) the moment the screen changes, so a language-preview or advisory
  // playback triggered on one screen never bleeds into whatever screen the
  // user navigates to next (e.g. tapping "Confirm & Proceed" plays a
  // sample and immediately navigates away in the same action).
  useEffect(() => {
    return () => {
      try { Speech.stop(); } catch (e) {}
      if (sound) {
        sound.remove();
      }
      setIsPlayingAudio(false);
      setPlayingAdvisoryId(null);
    };
  }, [screen, sound]);

  // Cooldown countdown timer
  useEffect(() => {
    let timer: any;
    if (cooldownSeconds > 0) {
      timer = setInterval(() => {
        setCooldownSeconds((prev) => prev - 1);
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [cooldownSeconds]);

  useEffect(() => {
    // Try to restore an existing backend session (signed session cookie
    // from a prior /v2/auth/verify-otp) rather than assuming logged-out.
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/v2/farmers/me`);
        if (res.ok) {
          const data = await res.json();
          setFarmer({ id: data.id, name: data.name, phone: data.phone ?? null, photo_url: data.photo_url ?? null });
          await fetchBackendData();
          setScreen('HOME');
        }
      } catch (e) {
        console.log('Session restore check failed (likely offline or logged out):', e);
      }
    })();

    return () => {
      if (sound) {
        sound.remove();
      }
    };
  }, []);

  // Module 31: read the once-only onboarding flag on mount. Per the
  // Expo SDK 57 docs, @react-native-async-storage/async-storage's API is
  // unchanged from prior SDKs (plain async getItem/setItem, no new
  // permission or config step) -- confirmed against
  // https://docs.expo.dev/versions/v57.0.0/sdk/async-storage/ before use.
  useEffect(() => {
    (async () => {
      try {
        const seen = await AsyncStorage.getItem('onboardingSeen');
        setOnboardingSeen(seen === 'true');
      } catch (e) {
        // Degrade-not-fail: if local storage is unreadable, treat
        // onboarding as unseen rather than crash the cold-start flow.
        setOnboardingSeen(false);
      }
    })();
  }, []);

  // Request all permissions & detect location language
  // Camera/gallery permissions are requested contextually, right when the
  // farmer actually takes/picks a photo (pickImageFromGallery/
  // takeCameraPhoto below) -- not upfront here. Only location is needed
  // this early, for language auto-detection.
  const requestPermissionsAndDetectLanguage = async () => {
    setIsDetectingLocation(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();

      let detectedLocationText = 'Mandya, Karnataka';
      let autoLang: LangKey = 'kn';

      if (status === 'granted') {
        const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Low });
        setDetectedCoords({ latitude: loc.coords.latitude, longitude: loc.coords.longitude });
        const geocode = await Location.reverseGeocodeAsync({
          latitude: loc.coords.latitude,
          longitude: loc.coords.longitude,
        });

        if (geocode && geocode.length > 0) {
          const place = geocode[0];
          const region = (place.region || place.subregion || place.city || place.country || '').toLowerCase();
          detectedLocationText = `${place.city || place.subregion || place.district || 'Your Region'}, ${place.region || ''}`;

          if (region.includes('karnataka') || region.includes('bengaluru') || region.includes('mysuru') || region.includes('mandya')) {
            autoLang = 'kn';
          } else if (region.includes('andhra') || region.includes('telangana') || region.includes('hyderabad') || region.includes('vijayawada')) {
            autoLang = 'te';
          } else if (region.includes('delhi') || region.includes('pradesh') || region.includes('bihar') || region.includes('rajasthan') || region.includes('haryana')) {
            autoLang = 'hi';
          } else {
            autoLang = 'te';
          }
        }
      }

      setLocationName(detectedLocationText);
      setDetectedLang(autoLang);
      setLanguage(autoLang);
      setScreen(farmer ? 'HOME' : (onboardingSeen ? 'AUTH' : 'ONBOARD_1'));
      setLangConfirmVisible(true);
    } catch (err: any) {
      console.log('Location detection exception:', err.message);
      setLocationName('Andhra Pradesh / Telangana');
      setDetectedLang('te');
      setLanguage('te');
      setScreen(farmer ? 'HOME' : (onboardingSeen ? 'AUTH' : 'ONBOARD_1'));
      setLangConfirmVisible(true);
    } finally {
      setIsDetectingLocation(false);
    }
  };

  const finishOnboarding = async () => {
    try {
      await AsyncStorage.setItem('onboardingSeen', 'true');
    } catch (e) {
      // Degrade-not-fail: still proceed to AUTH even if the flag can't be
      // persisted -- worst case onboarding shows again next cold start.
    }
    setOnboardingSeen(true);
    setScreen('AUTH');
  };

  const fetchBackendData = async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      console.log(`Fetching backend data from ${API_BASE_URL}/v2/fields`);
      const fieldsRes = await fetch(`${API_BASE_URL}/v2/fields`, {
        headers: { 'Accept': 'application/json' }
      });

      if (!fieldsRes.ok) {
        throw new Error(`GET /v2/fields -> ${fieldsRes.status}`);
      }

      const data = await fieldsRes.json();
      // Real fields only -- a farmer who hasn't added a field yet gets an
      // empty list and the app shows a real "add a field" empty state, not
      // fabricated demo data standing in for it.
      const loadedFields: any[] = Array.isArray(data) ? data : (data.items || data.fields || []);

      setFields(loadedFields);
      const activeField = loadedFields[0] || null;
      setSelectedField(activeField);

      // Advisories are per-field (GET /v2/fields/{field_id}/advisories) --
      // there is no bare GET /v2/advisories in the API (see
      // specs/core/openapi.yaml). No field yet means no advisories to ask
      // for; a real field with genuinely zero advisories yet is a real
      // empty state, not a reason to invent one.
      let loadedAdvisories: any[] = [];
      if (activeField) {
        const advRes = await fetch(`${API_BASE_URL}/v2/fields/${activeField.id}/advisories`, {
          headers: { 'Accept': 'application/json' }
        });
        if (advRes.ok) {
          const advData = await advRes.json();
          const rawAdvisories = Array.isArray(advData) ? advData : (advData.items || advData.advisories || []);
          loadedAdvisories = rawAdvisories.map((a: any) => ({ ...a, _remote: true }));
        }
      }

      setAdvisories(loadedAdvisories);
    } catch (err: any) {
      // Genuine failure to reach the backend -- surface it as a real error
      // state (with a retry action) rather than papering over it with fake
      // data that looks indistinguishable from a real farmer's real field.
      console.log('Backend fetch warning:', err.message);
      setFields([]);
      setSelectedField(null);
      setAdvisories([]);
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  };

  const openAddField = () => {
    setAddFieldName('');
    setAddFieldAreaHa('');
    setAddFieldSoilType(null);
    setAddFieldCrop(null);
    setAddFieldError('');
    setAddFieldCoords(detectedCoords);
    setAddFieldVisible(true);
  };

  const captureFieldLocation = async () => {
    setAddFieldLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(t.noFieldTitle, t.locationPermissionDenied);
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const coords = { latitude: loc.coords.latitude, longitude: loc.coords.longitude };
      setAddFieldCoords(coords);
      setDetectedCoords(coords);
    } catch (e) {
      Alert.alert(t.noFieldTitle, t.locationCaptureFailed);
    } finally {
      setAddFieldLocating(false);
    }
  };

  const submitAddField = async () => {
    if (!addFieldName.trim()) {
      setAddFieldError(t.addFieldNameRequired);
      return;
    }
    const areaValue = parseFloat(addFieldAreaHa);
    if (!addFieldAreaHa || isNaN(areaValue) || areaValue <= 0) {
      setAddFieldError(t.addFieldAreaRequired);
      return;
    }
    if (!addFieldCoords) {
      setAddFieldError(t.addFieldLocationRequired);
      return;
    }

    setAddFieldSubmitting(true);
    setAddFieldError('');
    try {
      const payload: any = {
        name: addFieldName.trim(),
        latitude: addFieldCoords.latitude,
        longitude: addFieldCoords.longitude,
        area_ha: areaValue,
      };
      if (addFieldSoilType) payload.soil_type = addFieldSoilType;
      if (addFieldCrop) payload.current_crop = addFieldCrop;

      const res = await fetch(`${API_BASE_URL}/v2/fields`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.error?.message || `HTTP ${res.status}`);
      }

      setAddFieldVisible(false);
      await fetchBackendData();
    } catch (e: any) {
      setAddFieldError(e.message || t.addFieldGenericError);
    } finally {
      setAddFieldSubmitting(false);
    }
  };

  const openProfile = async () => {
    setProfileName(farmer?.name || '');
    setProfilePhotoUri(farmer?.photo_url || null);
    setProfilePhotoDataUri(null);
    setProfileError('');
    setProfileVisible(true);
    // Refresh from the backend in case another session changed it.
    try {
      const res = await fetch(`${API_BASE_URL}/v2/farmers/me`);
      if (res.ok) {
        const data = await res.json();
        setProfileName(data.name || '');
        setProfilePhotoUri(data.photo_url || null);
        setFarmer((prev) => (prev ? { ...prev, name: data.name, photo_url: data.photo_url } : prev));
      }
    } catch (e) {
      // Best-effort refresh; the modal still works off whatever we already have.
    }
  };

  const pickProfilePhoto = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(t.noFieldTitle, t.locationPermissionDenied);
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.4,
    });
    if (result.canceled || !result.assets || !result.assets[0]) return;

    const uri = result.assets[0].uri;
    setProfilePhotoUri(uri);

    // Same Blob->base64 approach as elsewhere in this file (Expo's fetch
    // needs a real Blob, not the classic {uri,name,type} RN shape) --
    // FileReader.readAsDataURL gives us the base64 data URI directly,
    // stored as-is server-side since no file-storage service exists yet.
    try {
      const localFile = await fetch(uri);
      const blob = await localFile.blob();
      const dataUri: string = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      setProfilePhotoDataUri(dataUri);
    } catch (e) {
      Alert.alert(t.noFieldTitle, t.addFieldGenericError);
    }
  };

  const submitProfile = async () => {
    if (!profileName.trim()) {
      setProfileError(t.addFieldNameRequired);
      return;
    }
    setProfileSaving(true);
    setProfileError('');
    try {
      const payload: any = { name: profileName.trim() };
      if (profilePhotoDataUri) payload.photo_url = profilePhotoDataUri;

      const res = await fetch(`${API_BASE_URL}/v2/farmers/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.error?.message || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setFarmer((prev) => (prev ? { ...prev, name: data.name, photo_url: data.photo_url } : prev));
      setProfileVisible(false);
    } catch (e: any) {
      setProfileError(e.message || t.addFieldGenericError);
    } finally {
      setProfileSaving(false);
    }
  };

  const getTtsLangCode = (lang: LangKey) => {
    switch (lang) {
      case 'kn': return 'kn-IN';
      case 'te': return 'te-IN';
      case 'hi': return 'hi-IN';
      default: return 'en-US';
    }
  };

  const playAdvisoryVoice = async (advisory: any) => {
    if (!advisory) return;
    try {
      setIsPlayingAudio(true);
      setPlayingAdvisoryId(advisory.id);

      try { await Speech.stop(); } catch (e) {}

      const cleanText = getCleanTtsText(advisory.body, language);

      // Only advisories fetched from GET /v2/fields/{id}/advisories (tagged
      // _remote: true) have a real backend audio route. Local fallback/mock
      // advisories, scan-result summaries, and scan-history entries carry
      // client-generated ids (e.g. 'adv-001', 'scan-tab-adv', 'h1') that were
      // never issued by the backend -- requesting audio for them always 404s,
      // so skip the network hop and go straight to on-device speech.
      if (!advisory._remote) {
        Speech.speak(cleanText, {
          language: getTtsLangCode(language),
          onDone: () => {
            setIsPlayingAudio(false);
            setPlayingAdvisoryId(null);
          },
          onError: () => {
            setIsPlayingAudio(false);
            setPlayingAdvisoryId(null);
          }
        });
        return;
      }

      const audioUrl = `${API_BASE_URL}/v2/advisories/${advisory.id}/audio?language=${language}`;

      // Auth is now the backend's session cookie (Module 27), not a bearer
      // token -- react-native's fetch shares cookies via the native
      // networking layer, so no Authorization header is needed here.
      const response = await fetch(audioUrl);

      if (response.status === 503 || !response.ok) {
        Speech.speak(cleanText, {
          language: getTtsLangCode(language),
          onDone: () => {
            setIsPlayingAudio(false);
            setPlayingAdvisoryId(null);
          },
          onError: () => {
            setIsPlayingAudio(false);
            setPlayingAdvisoryId(null);
          }
        });
        return;
      }

      // Known limitation: expo-audio's player issues its own native HTTP
      // request, separate from the fetch() probe above, and may not share
      // react-native fetch's cookie jar on every platform -- if it 401s
      // against the session-cookie-protected audio route, this falls
      // through to the on-device Speech.speak fallback below via the
      // outer catch, same as any other audio failure.
      if (sound) {
        sound.remove();
      }
      const newPlayer = createAudioPlayer({ uri: audioUrl });
      setSound(newPlayer);
      newPlayer.addListener('playbackStatusUpdate', (status) => {
        if (status.didJustFinish) {
          setIsPlayingAudio(false);
          setPlayingAdvisoryId(null);
        }
      });
      newPlayer.play();
    } catch (e) {
      const cleanText = getCleanTtsText(advisory.body, language);
      Speech.speak(cleanText, {
        language: getTtsLangCode(language),
        onDone: () => {
          setIsPlayingAudio(false);
          setPlayingAdvisoryId(null);
        }
      });
    }
  };

  const previewLanguageSample = async (lang: LangKey) => {
    try {
      await Speech.stop();
    } catch (e) {}
    
    const samples: Record<LangKey, string> = {
      en: "Hello! Welcome to Agro Mirai smart farming assistant.",
      kn: "ನಮಸ್ಕಾರ! ಅಗ್ರೋ ಮಿರಾ ರೈತ ಸೇವೆಗೆ ಸ್ವಾಗತ.",
      te: "నమస్కారం! ఆగ్రో మిరాయ్ రైతు సహాయక సేవకు స్వాగతం.",
      hi: "नमस्ते! एग्रो मिराई किसान सेवा में आपका स्वागत है।"
    };
    
    const cleanSpeech = getCleanTtsText(samples[lang], lang);
    Speech.speak(cleanSpeech, { language: getTtsLangCode(lang) });
  };

  // Image Picking & AI Disease Analysis
  const pickImageFromGallery = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(t.galleryPermTitle, t.galleryPermBody);
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets[0]) {
      const uri = result.assets[0].uri;
      setSelectedImageUri(uri);
      await analyzeLeafImage(uri);
    }
  };

  const openEmbeddedCamera = async () => {
    if (!cameraPermission?.granted) {
      const result = await requestCameraPermission();
      if (!result.granted) {
        Alert.alert(t.cameraPermTitle, t.cameraPermBody);
        return;
      }
    }
    setEmbeddedCameraVisible(true);
  };

  const captureFromEmbeddedCamera = async () => {
    if (!cameraRef.current || !cameraReady) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
      if (photo?.uri) {
        setSelectedImageUri(photo.uri);
        setCameraReady(false);
        setEmbeddedCameraVisible(false);
        await analyzeLeafImage(photo.uri);
      }
    } catch (e) {
      Alert.alert(t.captureFailedTitle, t.captureFailedBody);
    }
  };

  const analyzeLeafImage = async (imageUri: string) => {
    if (!selectedField?.id) {
      Alert.alert(t.noFieldTitle, t.noFieldBody);
      return;
    }
    setIsAnalyzingImage(true);
    setScanResult(null);
    setScanError(false);
    try {
      const fieldId = selectedField.id;

      // Expo SDK 53+ replaces RN's classic fetch with its own spec-compliant
      // "Winter" fetch, whose FormData multipart encoder
      // (expo/src/winter/fetch/convertFormData.ts) only accepts a string, a
      // real Blob/File instance, or an object with a .bytes() method -- it
      // does NOT understand React Native's classic
      // { uri, name, type } file-part convention, even though that shape is
      // still shown in the type declarations. Appending that shape throws
      // "Unsupported FormDataPart implementation" every time under Expo's
      // fetch. The fix is to fetch the local file:// URI into a real Blob
      // first, then append the Blob -- not a header or FormData-shape tweak.
      const localFile = await fetch(imageUri);
      const imageBlob = await localFile.blob();

      const formData = new FormData();
      formData.append('image', imageBlob, 'leaf.jpg');

      console.log(`Posting image to ${API_BASE_URL}/v2/fields/${fieldId}/disease-risk/image`);
      const response = await fetch(`${API_BASE_URL}/v2/fields/${fieldId}/disease-risk/image`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
        },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setScanResult(data);
      } else {
        console.log(`Disease-risk image upload rejected: ${response.status}`);
        setScanError(true);
      }
    } catch (err: any) {
      console.log('Image upload exception:', err.message);
      setScanError(true);
    } finally {
      setIsAnalyzingImage(false);
    }
  };

  // Module 27: Name+Phone+OTP auth against the backend's
  // /v2/auth/request-otp and /v2/auth/verify-otp (decisions/0023). No
  // password, no email, and no client-side "demo login" shortcut --
  // the previous build's hardcoded demo_access_token_farmer_123 button
  // was the mobile-side twin of a backend security backdoor discarded
  // in the same module, and is removed outright here, not disabled.

  const handleRequestOtp = async () => {
    if (cooldownSeconds > 0) return;
    setAuthError('');

    if (!phoneInput.trim()) {
      setAuthError(t.phoneLabel);
      return;
    }
    if (authStep === 'ENTER_PHONE' && !nameInput.trim()) {
      setAuthError(t.nameLabel);
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v2/auth/request-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: phoneInput.trim(),
          name: nameInput.trim(),
          preferred_language: language,
        }),
      });

      if (res.status === 429) {
        setCooldownSeconds(60);
        setAuthError(t.pleaseWait + ' (60s)');
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setAuthError(body?.error?.message || 'Failed to send OTP.');
        return;
      }

      const body = await res.json();
      setIsNewFarmerPending(!!body.is_new_farmer);
      setAuthStep('ENTER_OTP');
      setOtpInput('');
      setCooldownSeconds(30);
    } catch (err: any) {
      console.error('request-otp error:', err);
      setAuthError(err.message || 'Failed to send OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    setAuthError('');
    if (!otpInput.trim()) {
      setAuthError(t.otpLabel);
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v2/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: phoneInput.trim(), otp: otpInput.trim() }),
      });

      if (!res.ok) {
        setAuthError(t.invalidOtp);
        return;
      }

      const data = await res.json();
      setFarmer({ id: data.id, name: data.name, phone: data.phone ?? null, photo_url: data.photo_url ?? null });
      await fetchBackendData();
      if (isNewFarmerPending) {
        setProfileSetupLang(detectedLang);
        setScreen('PROFILE_SETUP');
      } else {
        setScreen('HOME');
      }
    } catch (err: any) {
      console.error('verify-otp error:', err);
      setAuthError(err.message || t.invalidOtp);
    } finally {
      setIsLoading(false);
    }
  };

  const submitProfileSetup = async () => {
    setProfileSetupSubmitting(true);
    try {
      await fetch(`${API_BASE_URL}/v2/farmers/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferred_language: profileSetupLang }),
      }).catch(() => null);
    } finally {
      setLanguage(profileSetupLang);
      setIsNewFarmerPending(false);
      setProfileSetupSubmitting(false);
      setScreen('HOME');
    }
  };

  const handleChangeNumber = () => {
    setAuthStep('ENTER_PHONE');
    setOtpInput('');
    setAuthError('');
  };

  const handleSignOut = async () => {
    try {
      await fetch(`${API_BASE_URL}/v2/auth/logout`, { method: 'POST' });
    } catch (e) {
      console.log('Logout request failed (continuing to clear local state):', e);
    }
    setFarmer(null);
    setAuthStep('ENTER_PHONE');
    setPhoneInput('');
    setNameInput('');
    setOtpInput('');
    setScreen('LANG_PICKER');
  };

  const cycleLanguage = () => {
    const order: LangKey[] = ['kn', 'te', 'hi', 'en'];
    const currentIndex = order.indexOf(language);
    const nextLang = order[(currentIndex + 1) % order.length];
    setLanguage(nextLang);
    if (farmer) {
      fetch(`${API_BASE_URL}/v2/farmers/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferred_language: nextLang }),
      }).catch(() => null);
    }
  };

  // Screen 0: Splash Screen
  if (screen === 'SPLASH') {
    const splashLogoSize = Math.min(windowWidth * 0.65, 260);
    return (
      <SafeAreaView style={[styles.container, styles.splashContainer]}>
        <StatusBar barStyle="dark-content" backgroundColor={THEME.grainCream} />
        
        <View style={styles.splashCenterContent}>
          <AgroMiraiLogo size={splashLogoSize} useCropped={false} />
          <Text style={[styles.splashTagline, { fontSize: Math.max(15, 17 * scale) }]}>
            {t.splashTagline}
          </Text>
        </View>

        <View style={[styles.splashFooter, { paddingBottom: Math.max(20, insets.bottom + 10) }]}>
          <TouchableOpacity
            style={[styles.splashEnterBtn, { paddingVertical: Math.max(14, 18 * scale) }]}
            onPress={requestPermissionsAndDetectLanguage}
            activeOpacity={0.85}
            disabled={isDetectingLocation}
          >
            {isDetectingLocation ? (
              <ActivityIndicator color={THEME.grainCream} />
            ) : (
              <Text style={[styles.splashEnterBtnText, { fontSize: Math.max(18, 20 * scale) }]}>
                {t.getStarted}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Language auto-detection confirmation is a popup, not a dedicated screen
  // -- screen navigation already moved past this point by the time it's
  // shown, so this same modal node is rendered inside whichever of
  // AUTH/HOME is now underneath it.
  const langConfirmModal = (
    <Modal
      visible={langConfirmVisible}
      animationType="fade"
      transparent={true}
      onRequestClose={() => setLangConfirmVisible(false)}
    >
      <View style={modalStyles.modalOverlay}>
        <View style={styles.confirmCard}>
          <Icon name="location" size={40} color={THEME.brand700} />
          <Text style={styles.locationTitle}>{locationName}</Text>

          <View style={[styles.langPillBadge, { flexDirection: 'row', alignItems: 'center', gap: 6 }]}>
            <Icon name="globe" size={14} color={THEME.brand700} />
            <Text style={styles.langPillBadgeText}>{t.detectedLangPrefix} {LANG_DISPLAY_NAMES[detectedLang]}</Text>
          </View>

          <Text style={styles.confirmPromptText}>
            We set your regional language to <Text style={{ fontWeight: 'bold', color: THEME.brand900 }}>{LANG_DISPLAY_NAMES[detectedLang]}</Text>. Is this correct?
          </Text>

          <TouchableOpacity
            style={[styles.primaryButton, { marginTop: 20 }]}
            onPress={() => {
              previewLanguageSample(detectedLang);
              setLangConfirmVisible(false);
            }}
          >
            <Text style={styles.primaryButtonText}>{t.confirmLangBtn}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.changeLangOutlineBtn}
            onPress={() => {
              setLangConfirmVisible(false);
              setScreen('LANG_PICKER');
            }}
          >
            <Text style={styles.changeLangOutlineBtnText}>{t.changeLangBtn}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  // Screen 1: Language Picker
  if (screen === 'LANG_PICKER') {
    const headerLogoSize = Math.min(windowWidth * 0.28, 110);
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor={THEME.brand900} />
        
        <View style={styles.onboardingHeader}>
          <AgroMiraiLogo size={headerLogoSize} useCropped={true} />
          <Text style={[styles.onboardingSubtitle, { fontSize: Math.max(13, 14 * scale) }]}>
            {t.selectLang}
          </Text>
        </View>

        <ScrollView 
          contentContainerStyle={[styles.cardContainer, { paddingHorizontal: isSmallDevice ? 12 : 18 }]} 
          showsVerticalScrollIndicator={false}
        >
          {/* Kannada Card */}
          <TouchableOpacity 
            style={[styles.langCard, language === 'kn' && styles.selectedLangCard]} 
            onPress={() => {
              setLanguage('kn');
              previewLanguageSample('kn');
            }}
          >
            <Text style={styles.langScriptTitle}>ಕನ್ನಡ</Text>
            <TouchableOpacity style={[styles.previewBtn, { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }]} onPress={() => previewLanguageSample('kn')}>
              <Icon name="speaker" size={14} color={THEME.brand700} />
              <Text style={styles.previewBtnText}>ಕೇಳಿ</Text>
            </TouchableOpacity>
          </TouchableOpacity>

          {/* Telugu Card */}
          <TouchableOpacity 
            style={[styles.langCard, language === 'te' && styles.selectedLangCard]} 
            onPress={() => {
              setLanguage('te');
              previewLanguageSample('te');
            }}
          >
            <Text style={styles.langScriptTitle}>తెలుగు</Text>
            <TouchableOpacity style={[styles.previewBtn, { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }]} onPress={() => previewLanguageSample('te')}>
              <Icon name="speaker" size={14} color={THEME.brand700} />
              <Text style={styles.previewBtnText}>వినండి</Text>
            </TouchableOpacity>
          </TouchableOpacity>

          {/* Hindi Card */}
          <TouchableOpacity 
            style={[styles.langCard, language === 'hi' && styles.selectedLangCard]} 
            onPress={() => {
              setLanguage('hi');
              previewLanguageSample('hi');
            }}
          >
            <Text style={styles.langScriptTitle}>हिंदी</Text>
            <TouchableOpacity style={[styles.previewBtn, { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }]} onPress={() => previewLanguageSample('hi')}>
              <Icon name="speaker" size={14} color={THEME.brand700} />
              <Text style={styles.previewBtnText}>सुनें</Text>
            </TouchableOpacity>
          </TouchableOpacity>

          {/* English Card */}
          <TouchableOpacity 
            style={[styles.langCard, language === 'en' && styles.selectedLangCard]} 
            onPress={() => {
              setLanguage('en');
              previewLanguageSample('en');
            }}
          >
            <Text style={styles.langScriptTitle}>English</Text>
            <TouchableOpacity style={[styles.previewBtn, { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }]} onPress={() => previewLanguageSample('en')}>
              <Icon name="speaker" size={14} color={THEME.brand700} />
              <Text style={styles.previewBtnText}>Listen</Text>
            </TouchableOpacity>
          </TouchableOpacity>
        </ScrollView>

        <View style={[styles.footerBar, { paddingBottom: Math.max(16, insets.bottom + 8) }]}>
          <TouchableOpacity 
            style={styles.primaryButton}
            onPress={() => {
              if (farmer) {
                setScreen('HOME');
              } else if (!onboardingSeen) {
                setScreen('ONBOARD_1');
              } else {
                setScreen('AUTH');
              }
            }}
          >
            <Text style={styles.primaryButtonText}>{t.continue}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Screens 1b/1c: First-run onboarding (shown once, per AsyncStorage's
  // 'onboardingSeen' flag -- module 31). Two screens max per the module
  // brief ("this is a utility app, not a consumer social app").
  if (screen === 'ONBOARD_1' || screen === 'ONBOARD_2') {
    const isFirst = screen === 'ONBOARD_1';
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="dark-content" backgroundColor={THEME.grainCream} />
        <View style={styles.onboardScreen}>
          <View style={styles.onboardIconCircle}>
            <Icon name={isFirst ? 'leaf' : 'mic'} size={44} color={THEME.brand700} />
          </View>
          <Text style={styles.onboardTitle}>{isFirst ? t.onboard1Title : t.onboard2Title}</Text>
          <Text style={styles.onboardBody}>{isFirst ? t.onboard1Body : t.onboard2Body}</Text>

          <View style={styles.onboardDotsRow}>
            <View style={[styles.onboardDot, isFirst && styles.onboardDotActive]} />
            <View style={[styles.onboardDot, !isFirst && styles.onboardDotActive]} />
          </View>
        </View>

        <View style={[styles.footerBar, { paddingBottom: Math.max(16, insets.bottom + 8) }]}>
          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() => {
              if (isFirst) {
                setScreen('ONBOARD_2');
              } else {
                finishOnboarding();
              }
            }}
          >
            <Text style={styles.primaryButtonText}>{isFirst ? t.continue : t.onboardDoneBtn}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={{ marginTop: 10, alignItems: 'center' }} onPress={finishOnboarding}>
            <Text style={styles.onboardSkipText}>{t.onboardSkip}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Screen 2: Auth Screen
  if (screen === 'AUTH') {
    const logoSize = Math.min(windowWidth * 0.25, 100);
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor={THEME.brand900} />
        
        <View style={styles.authTopHeader}>
          <TouchableOpacity 
            style={styles.backButton}
            onPress={() => setScreen('LANG_PICKER')}
          >
            <Text style={styles.backButtonText}>{t.back}</Text>
          </TouchableOpacity>

          <TouchableOpacity style={[styles.langCyclePill, { flexDirection: 'row', alignItems: 'center', gap: 5 }]} onPress={cycleLanguage}>
            <Icon name="globe" size={13} color={THEME.brand900} />
            <Text style={styles.langCycleText}>{language.toUpperCase()}</Text>
          </TouchableOpacity>
        </View>

        <ScrollView
          contentContainerStyle={[styles.scrollContent, { paddingHorizontal: isSmallDevice ? 12 : 20 }]}
          showsVerticalScrollIndicator={false}
        >
          <View style={{ alignItems: 'center', marginVertical: 12 }}>
            <AgroMiraiLogo size={logoSize} useCropped={true} />
          </View>

          <Text style={[styles.screenHeading, { fontSize: Math.max(20, 24 * scale) }]}>
            {t.loginTitle}
          </Text>

          {authError ? (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>{authError}</Text>
              {cooldownSeconds > 0 && (
                <Text style={styles.cooldownText}>
                  {t.pleaseWait} ({cooldownSeconds}s)
                </Text>
              )}
            </View>
          ) : null}

          {authStep === 'ENTER_PHONE' ? (
            <>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>{t.nameLabel}</Text>
                <TextInput
                  style={styles.input}
                  value={nameInput}
                  onChangeText={setNameInput}
                  autoCapitalize="words"
                  placeholder={t.namePlaceholder}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>{t.phoneLabel}</Text>
                <TextInput
                  style={styles.input}
                  value={phoneInput}
                  onChangeText={setPhoneInput}
                  autoCapitalize="none"
                  keyboardType="phone-pad"
                  placeholder={t.phonePlaceholder}
                />
              </View>

              <TouchableOpacity
                style={[styles.primaryButton, (isLoading || cooldownSeconds > 0) && styles.buttonDisabled]}
                onPress={handleRequestOtp}
                disabled={isLoading || cooldownSeconds > 0}
              >
                {isLoading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.primaryButtonText}>
                    {cooldownSeconds > 0 ? `${t.pleaseWait} (${cooldownSeconds}s)` : t.sendOtpBtn}
                  </Text>
                )}
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.otpSentHint}>{t.otpSentHint}</Text>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>{t.otpLabel}</Text>
                <TextInput
                  style={styles.input}
                  value={otpInput}
                  onChangeText={setOtpInput}
                  keyboardType="number-pad"
                  maxLength={6}
                  placeholder={t.otpPlaceholder}
                />
              </View>

              <TouchableOpacity
                style={[styles.primaryButton, isLoading && styles.buttonDisabled]}
                onPress={handleVerifyOtp}
                disabled={isLoading}
              >
                {isLoading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.primaryButtonText}>{t.verifyOtpBtn}</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.switchAuthBtn}
                onPress={handleRequestOtp}
                disabled={isLoading || cooldownSeconds > 0}
              >
                <Text style={styles.switchAuthText}>
                  {cooldownSeconds > 0 ? `${t.resendOtpBtn} (${cooldownSeconds}s)` : t.resendOtpBtn}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.switchAuthBtn} onPress={handleChangeNumber}>
                <Text style={styles.switchAuthText}>{t.changeNumberBtn}</Text>
              </TouchableOpacity>
            </>
          )}
        </ScrollView>
        {langConfirmModal}
      </SafeAreaView>
    );
  }

  // Screen 2.5: First-time Profile Setup -- shown once, only for a farmer
  // request-otp just told us is new (is_new_farmer). No typing: name and
  // phone are already collected (auth step 1), so all that's left is
  // confirming the language, and that's a single tap on a pre-selected chip.
  if (screen === 'PROFILE_SETUP') {
    const langOptions: { key: LangKey; label: string }[] = [
      { key: 'en', label: 'English' },
      { key: 'kn', label: 'ಕನ್ನಡ' },
      { key: 'te', label: 'తెలుగు' },
      { key: 'hi', label: 'हिंदी' },
    ];
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor={THEME.brand900} />
        <View style={styles.onboardingHeader}>
          <AgroMiraiLogo size={90} useCropped={true} />
        </View>
        <View style={{ flex: 1, padding: 20, justifyContent: 'center', alignItems: 'center' }}>
          <View style={styles.confirmCard}>
            <Text style={{ fontSize: 24, fontWeight: 'bold', color: THEME.brand900, marginBottom: 6 }}>
              {t.profileSetupTitle}
            </Text>
            <Text style={{ fontSize: 15, color: THEME.ink600, marginBottom: 18, textAlign: 'center' }}>
              {t.profileSetupSub}
            </Text>

            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, justifyContent: 'center' }}>
              {langOptions.map((opt) => (
                <TouchableOpacity
                  key={opt.key}
                  onPress={() => setProfileSetupLang(opt.key)}
                  style={[modalStyles.chip, { paddingVertical: 12, paddingHorizontal: 20 }, profileSetupLang === opt.key && modalStyles.chipActive]}
                >
                  <Text style={[modalStyles.chipText, { fontSize: 15, textTransform: 'none' }, profileSetupLang === opt.key && modalStyles.chipTextActive]}>
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity
              style={[styles.primaryButton, { marginTop: 26, width: '100%' }]}
              onPress={submitProfileSetup}
              disabled={profileSetupSubmitting}
            >
              {profileSetupSubmitting ? (
                <ActivityIndicator color={THEME.grainCream} />
              ) : (
                <Text style={styles.primaryButtonText}>{t.profileSetupContinue}</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // Module 31: inline expandable fact-panel content for the Home tab's
  // Irrigation/Crop cards, replacing the old category-detail Modal. Same
  // real, backend-computed fields it always showed -- urgentAdvisory.body
  // (GET /v2/fields/{id}/advisories -> Advisory.body) and the active
  // field's current_crop/area_ha (GET /v2/fields -> Field.current_crop /
  // .area_ha, per specs/core/openapi.yaml) -- nothing new invented here.
  const renderIrrigationFacts = () => (
    <View style={{ gap: 10 }}>
      {urgentAdvisory ? (
        <>
          <Text style={styles.inlineFactRowValue}>{urgentAdvisory.body}</Text>
          <TouchableOpacity
            style={[modalStyles.playResultVoiceBtn, { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }]}
            onPress={() => playAdvisoryVoice(urgentAdvisory)}
          >
            <Icon name="speaker" size={14} color={THEME.brand700} />
            <Text style={modalStyles.playResultVoiceText}>{t.listenVoice}</Text>
          </TouchableOpacity>
        </>
      ) : (
        <Text style={styles.inlineFactRowValue}>{t.emptyAdvisories}</Text>
      )}
    </View>
  );

  const renderCropFacts = () => (
    <View style={{ gap: 8 }}>
      {selectedField ? (
        <>
          <View style={styles.inlineFactRow}>
            <Text style={styles.inlineFactRowLabel}>{t.cropTypeLabel}</Text>
            <Text style={styles.inlineFactRowValue}>{selectedField.current_crop || '—'}</Text>
          </View>
          <View style={styles.inlineFactRow}>
            <Text style={styles.inlineFactRowLabel}>{t.fieldAreaLabel}</Text>
            <Text style={styles.inlineFactRowValue}>{selectedField.area_ha ? `${selectedField.area_ha} ha` : '—'}</Text>
          </View>
        </>
      ) : (
        <Text style={styles.inlineFactRowValue}>{t.emptyFields}</Text>
      )}
    </View>
  );

  // Screen 3: Premium Dashboard & 4-Tab Interface
  const urgentAdvisory = advisories[0];
  const gridCardWidth = (windowWidth - (isSmallDevice ? 32 : 44) - 16) / 3;

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={THEME.brand900} />
      
      {/* Top Navigation Bar */}
      <View style={styles.dashHeaderNav}>
        <View style={styles.dashBrandGroup}>
          <AgroMiraiLogo size={38} useCropped={true} />
          <Text style={[styles.dashBrandName, { fontSize: isSmallDevice ? 15 : 18 }]}>AGRO MIRAI</Text>
        </View>

        <View style={styles.dashHeaderActions}>
          <TouchableOpacity style={[styles.dashLangToggle, { flexDirection: 'row', alignItems: 'center', gap: 5 }]} onPress={cycleLanguage}>
            <Icon name="globe" size={13} color={THEME.brand900} />
            <Text style={styles.dashLangText}>{language.toUpperCase()}</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.dashAvatarCircle} onPress={openProfile}>
            {farmer?.photo_url ? (
              <Image source={{ uri: farmer.photo_url }} style={styles.dashAvatarImage} />
            ) : (
              <Text style={styles.dashAvatarInitial}>{(farmer?.name || '?').charAt(0).toUpperCase()}</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity style={styles.dashLogoutCircle} onPress={handleSignOut}>
            <Icon name="logout" size={16} color={THEME.ink700} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Module 31: the field-selector pill that used to live in the Home
          header was removed per the redesign brief -- Home no longer shows
          a field picker; the active field and "Add a field" now live in the
          Settings tab (see the 'settings' activeTab block below), reusing
          the same openAddField() handler this pill used to call. A
          brand-new zero-field farmer still has a clear path in: the
          zero-fields empty-state card rendered inside the 'home' tab below
          links to Settings instead of opening this pill directly. */}

      {/* Main Tab Screen Content Container */}
      <View style={{ flex: 1 }}>
        {/* --- TAB 1: HOME --- */}
        {activeTab === 'home' && (
          <ScrollView 
            contentContainerStyle={[styles.dashScrollContent, { paddingHorizontal: isSmallDevice ? 12 : 16 }]} 
            showsVerticalScrollIndicator={false}
          >
            {/* Module 31: zero-field empty state -- with the header field
                pill gone, a brand-new farmer with no fields yet needs an
                explicit path into Add-Field. Points at Settings, where the
                "Fields" group now lives, rather than reopening the modal
                directly, so the farmer learns where field management now
                lives. */}
            {fields.length === 0 && (
              <TouchableOpacity
                style={styles.emptyFieldCard}
                onPress={() => setActiveTab('settings')}
                activeOpacity={0.85}
              >
                <Icon name="field" size={26} color={THEME.brand700} />
                <View style={{ flex: 1, marginLeft: 10 }}>
                  <Text style={styles.emptyFieldTitle}>{t.homeNoFieldTitle}</Text>
                  <Text style={styles.emptyFieldSub}>{t.homeNoFieldSub}</Text>
                </View>
                <Icon name="chevron-right" size={18} color={THEME.brand700} />
              </TouchableOpacity>
            )}

            {/* Embedded AI Leaf Disease Scanner Launcher */}
            <TouchableOpacity
              style={[styles.scanLeafBanner, { flexDirection: 'row', alignItems: 'center' }]}
              onPress={() => openEmbeddedCamera()}
              activeOpacity={0.85}
            >
              <Icon name="camera" size={22} color={THEME.brand900} />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={[styles.scanLeafTitle, { fontSize: isSmallDevice ? 14 : 16 }]}>{t.scanLeaf}</Text>
                <Text style={styles.scanLeafSub}>{t.scanLeafSub}</Text>
              </View>
              <Icon name="chevron-right" size={16} color={THEME.brand900} />
            </TouchableOpacity>

            {/* Zone 1 — Hero Audio Advisory Banner */}
            <View style={styles.heroBannerCard}>
              <View style={styles.heroBannerHeader}>
                <View style={styles.heroBadgeUrgent}>
                  <Text style={styles.heroBadgeUrgentText}>{t.urgentPriority}</Text>
                </View>
                <Text style={styles.heroDateText}>{t.todayAction}</Text>
              </View>

              {urgentAdvisory ? (
                <>
                  <TouchableOpacity
                    style={[styles.heroAudioPlayBar, isPlayingAudio && styles.heroAudioPlayBarActive]}
                    onPress={() => playAdvisoryVoice(urgentAdvisory)}
                    activeOpacity={0.85}
                  >
                    <View style={styles.heroPlayCircle}>
                      <Icon name={isPlayingAudio ? 'pause' : 'play'} size={16} color={THEME.grainCream} />
                    </View>
                    <View style={styles.heroAudioMeta}>
                      <Text style={styles.heroAudioTitle}>
                        {isPlayingAudio ? t.playingAudio : t.todayAdvisory}
                      </Text>
                      <Text style={styles.heroAudioWaveText}>━━━━━━━●━━━━━ 0:25</Text>
                    </View>
                  </TouchableOpacity>

                  <View style={styles.heroTranscriptBox}>
                    <Text style={styles.heroTranscriptBody}>{urgentAdvisory.body}</Text>
                  </View>
                </>
              ) : (
                <View style={styles.heroTranscriptBox}>
                  <Text style={styles.heroTranscriptBody}>{t.emptyAdvisories}</Text>
                </View>
              )}
            </View>

            {/* Zone 2 — Feature Quick Access Grid */}
            <View style={styles.categoryGridSection}>
              <Text style={styles.sectionTitle}>{t.fieldActions}</Text>

              <View style={styles.gridRow}>
                {/* Irrigation */}
                <TouchableOpacity 
                  style={[styles.gridCard, { width: gridCardWidth }]}
                  activeOpacity={0.8}
                  onPress={() => setActiveModal(activeModal === 'irrigation' ? null : 'irrigation')}
                >
                  <View style={[styles.gridDot, { backgroundColor: THEME.statusCaution }]} />
                  <View style={[styles.gridIconBg, { backgroundColor: '#E0F2FE' }]}>
                    <Icon name="drop" size={20} color="#0369A1" />
                  </View>
                  <Text style={styles.gridTitle}>{t.irrigation}</Text>
                  <Text style={styles.gridSub}>{t.gridSubIrrigation}</Text>
                  <Icon name={activeModal === 'irrigation' ? 'chevron-up' : 'chevron-down'} size={14} color={THEME.ink500} />
                </TouchableOpacity>

                {/* Disease Risk / Scanner */}
                <TouchableOpacity
                  style={[styles.gridCard, { width: gridCardWidth }]}
                  activeOpacity={0.8}
                  onPress={() => openEmbeddedCamera()}
                >
                  <View style={[styles.gridDot, { backgroundColor: THEME.statusUrgent }]} />
                  <View style={[styles.gridIconBg, { backgroundColor: '#FEE2E2' }]}>
                    <Icon name="blight" size={20} color="#B23A2E" />
                  </View>
                  <Text style={styles.gridTitle}>{t.disease}</Text>
                  <Text style={styles.gridSub}>{t.gridSubDisease}</Text>
                </TouchableOpacity>

                {/* Crop Health */}
                <TouchableOpacity
                  style={[styles.gridCard, { width: gridCardWidth }]}
                  activeOpacity={0.8}
                  onPress={() => setActiveModal(activeModal === 'crop' ? null : 'crop')}
                >
                  <View style={[styles.gridDot, { backgroundColor: THEME.statusGood }]} />
                  <View style={[styles.gridIconBg, { backgroundColor: '#DCFCE7' }]}>
                    <Icon name="sprout" size={20} color="#2F7D4F" />
                  </View>
                  <Text style={styles.gridTitle}>{t.crop}</Text>
                  <Text style={styles.gridSub}>{t.gridSubCrop}</Text>
                  <Icon name={activeModal === 'crop' ? 'chevron-up' : 'chevron-down'} size={14} color={THEME.ink500} />
                </TouchableOpacity>
              </View>

              {/* Module 31: inline expandable fact panel, replacing the
                  former category-detail <Modal>. Renders the same
                  label/value rows the backend already computes (no new
                  data invented) -- see irrigationModalContent/
                  cropModalContent below, now rendered inline instead of in
                  a Modal overlay. No sparkline: GET /v2/fields/{id}/irrigation
                  (specs/core/openapi.yaml IrrigationAdvice schema) returns
                  only the current advisory, not a historical time series,
                  so a trend chart would have to be fabricated client-side --
                  flagged in the module report as a real backend gap instead
                  of faked here. */}
              {activeModal === 'irrigation' && (
                <View style={styles.inlineFactPanel}>
                  <Text style={styles.inlineFactPanelTitle}>{t.modalIrrigationTitle}</Text>
                  {renderIrrigationFacts()}
                </View>
              )}
              {activeModal === 'crop' && (
                <View style={styles.inlineFactPanel}>
                  <Text style={styles.inlineFactPanelTitle}>{t.modalCropTitle}</Text>
                  {renderCropFacts()}
                </View>
              )}
            </View>
          </ScrollView>
        )}

        {/* --- TAB 2: AI SCAN --- */}
        {activeTab === 'scan' && (
          <ScrollView contentContainerStyle={styles.tabContentContainer} showsVerticalScrollIndicator={false}>
            <View style={styles.tabHeaderCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Icon name="camera" size={20} color={THEME.brand900} />
                <Text style={styles.tabHeaderTitle}>{t.scanTitle}</Text>
              </View>
              <Text style={styles.tabHeaderSub}>{t.scanTabSub}</Text>
            </View>

            <TouchableOpacity
              style={styles.bigScanLauncherBtn}
              onPress={() => openEmbeddedCamera()}
              activeOpacity={0.85}
            >
              <Icon name="camera" size={40} color={THEME.brand900} />
              <Text style={styles.bigScanLauncherTitle}>{t.scanLeaf}</Text>
              <Text style={styles.bigScanLauncherSub}>{t.embeddedCamSub}</Text>
            </TouchableOpacity>

            {/* Gallery only here -- camera capture already has one entry
                point (the launcher above, which opens the real in-app
                camera). A second "take photo" button here duplicated it
                with takeCameraPhoto()'s native OS camera picker instead,
                a genuinely different, unbranded UX a user could land on
                by tapping the more discoverable AI Scan tab -- real bug
                found during a live device walkthrough. */}
            <View style={{ marginTop: 12 }}>
              <TouchableOpacity style={modalStyles.pickerBtn} onPress={pickImageFromGallery}>
                <Text style={modalStyles.pickerBtnText}>{t.pickGallery}</Text>
              </TouchableOpacity>
            </View>

            {selectedImageUri && (
              <View style={[modalStyles.resultBox, { marginTop: 16 }]}>
                <Image source={{ uri: selectedImageUri }} style={modalStyles.previewImage} />
                {isAnalyzingImage ? (
                  <View style={{ paddingVertical: 14, alignItems: 'center' }}>
                    <ActivityIndicator size="large" color={THEME.brand800} />
                    <Text style={{ marginTop: 8, color: THEME.brand900, fontWeight: '600' }}>{t.analyzing}</Text>
                  </View>
                ) : scanError ? (
                  <View style={{ paddingVertical: 14, alignItems: 'center' }}>
                    <Text style={{ color: THEME.statusUrgent, fontWeight: '700', marginBottom: 6, textAlign: 'center' }}>{t.scanErrorTitle}</Text>
                    <Text style={{ color: THEME.ink600, textAlign: 'center', marginBottom: 12 }}>{t.scanErrorBody}</Text>
                    <TouchableOpacity style={modalStyles.pickerBtn} onPress={() => selectedImageUri && analyzeLeafImage(selectedImageUri)}>
                      <Text style={modalStyles.pickerBtnText}>{t.retryBtn}</Text>
                    </TouchableOpacity>
                  </View>
                ) : scanResult ? (
                  <View>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <Icon name="blight" size={16} color={THEME.statusUrgent} />
                        <Text style={modalStyles.diseaseResultTitle}>{scanResult.disease_name || scanResult.disease || t.diseaseNameFallback}</Text>
                      </View>
                      <Text style={modalStyles.confidenceBadge}>{((scanResult.confidence || 0.95) * 100).toFixed(0)}% {t.aiMatchLabel}</Text>
                    </View>
                    <Text style={modalStyles.recommendationBody}>{scanResult.recommendation || scanResult.recommended_action}</Text>
                    <TouchableOpacity
                      style={[modalStyles.playResultVoiceBtn, { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }]}
                      onPress={() => playAdvisoryVoice({ id: 'scan-tab-adv', body: scanResult.recommendation || scanResult.recommended_action })}
                    >
                      <Icon name="speaker" size={14} color={THEME.brand700} />
                      <Text style={modalStyles.playResultVoiceText}>{t.listenVoice}</Text>
                    </TouchableOpacity>
                  </View>
                ) : null}
              </View>
            )}
          </ScrollView>
        )}

        {/* --- TAB 3: RECORDS (Module 31: merges the former History +
            Advisories tabs into one filterable card list. Both source
            lists -- `advisories` (real GET /v2/fields/{id}/advisories
            results) and `scanHistory` (real disease-scan results from this
            session; still session-only, no backend endpoint persists scan
            history -- see the module's known-limitations note) -- already
            existed; this only changes how they're presented, no new
            backend calls invented. */}
        {activeTab === 'records' && (() => {
          type RecordItem = { key: string; kind: 'irrigation' | 'disease'; timestamp: string; title: string; body: string; tag: string; onPlay: () => void; playing: boolean };
          const recordItems: RecordItem[] = [
            ...advisories.map((adv, idx): RecordItem => ({
              key: `adv-${adv.id || idx}`,
              kind: 'irrigation',
              timestamp: adv.created_at || adv.date || '',
              title: adv.title || t.todayAction,
              body: adv.body,
              tag: (adv.urgency || 'moderate').toUpperCase(),
              onPlay: () => playAdvisoryVoice(adv),
              playing: playingAdvisoryId === adv.id && isPlayingAudio,
            })),
            ...scanHistory.map((item): RecordItem => ({
              key: `scan-${item.id}`,
              kind: 'disease',
              timestamp: item.date || '',
              title: item.disease,
              body: item.recommendation,
              tag: `${((item.confidence || 0.9) * 100).toFixed(0)}%`,
              onPlay: () => playAdvisoryVoice({ id: item.id, body: item.recommendation }),
              playing: playingAdvisoryId === item.id && isPlayingAudio,
            })),
          ];
          const filtered = recordItems.filter((r) => recordsFilter === 'all' || r.kind === recordsFilter);

          return (
            <ScrollView contentContainerStyle={styles.tabContentContainer} showsVerticalScrollIndicator={false}>
              <View style={styles.tabHeaderCard}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Icon name="list" size={20} color={THEME.brand900} />
                  <Text style={styles.tabHeaderTitle}>{t.tabRecords}</Text>
                </View>
                <Text style={styles.tabHeaderSub}>{t.recordsSubtitle}</Text>
              </View>

              <View style={styles.recordsFilterRow}>
                {(['all', 'irrigation', 'disease'] as const).map((f) => (
                  <TouchableOpacity
                    key={f}
                    style={[styles.recordsFilterChip, recordsFilter === f && styles.recordsFilterChipActive]}
                    onPress={() => setRecordsFilter(f)}
                  >
                    <Text style={[styles.recordsFilterChipText, recordsFilter === f && styles.recordsFilterChipTextActive]}>
                      {f === 'all' ? t.recordsFilterAll : f === 'irrigation' ? t.recordsFilterIrrigation : t.recordsFilterDisease}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {filtered.length === 0 ? (
                <View style={styles.tabHeaderCard}>
                  <Text style={styles.tabHeaderSub}>{t.emptyRecords}</Text>
                </View>
              ) : filtered.map((r) => (
                <View
                  key={r.key}
                  style={[
                    styles.recordCard,
                    { borderLeftColor: r.kind === 'disease' ? THEME.statusUrgent : THEME.statusCaution },
                  ]}
                >
                  <View style={styles.recordCardHeader}>
                    <Icon name={r.kind === 'disease' ? 'blight' : 'drop'} size={18} color={r.kind === 'disease' ? THEME.statusUrgent : THEME.statusCaution} />
                    <Text style={styles.recordCardTitle} numberOfLines={1}>{r.title}</Text>
                    <Text style={styles.recordCardTag}>{r.tag}</Text>
                  </View>
                  {!!r.timestamp && <Text style={styles.recordCardTimestamp}>{r.timestamp}</Text>}
                  <Text style={styles.recordCardBody} numberOfLines={2}>{r.body}</Text>
                  <TouchableOpacity style={styles.recordCardPlayBtn} onPress={r.onPlay}>
                    <Icon name={r.playing ? 'pause' : 'play'} size={13} color={THEME.brand700} />
                    <Text style={styles.recordCardPlayText}>{t.listenVoice}</Text>
                  </TouchableOpacity>
                </View>
              ))}
            </ScrollView>
          );
        })()}

        {/* --- TAB 4: SETTINGS (new, Module 31) --- */}
        {activeTab === 'settings' && (
          <ScrollView contentContainerStyle={styles.tabContentContainer} showsVerticalScrollIndicator={false}>
            <View style={styles.tabHeaderCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Icon name="settings" size={20} color={THEME.brand900} />
                <Text style={styles.tabHeaderTitle}>{t.tabSettings}</Text>
              </View>
            </View>

            <Text style={styles.settingsGroupLabel}>{t.settingsFieldsGroup}</Text>
            <View style={styles.settingsGroupCard}>
              <View style={styles.settingsRow}>
                <Icon name="field" size={18} color={THEME.brand700} />
                <View style={{ flex: 1, marginLeft: 10 }}>
                  <Text style={styles.settingsRowLabel}>{t.settingsActiveFieldLabel}</Text>
                  <Text style={styles.settingsRowValue} numberOfLines={1}>
                    {selectedField ? (selectedField.name || selectedField.current_crop || t.selectField) : t.settingsNoFieldYet}
                  </Text>
                </View>
              </View>
              <TouchableOpacity style={[styles.settingsRow, styles.settingsRowButton]} onPress={openAddField}>
                <Icon name="bolt" size={18} color={THEME.brand700} />
                <Text style={[styles.settingsRowLabel, { flex: 1, marginLeft: 10 }]}>{t.settingsAddFieldRow}</Text>
                <Icon name="chevron-right" size={16} color={THEME.ink500} />
              </TouchableOpacity>
            </View>

            <Text style={styles.settingsGroupLabel}>{t.settingsPreferencesGroup}</Text>
            <View style={styles.settingsGroupCard}>
              <TouchableOpacity style={[styles.settingsRow, styles.settingsRowButton]} onPress={cycleLanguage}>
                <Icon name="globe" size={18} color={THEME.brand700} />
                <Text style={[styles.settingsRowLabel, { flex: 1, marginLeft: 10 }]}>{t.settingsLanguageRow}</Text>
                <Text style={styles.settingsRowValue}>{LANG_DISPLAY_NAMES[language]}</Text>
              </TouchableOpacity>
              {/* Module 31 note: an "Ask AGRO MIRAI" voice-chat row was
                  considered per the module brief, but was deliberately
                  omitted -- grepping this file found no client-side call to
                  POST /v2/stt anywhere (voice playback via
                  playAdvisoryVoice/previewLanguageSample only ever calls
                  GET /v2/advisories/{id}/audio and on-device TTS), so a
                  chat-style STT entry point here would be a dead button. */}
            </View>
          </ScrollView>
        )}
      </View>

      {/* --- 4-TAB BOTTOM NAVIGATION BAR --- */}
      <View style={[styles.bottomTabBar, { paddingBottom: Math.max(10, insets.bottom) }]}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'home' && styles.activeTabItem]}
          onPress={() => setActiveTab('home')}
        >
          <Icon name="home" size={20} color={activeTab === 'home' ? THEME.brand700 : THEME.ink500} />
          <Text style={[styles.tabLabel, activeTab === 'home' && styles.activeTabLabel]}>{t.tabHome}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'scan' && styles.activeTabItem]}
          onPress={() => setActiveTab('scan')}
        >
          <Icon name="camera" size={20} color={activeTab === 'scan' ? THEME.brand700 : THEME.ink500} />
          <Text style={[styles.tabLabel, activeTab === 'scan' && styles.activeTabLabel]}>{t.tabScan}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'records' && styles.activeTabItem]}
          onPress={() => setActiveTab('records')}
        >
          <Icon name="list" size={20} color={activeTab === 'records' ? THEME.brand700 : THEME.ink500} />
          <Text style={[styles.tabLabel, activeTab === 'records' && styles.activeTabLabel]}>{t.tabRecords}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'settings' && styles.activeTabItem]}
          onPress={() => setActiveTab('settings')}
        >
          <Icon name="settings" size={20} color={activeTab === 'settings' ? THEME.brand700 : THEME.ink500} />
          <Text style={[styles.tabLabel, activeTab === 'settings' && styles.activeTabLabel]}>{t.tabSettings}</Text>
        </TouchableOpacity>
      </View>

      {/* --- FULL-BLEED LEAF SCAN CAMERA --- */}
      <Modal
        visible={embeddedCameraVisible}
        animationType="slide"
        transparent={false}
        onRequestClose={() => { setCameraReady(false); setEmbeddedCameraVisible(false); }}
      >
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          {cameraPermission?.granted && (
            <CameraView
              ref={cameraRef}
              style={StyleSheet.absoluteFill}
              facing="back"
              flash={cameraFlash}
              onCameraReady={() => setCameraReady(true)}
            />
          )}

          {/* Corner-bracket reticle, not a boxed guide */}
          <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, justifyContent: 'center', alignItems: 'center' }}>
            <View style={{ width: 220, height: 220 }}>
              {[
                { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3 },
                { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3 },
                { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3 },
                { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3 },
              ].map((corner, i) => (
                <View
                  key={i}
                  style={{ position: 'absolute', width: 32, height: 32, borderColor: '#FFFFFF', borderRadius: 6, ...corner }}
                />
              ))}
            </View>
          </View>

          {/* Top-left back chevron only, no header bar */}
          <View style={{ position: 'absolute', top: Math.max(16, insets.top), left: 16 }}>
            <TouchableOpacity
              onPress={() => { setCameraReady(false); setEmbeddedCameraVisible(false); }}
              style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'center', alignItems: 'center' }}
            >
              <Text style={{ color: '#FFFFFF', fontSize: 22, fontWeight: '600' }}>‹</Text>
            </TouchableOpacity>
          </View>

          {/* Floating translucent control bar */}
          <BlurView
            intensity={40}
            tint="dark"
            style={{
              position: 'absolute',
              left: 20,
              right: 20,
              bottom: Math.max(24, insets.bottom + 12),
              borderRadius: 32,
              paddingVertical: 14,
              paddingHorizontal: 24,
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
              overflow: 'hidden',
              backgroundColor: 'rgba(15,23,42,0.35)',
            }}
          >
            <TouchableOpacity
              style={{ padding: 8 }}
              onPress={() => {
                setCameraReady(false);
                setEmbeddedCameraVisible(false);
                pickImageFromGallery();
              }}
            >
              <Icon name="gallery" size={24} color="#FFFFFF" />
            </TouchableOpacity>

            <TouchableOpacity
              style={{ width: 68, height: 68, borderRadius: 34, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center' }}
              onPress={captureFromEmbeddedCamera}
            >
              <View style={{ width: 56, height: 56, borderRadius: 28, borderWidth: 3, borderColor: THEME.brand500 }} />
            </TouchableOpacity>

            <TouchableOpacity
              style={{ padding: 8, opacity: cameraFlash === 'on' ? 1 : 0.5 }}
              onPress={() => setCameraFlash(cameraFlash === 'off' ? 'on' : 'off')}
            >
              <Icon name="bolt" size={24} color="#FFFFFF" />
            </TouchableOpacity>
          </BlurView>
        </View>
      </Modal>

      {/* Module 31: the old category-detail <Modal> (irrigation/crop) was
          removed -- those fact panels are now rendered inline and
          expandable on the Home tab via renderIrrigationFacts()/
          renderCropFacts() (defined above MainApp's return, next to the
          other small render helpers), toggled by the same `activeModal`
          state the grid cards already used, just no longer opening an
          overlay. */}

      {/* --- ADD FIELD MODAL --- */}
      <Modal
        visible={addFieldVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setAddFieldVisible(false)}
      >
        <View style={modalStyles.modalOverlay}>
          <View style={[modalStyles.modalCard, { maxHeight: windowHeight * 0.85 }]}>
            <View style={modalStyles.modalHeader}>
              <Text style={modalStyles.modalTitle}>{t.addFieldTitle}</Text>
              <TouchableOpacity onPress={() => setAddFieldVisible(false)}>
                <Icon name="close" size={20} color={THEME.ink700} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginBottom: 6 }}>{t.addFieldNameLabel}</Text>
              <TextInput
                style={modalStyles.textInput}
                value={addFieldName}
                onChangeText={setAddFieldName}
                placeholder={t.addFieldNameLabel}
              />

              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginTop: 14, marginBottom: 6 }}>{t.addFieldAreaLabel}</Text>
              <TextInput
                style={modalStyles.textInput}
                value={addFieldAreaHa}
                onChangeText={setAddFieldAreaHa}
                placeholder="1.5"
                keyboardType="decimal-pad"
              />

              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginTop: 14, marginBottom: 6 }}>{t.addFieldSoilLabel}</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {SOIL_TYPES.map((s) => (
                    <TouchableOpacity
                      key={s}
                      onPress={() => setAddFieldSoilType(addFieldSoilType === s ? null : s)}
                      style={[modalStyles.chip, addFieldSoilType === s && modalStyles.chipActive]}
                    >
                      <Text style={[modalStyles.chipText, addFieldSoilType === s && modalStyles.chipTextActive]}>{s}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginTop: 14, marginBottom: 6 }}>{t.addFieldCropLabel}</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {CROP_TYPES.map((c) => (
                    <TouchableOpacity
                      key={c}
                      onPress={() => setAddFieldCrop(addFieldCrop === c ? null : c)}
                      style={[modalStyles.chip, addFieldCrop === c && modalStyles.chipActive]}
                    >
                      <Text style={[modalStyles.chipText, addFieldCrop === c && modalStyles.chipTextActive]}>{c}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginTop: 14, marginBottom: 6 }}>{t.addFieldLocationLabel}</Text>
              <TouchableOpacity
                style={[modalStyles.pickerBtn, { backgroundColor: addFieldCoords ? THEME.brand100 : THEME.brand800, alignSelf: 'flex-start' }]}
                onPress={captureFieldLocation}
                disabled={addFieldLocating}
              >
                {addFieldLocating ? (
                  <ActivityIndicator size="small" color={THEME.brand800} />
                ) : (
                  <Text style={[modalStyles.pickerBtnText, { color: addFieldCoords ? THEME.brand900 : '#FFF' }]}>
                    {addFieldCoords ? t.addFieldLocationCaptured : t.addFieldUseLocationBtn}
                  </Text>
                )}
              </TouchableOpacity>

              {addFieldError ? (
                <Text style={{ color: THEME.statusUrgent, marginTop: 12 }}>{addFieldError}</Text>
              ) : null}
            </ScrollView>

            <View style={modalStyles.actionBtnRow}>
              <TouchableOpacity style={modalStyles.pickerBtn} onPress={() => setAddFieldVisible(false)}>
                <Text style={modalStyles.pickerBtnText}>{t.addFieldCancelBtn}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[modalStyles.pickerBtn, { backgroundColor: THEME.brand800 }]}
                onPress={submitAddField}
                disabled={addFieldSubmitting}
              >
                {addFieldSubmitting ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Text style={[modalStyles.pickerBtnText, { color: '#FFF' }]}>{t.addFieldSubmitBtn}</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* --- PROFILE MODAL --- */}
      <Modal
        visible={profileVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setProfileVisible(false)}
      >
        <View style={modalStyles.modalOverlay}>
          <View style={[modalStyles.modalCard, { maxHeight: windowHeight * 0.85 }]}>
            <View style={modalStyles.modalHeader}>
              <Text style={modalStyles.modalTitle}>{t.profileTitle}</Text>
              <TouchableOpacity onPress={() => setProfileVisible(false)}>
                <Icon name="close" size={20} color={THEME.ink700} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={{ alignItems: 'center', marginBottom: 18 }}>
                <TouchableOpacity onPress={pickProfilePhoto} style={{ marginBottom: 10 }}>
                  <View style={{ width: 96, height: 96, borderRadius: 48, backgroundColor: THEME.brand600, justifyContent: 'center', alignItems: 'center', overflow: 'hidden', borderWidth: 2, borderColor: THEME.accentGold }}>
                    {profilePhotoUri ? (
                      <Image source={{ uri: profilePhotoUri }} style={{ width: '100%', height: '100%' }} />
                    ) : (
                      <Text style={{ color: '#FFF', fontSize: 36, fontWeight: 'bold' }}>
                        {(profileName || '?').charAt(0).toUpperCase()}
                      </Text>
                    )}
                  </View>
                </TouchableOpacity>
                <TouchableOpacity onPress={pickProfilePhoto}>
                  <Text style={{ color: THEME.brand800, fontWeight: '600', fontSize: 13 }}>{t.changePhotoBtn}</Text>
                </TouchableOpacity>
              </View>

              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginBottom: 6 }}>{t.profileNameLabel}</Text>
              <TextInput
                style={modalStyles.textInput}
                value={profileName}
                onChangeText={setProfileName}
                placeholder={t.profileNameLabel}
              />

              <Text style={{ fontSize: 14, fontWeight: '600', color: THEME.ink900, marginTop: 14, marginBottom: 6 }}>{t.profilePhoneLabel}</Text>
              <View style={[modalStyles.textInput, { backgroundColor: THEME.brand100, justifyContent: 'center' }]}>
                <Text style={{ fontSize: 15, color: THEME.ink600 }}>{farmer?.phone || '—'}</Text>
              </View>

              {profileError ? (
                <Text style={{ color: THEME.statusUrgent, marginTop: 12 }}>{profileError}</Text>
              ) : null}
            </ScrollView>

            <View style={modalStyles.actionBtnRow}>
              <TouchableOpacity style={modalStyles.pickerBtn} onPress={() => setProfileVisible(false)}>
                <Text style={modalStyles.pickerBtnText}>{t.addFieldCancelBtn}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[modalStyles.pickerBtn, { backgroundColor: THEME.brand800 }]}
                onPress={submitProfile}
                disabled={profileSaving}
              >
                {profileSaving ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Text style={[modalStyles.pickerBtnText, { color: '#FFF' }]}>{t.saveProfileBtn}</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {langConfirmModal}
    </SafeAreaView>
  );
}

// --- Responsive Modal & Screen Styles ---
const modalStyles = StyleSheet.create({
  textInput: {
    borderWidth: 1.5,
    borderColor: THEME.glassBorder,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: THEME.ink900,
    backgroundColor: '#FFF',
  },
  chip: {
    borderWidth: 1.5,
    borderColor: THEME.glassBorder,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#FFF',
  },
  chipActive: {
    backgroundColor: THEME.brand800,
    borderColor: THEME.brand800,
  },
  chipText: {
    fontSize: 13,
    color: THEME.ink700,
    textTransform: 'capitalize',
  },
  chipTextActive: {
    color: '#FFF',
    fontWeight: '600',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    backgroundColor: THEME.grainCream,
    width: '100%',
    maxWidth: 500,
    borderRadius: 20,
    padding: 18,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 5,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: 'bold',
    color: THEME.brand900,
    flex: 1,
  },
  closeBtn: {
    fontSize: 20,
    fontWeight: 'bold',
    color: THEME.soilBrown,
    padding: 4,
  },
  previewImage: {
    width: '100%',
    height: 180,
    borderRadius: 14,
    marginBottom: 14,
  },
  placeholderBox: {
    width: '100%',
    height: 130,
    backgroundColor: THEME.brand100,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 1.5,
    borderColor: THEME.brand500,
    borderStyle: 'dashed',
  },
  placeholderText: {
    color: THEME.brand900,
    fontSize: 14,
    fontWeight: '600',
    marginTop: 6,
  },
  resultBox: {
    backgroundColor: THEME.grainCardBg,
    padding: 14,
    borderRadius: 14,
    borderLeftWidth: 4,
    borderLeftColor: THEME.statusCaution,
    marginBottom: 16,
  },
  diseaseResultTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: THEME.ink900,
    flex: 1,
  },
  confidenceBadge: {
    fontFamily: 'IBMPlexMono_500Medium',
    fontSize: 11,
    color: THEME.statusGood,
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  recommendationBody: {
    fontSize: 14,
    color: THEME.ink900,
    lineHeight: 21,
    marginTop: 6,
  },
  playResultVoiceBtn: {
    backgroundColor: THEME.brand800,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 12,
    marginTop: 10,
    alignItems: 'center',
  },
  playResultVoiceText: {
    color: THEME.grainCream,
    fontSize: 13,
    fontWeight: 'bold',
  },
  actionBtnRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 10,
    marginTop: 10,
  },
  pickerBtn: {
    flex: 1,
    backgroundColor: THEME.brand100,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: THEME.brand600,
  },
  pickerBtnText: {
    color: THEME.brand900,
    fontSize: 12,
    fontWeight: 'bold',
  },
});

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.grainCream,
  },
  // --- Module 31: new/redesigned component styles ---
  emptyFieldCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: THEME.accentGoldSoft,
    borderRadius: 16,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: THEME.accentGold,
  },
  emptyFieldTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: THEME.brand900,
  },
  emptyFieldSub: {
    fontSize: 12,
    color: THEME.ink600,
    marginTop: 2,
  },
  inlineFactPanel: {
    backgroundColor: THEME.grainCardBg,
    borderRadius: 16,
    padding: 16,
    marginTop: 12,
    borderWidth: 1,
    borderColor: THEME.glassBorder,
  },
  inlineFactPanelTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: THEME.brand900,
    marginBottom: 10,
  },
  inlineFactRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  inlineFactRowLabel: {
    fontSize: 13,
    color: THEME.ink600,
    fontWeight: '600',
  },
  inlineFactRowValue: {
    fontSize: 14,
    color: THEME.ink900,
    lineHeight: 21,
  },
  recordsFilterRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  recordsFilterChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: THEME.grainCardBg,
    borderWidth: 1,
    borderColor: THEME.glassBorder,
  },
  recordsFilterChipActive: {
    backgroundColor: THEME.brand900,
    borderColor: THEME.brand900,
  },
  recordsFilterChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: THEME.ink700,
  },
  recordsFilterChipTextActive: {
    color: THEME.grainCream,
  },
  recordCard: {
    backgroundColor: THEME.grainCardBg,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: THEME.glassBorder,
  },
  recordCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  recordCardTitle: {
    flex: 1,
    fontSize: 14,
    fontWeight: '700',
    color: THEME.ink900,
  },
  recordCardTag: {
    fontSize: 11,
    fontWeight: '700',
    color: THEME.brand700,
    backgroundColor: THEME.brand100,
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  recordCardTimestamp: {
    fontFamily: 'IBMPlexMono_400Regular',
    fontSize: 11,
    color: THEME.ink500,
    marginTop: 6,
  },
  recordCardBody: {
    fontSize: 13,
    color: THEME.ink700,
    marginTop: 6,
    lineHeight: 19,
  },
  recordCardPlayBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  recordCardPlayText: {
    fontSize: 12,
    fontWeight: '700',
    color: THEME.brand700,
  },
  settingsGroupLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: THEME.ink500,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
    marginTop: 8,
  },
  settingsGroupCard: {
    backgroundColor: THEME.grainCardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: THEME.glassBorder,
    marginBottom: 18,
    overflow: 'hidden',
  },
  settingsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: THEME.glassBorder,
  },
  settingsRowButton: {
    justifyContent: 'space-between',
  },
  settingsRowLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: THEME.ink900,
  },
  settingsRowValue: {
    fontSize: 12,
    color: THEME.ink500,
    marginTop: 2,
  },
  onboardScreen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  onboardIconCircle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: THEME.brand100,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 22,
  },
  onboardTitle: {
    fontFamily: 'Fraunces_700Bold',
    fontSize: 22,
    color: THEME.brand900,
    textAlign: 'center',
    marginBottom: 12,
  },
  // Module 31: Fraunces for headline/title moments (screen titles, the
  // hero advisory headline), IBM Plex Mono for numbers/timestamps/units
  // (irrigation mm, dates, confidence %, play-time) -- applied on top of
  // the Text/TextInput shadow's Poppins default, which still governs
  // everything else.
  fontHeadline: {
    fontFamily: 'Fraunces_700Bold',
  },
  fontMono: {
    fontFamily: 'IBMPlexMono_500Medium',
  },
  onboardBody: {
    fontSize: 15,
    color: THEME.ink700,
    textAlign: 'center',
    lineHeight: 22,
  },
  onboardDotsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 24,
  },
  onboardDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: THEME.ink300,
  },
  onboardDotActive: {
    backgroundColor: THEME.brand700,
    width: 20,
  },
  onboardSkipText: {
    fontSize: 13,
    color: THEME.ink500,
    fontWeight: '600',
  },
  splashContainer: {
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 20,
  },
  splashCenterContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  splashTagline: {
    color: THEME.brand900,
    marginTop: 20,
    textAlign: 'center',
    fontWeight: '600',
    lineHeight: 24,
  },
  splashFooter: {
    width: '100%',
    paddingHorizontal: 20,
  },
  splashEnterBtn: {
    backgroundColor: THEME.brand800,
    borderRadius: 16,
    alignItems: 'center',
    width: '100%',
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 4,
  },
  splashEnterBtnText: {
    color: THEME.grainCream,
    fontWeight: 'bold',
  },
  onboardingHeader: {
    paddingVertical: 14,
    backgroundColor: THEME.brand900,
    alignItems: 'center',
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  onboardingSubtitle: {
    color: THEME.brand100,
    marginTop: 4,
    fontWeight: '600',
  },
  confirmCard: {
    backgroundColor: THEME.grainCardBg,
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: THEME.brand500,
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  locationTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: THEME.brand900,
    textAlign: 'center',
    marginBottom: 8,
  },
  langPillBadge: {
    backgroundColor: THEME.brand100,
    borderColor: THEME.brand600,
    borderWidth: 1,
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 16,
    marginBottom: 14,
  },
  langPillBadgeText: {
    color: THEME.brand900,
    fontSize: 14,
    fontWeight: 'bold',
  },
  confirmPromptText: {
    fontSize: 15,
    color: THEME.ink900,
    textAlign: 'center',
    lineHeight: 22,
    marginVertical: 10,
  },
  changeLangOutlineBtn: {
    marginTop: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: THEME.soilBrown,
    width: '100%',
    alignItems: 'center',
  },
  changeLangOutlineBtnText: {
    color: THEME.soilBrown,
    fontSize: 14,
    fontWeight: 'bold',
  },
  authTopHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: THEME.brand900,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backButton: {
    backgroundColor: THEME.brand800,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
  },
  backButtonText: {
    color: THEME.grainCream,
    fontSize: 13,
    fontWeight: 'bold',
  },
  langCyclePill: {
    backgroundColor: THEME.brand600,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
  },
  langCycleText: {
    color: THEME.grainCream,
    fontSize: 12,
    fontWeight: 'bold',
  },
  cardContainer: {
    paddingVertical: 16,
    gap: 12,
  },
  langCard: {
    backgroundColor: THEME.grainCardBg,
    paddingVertical: 18,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: THEME.brand600,
    alignItems: 'center',
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
  },
  selectedLangCard: {
    backgroundColor: THEME.brand100,
    borderColor: THEME.brand900,
  },
  langScriptTitle: {
    fontSize: 26,
    fontWeight: 'bold',
    color: THEME.ink900,
    marginBottom: 8,
  },
  previewBtn: {
    backgroundColor: THEME.brand800,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
  },
  previewBtnText: {
    color: THEME.grainCream,
    fontSize: 13,
    fontWeight: '600',
  },
  footerBar: {
    paddingHorizontal: 16,
  },
  primaryButton: {
    backgroundColor: THEME.brand800,
    paddingVertical: 16,
    borderRadius: 14,
    alignItems: 'center',
    width: '100%',
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 5,
    elevation: 3,
  },
  buttonDisabled: {
    backgroundColor: '#A3B18A',
  },
  primaryButtonText: {
    color: THEME.grainCream,
    fontSize: 17,
    fontWeight: 'bold',
  },
  scrollContent: {
    paddingBottom: 32,
  },
  screenHeading: {
    fontWeight: 'bold',
    color: THEME.brand900,
    marginVertical: 12,
    textAlign: 'center',
  },
  inputGroup: {
    marginBottom: 14,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: THEME.ink900,
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#FFF',
    borderWidth: 1.5,
    borderColor: THEME.brand600,
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    color: THEME.ink900,
  },
  errorBanner: {
    backgroundColor: '#FDE8E8',
    borderColor: THEME.statusUrgent,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
  },
  errorText: {
    color: THEME.statusUrgent,
    fontSize: 13,
    fontWeight: '600',
  },
  cooldownText: {
    color: THEME.soilBrown,
    fontSize: 12,
    marginTop: 4,
    fontWeight: 'bold',
  },
  switchAuthBtn: {
    marginTop: 16,
    alignItems: 'center',
  },
  switchAuthText: {
    color: THEME.soilBrown,
    fontSize: 14,
    textDecorationLine: 'underline',
  },
  otpSentHint: {
    color: THEME.ink600,
    fontSize: 13,
    marginBottom: 14,
    fontStyle: 'italic',
  },

  // Dashboard Styles
  dashHeaderNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: THEME.brand900,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  dashBrandGroup: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  dashBrandName: {
    color: THEME.grainCream,
    fontWeight: '900',
    letterSpacing: 1.2,
    marginLeft: 8,
  },
  dashHeaderActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dashLangToggle: {
    backgroundColor: THEME.brand800,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: THEME.brand600,
  },
  dashLangText: {
    color: THEME.grainCream,
    fontSize: 11,
    fontWeight: 'bold',
  },
  dashLogoutCircle: {
    backgroundColor: 'rgba(217, 4, 41, 0.2)',
    padding: 7,
    borderRadius: 18,
  },
  dashLogoutIcon: {
    fontSize: 13,
  },
  dashAvatarCircle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: THEME.brand600,
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
    borderWidth: 1.5,
    borderColor: THEME.accentGold,
  },
  dashAvatarImage: {
    width: '100%',
    height: '100%',
  },
  dashAvatarInitial: {
    color: '#FFF',
    fontWeight: 'bold',
    fontSize: 13,
  },
  fieldSelectorContainer: {
    backgroundColor: THEME.brand900,
    paddingHorizontal: 14,
    paddingBottom: 10,
    borderBottomLeftRadius: 18,
    borderBottomRightRadius: 18,
  },
  fieldSelectorPill: {
    backgroundColor: THEME.grainCream,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 12,
    justifyContent: 'space-between',
  },
  fieldSelectorIcon: {
    fontSize: 15,
  },
  fieldSelectorText: {
    color: THEME.brand900,
    fontSize: 14,
    fontWeight: 'bold',
    flex: 1,
    marginLeft: 8,
  },
  fieldSelectorArrow: {
    color: THEME.brand900,
    fontSize: 11,
    fontWeight: 'bold',
  },
  dashScrollContent: {
    paddingVertical: 14,
    paddingBottom: 110,
  },
  scanLeafBanner: {
    backgroundColor: THEME.brand800,
    borderRadius: 16,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1.5,
    borderColor: THEME.brand500,
    elevation: 3,
  },
  scanLeafIcon: {
    fontSize: 24,
    marginRight: 10,
  },
  scanLeafTitle: {
    color: THEME.grainCream,
    fontWeight: 'bold',
  },
  scanLeafSub: {
    color: THEME.brand100,
    fontSize: 11,
    marginTop: 2,
  },
  scanLeafArrow: {
    color: THEME.grainCream,
    fontSize: 16,
    fontWeight: 'bold',
    marginLeft: 8,
  },
  heroBannerCard: {
    backgroundColor: THEME.brand900,
    borderRadius: 22,
    padding: 16,
    paddingTop: 20,
    marginBottom: 18,
    borderTopWidth: 3,
    borderTopColor: THEME.accentGold,
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
    overflow: 'hidden',
  },
  heroBannerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  heroBadgeUrgent: {
    backgroundColor: THEME.statusUrgent,
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  heroBadgeUrgentText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  heroDateText: {
    color: THEME.brand100,
    fontSize: 11,
    fontWeight: '600',
  },
  heroAudioPlayBar: {
    backgroundColor: THEME.brand800,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: THEME.brand500,
    marginBottom: 12,
  },
  heroAudioPlayBarActive: {
    backgroundColor: THEME.brand600,
  },
  heroPlayCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: THEME.grainCream,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  heroPlaySymbol: {
    fontSize: 18,
    color: THEME.brand900,
    marginLeft: 2,
  },
  heroAudioMeta: {
    flex: 1,
  },
  heroAudioTitle: {
    color: THEME.grainCream,
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  heroAudioWaveText: {
    color: THEME.brand100,
    fontSize: 11,
    fontWeight: 'bold',
    letterSpacing: 0.8,
  },
  heroTranscriptBox: {
    backgroundColor: THEME.grainCardBg,
    padding: 12,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: THEME.brand500,
  },
  heroTranscriptBody: {
    fontSize: 15,
    color: THEME.ink900,
    lineHeight: 22,
    fontWeight: '500',
  },
  categoryGridSection: {
    marginBottom: 18,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: 'bold',
    color: THEME.brand900,
    marginBottom: 10,
  },
  gridRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  gridCard: {
    backgroundColor: THEME.grainCardBg,
    padding: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(45, 106, 79, 0.12)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
    position: 'relative',
  },
  gridDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    position: 'absolute',
    top: 8,
    right: 8,
  },
  gridIconBg: {
    width: 38,
    height: 38,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  gridIcon: {
    fontSize: 20,
  },
  gridTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: THEME.ink900,
  },
  gridSub: {
    fontSize: 11,
    color: THEME.ink600,
    marginTop: 2,
  },
  feedSection: {
    marginTop: 2,
  },
  feedCardContainer: {
    backgroundColor: THEME.grainCardBg,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(45, 106, 79, 0.12)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  feedCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  feedUrgencyPill: {
    paddingVertical: 3,
    paddingHorizontal: 7,
    borderRadius: 6,
  },
  feedUrgencyPillText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: 'bold',
  },
  feedCardTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: THEME.ink900,
    flex: 1,
  },
  feedVoiceBar: {
    backgroundColor: THEME.brand100,
    borderRadius: 10,
    padding: 8,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    borderWidth: 1,
    borderColor: THEME.brand500,
  },
  feedVoiceIconCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: THEME.brand800,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  feedVoiceIconSymbol: {
    color: '#FFF',
    fontSize: 13,
    marginLeft: 1,
  },
  feedVoiceWave: {
    color: THEME.brand900,
    fontSize: 11,
    fontWeight: 'bold',
  },
  feedCardBody: {
    fontSize: 14,
    color: THEME.ink900,
    lineHeight: 21,
  },

  // 4-Tab Bottom Bar Styles
  bottomTabBar: {
    flexDirection: 'row',
    backgroundColor: THEME.grainCardBg,
    marginHorizontal: 12,
    marginBottom: 8,
    borderRadius: 24,
    paddingTop: 10,
    paddingHorizontal: 6,
    borderWidth: 1,
    borderColor: THEME.glassBorder,
    shadowColor: THEME.shadowColor,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.12,
    shadowRadius: 14,
    elevation: 10,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    borderRadius: 16,
  },
  activeTabItem: {
    backgroundColor: THEME.brand100,
  },
  tabIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  activeTabIcon: {
    transform: [{ scale: 1.15 }],
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: THEME.ink500,
  },
  activeTabLabel: {
    color: THEME.brand900,
    fontWeight: 'bold',
  },

  // Tab View Containers
  tabContentContainer: {
    padding: 16,
    paddingBottom: 110,
  },
  tabHeaderCard: {
    backgroundColor: THEME.brand900,
    borderRadius: 24,
    padding: 18,
    marginBottom: 16,
  },
  tabHeaderTitle: {
    fontFamily: 'Fraunces_700Bold',
    fontSize: 19,
    color: THEME.grainCream,
  },
  tabHeaderSub: {
    fontSize: 12,
    color: THEME.brand100,
    marginTop: 4,
  },
  bigScanLauncherBtn: {
    backgroundColor: THEME.brand800,
    borderRadius: 28,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: THEME.brand500,
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
    elevation: 5,
  },
  bigScanLauncherTitle: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  bigScanLauncherSub: {
    color: THEME.brand100,
    fontSize: 12,
    marginTop: 4,
  },
  historyCard: {
    backgroundColor: THEME.grainCardBg,
    borderRadius: 20,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: THEME.glassBorder,
    shadowColor: THEME.shadowColor,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  historyDate: {
    fontSize: 12,
    fontWeight: 'bold',
    color: THEME.ink500,
  },
  urgencyBadge: {
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  urgencyBadgeText: {
    color: '#FFF',
    fontSize: 9,
    fontWeight: 'bold',
  },
  historyDiseaseTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: THEME.ink900,
  },
  historyFieldSub: {
    fontSize: 12,
    color: THEME.ink500,
    marginTop: 2,
    marginBottom: 8,
  },
  historyRecBody: {
    fontSize: 13,
    color: THEME.ink700,
    lineHeight: 19,
    marginBottom: 10,
  },
  historyListenBtn: {
    backgroundColor: THEME.brand100,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 10,
    alignSelf: 'flex-start',
  },
  historyListenText: {
    color: THEME.brand900,
    fontSize: 12,
    fontWeight: 'bold',
  },
});
