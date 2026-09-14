import React, { useState, useEffect, useRef } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  ScrollView, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert, 
  TextInput, 
  StatusBar, 
  Image, 
  Modal, 
  useWindowDimensions 
} from 'react-native';
import { SafeAreaProvider, SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Speech from 'expo-speech';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { createAudioPlayer, AudioPlayer } from 'expo-audio';
import { CameraView, useCameraPermissions, FlashMode } from 'expo-camera';
import { BlurView } from 'expo-blur';

import { API_BASE_URL } from './src/config';

// Pre-require logo assets for instant Metro bundling
const FULL_LOGO_WITH_NAME = require('./assets/Agro_Mirai_Logo.png');
const CROPPED_LOGO_WITHOUT_NAME = require('./assets/Logo.png');

// --- Premium Earth & Soft Glass Palette ---
const THEME = {
  brand900: '#1B4332',
  brand800: '#2D6A4F',
  brand600: '#40916C',
  brand500: '#52B788',
  brand100: '#E8F5E9',
  grainCream: '#FAF7F2',
  grainCardBg: '#FFFFFF',
  glassCardBg: 'rgba(255, 255, 255, 0.92)',
  glassBorder: 'rgba(45, 106, 79, 0.12)',
  soilBrown: '#6B4E31',
  ink900: '#111827',
  ink700: '#374151',
  ink600: '#4A554D',
  ink500: '#6B7280',
  ink300: '#D1D5DB',
  statusGood: '#10B981',
  statusCaution: '#F59E0B',
  statusUrgent: '#EF4444',
  shadowColor: '#1B4332',
};

// --- Complete 4-Language Native Script i18n ---
type LangKey = 'kn' | 'te' | 'hi' | 'en';

const TRANSLATIONS: Record<LangKey, Record<string, string>> = {
  kn: {
    splashTagline: 'ಸ್ಮಾರ್ಟ್ AI ಕೃಷಿ ಸಲಹೆಗಾರ',
    getStarted: 'ಪ್ರಾರಂಭಿಸಿ ➔',
    selectLang: 'ಭಾಷೆಯನ್ನು ಆಯ್ಕೆ ಮಾಡಿ',
    continue: 'ಮುಂದುವರಿಸಿ ➔',
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
    urgentPriority: '🚨 ಪ್ರಮುಖ ಸಲಹೆ',
    todayAction: 'ಇಂದಿನ ಕೃಷಿ ಕಾರ್ಯ',
    listen: '🔊 ಕೇಳಿ',
    scanLeaf: '📸 ಎಲೆ ಫೋಟೋ ತೆಗೆದು ರೋಗ ತಪಾಸಣೆ ಮಾಡಿ',
    scanTitle: 'ಎಲೆ ರೋಗ ತಪಾಸಣೆ (AI Scan)',
    pickGallery: '🖼️ ಗ್ಯಾಲರಿಯಿಂದ ಆಯ್ಕೆ ಮಾಡಿ',
    takePhoto: '📷 ಕ್ಯಾಮೆರಾದಿಂದ ಫೋಟೋ ತೆಗೆಯಿರಿ',
    analyzing: 'AI ಎಲೆ ರೋಗ ತಪಾಸಣೆ ನಡೆಸುತ್ತಿದೆ...',
    confirmLangTitle: 'ಸ್ಥಳೀಯ ಭಾಷೆ ದೃಢೀಕರಣ',
    confirmLangBtn: '✅ ದೃಢೀಕರಿಸಿ ಮುಂದುವರಿಸಿ',
    changeLangBtn: '🔄 ಭಾಷೆಯನ್ನು ಬದಲಾಯಿಸಿ',
    tabHome: 'ಮುಖ್ಯ ಪುಟ',
    tabScan: 'ಎಲೆ ಸ್ಕ್ಯಾನ್',
    tabHistory: 'ಇತಿಹಾಸ',
    tabAdvisories: 'ಸಲಹೆಗಳು',
    embeddedCamTitle: 'ಕ್ಯಾಮೆರಾ ವೀಕ್ಷಣೆ',
    closeCam: '✕ ಮುಚ್ಚಿ',
    scanLeafSub: 'ಎಲೆಯ ಫೋಟೋ ತೆಗೆದು ರೋಗ ಪರೀಕ್ಷಿಸಿ',
    scanTabSub: 'ಎಲೆಯ ಮೇಲಿನ ರೋಗ ಗುರುತಿಸುವಿಕೆ',
    embeddedCamSub: 'ಎಲೆಯನ್ನು ಚೌಕದ ಒಳಗೆ ಇರಿಸಿ',
    gridSubIrrigation: 'ಇಂದಿನ ಶಿಫಾರಸು',
    gridSubDisease: 'ಎಲೆ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ',
    gridSubCrop: 'ಪ್ರಸ್ತುತ ಸ್ಥಿತಿ',
    historyTabSub: 'ಹಿಂದಿನ ಸ್ಕ್ಯಾನ್ ಮತ್ತು ಸಲಹೆಗಳು',
    modalIrrigationTitle: '💧 ನೀರಾವರಿ ವಿವರಗಳು',
    modalCropTitle: '🌱 ಬೆಳೆ ಆರೋಗ್ಯ',
    modalHistoryTitle: '📜 ಸಲಹೆ ಇತಿಹಾಸ',
    recommendedDepth: 'ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಿನ ಪ್ರಮಾಣ',
    soilMoisture: 'ಮಣ್ಣಿನ ತೇವಾಂಶ',
    weatherForecast: 'ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ',
    cropTypeLabel: 'ಬೆಳೆ ಪ್ರಕಾರ',
    fieldAreaLabel: 'ಹೊಲದ ವಿಸ್ತೀರ್ಣ',
    growthPhaseLabel: 'ಬೆಳವಣಿಗೆ ಹಂತ',
    scanErrorTitle: '⚠️ ಸ್ಕ್ಯಾನ್ ವಿಫಲವಾಗಿದೆ',
    scanErrorBody: 'ಫೋಟೋ ಸರ್ವರ್‌ಗೆ ಕಳುಹಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ನಿಮ್ಮ ಇಂಟರ್ನೆಟ್ ಸಂಪರ್ಕ ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    retryBtn: '🔄 ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
  },
  te: {
    splashTagline: 'స్మార్ట్ AI వ్యవసాయ సలహాదారు',
    getStarted: 'ప్రారంభించండి ➔',
    selectLang: 'భాషను ఎంచుకోండి',
    continue: 'కొనసాగించండి ➔',
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
    urgentPriority: '🚨 అత్యవసర సలహా',
    todayAction: 'నేటి ముఖ్యమైన పని',
    listen: '🔊 వినండి',
    scanLeaf: '📸 ఆకు ఫోటో తీసి వ్యాధి తనిఖీ చేయండి',
    scanTitle: 'ఆకు తెగులు విశ్లేషణ (AI Scan)',
    pickGallery: '🖼️ గ్యాలరీ నుండి ఎంచుకోండి',
    takePhoto: '📷 కెమెరాతో ఫోటో తీయండి',
    analyzing: 'కృత్రిమ మేధ (AI) ఆకు తెగులును విశ్లేషిస్తోంది...',
    confirmLangTitle: 'ప్రాంతీయ భాష నిర్ధారణ',
    confirmLangBtn: '✅ నిర్ధారించి కొనసాగించండి',
    changeLangBtn: '🔄 వేరే భాషను ఎంచుకోండి',
    tabHome: 'హోమ్',
    tabScan: 'లీఫ్ స్కాన్',
    tabHistory: 'చరిత్ర',
    tabAdvisories: 'సలహాలు',
    embeddedCamTitle: 'కెమెరా వీక్షణ',
    closeCam: '✕ మూసివేయి',
    scanLeafSub: 'ఆకు ఫోటో తీసి వ్యాధిని తనిఖీ చేయండి',
    scanTabSub: 'ఆకుపై వ్యాధి గుర్తింపు',
    embeddedCamSub: 'ఆకును ఫ్రేమ్ లోపల ఉంచండి',
    gridSubIrrigation: 'నేటి సూచన',
    gridSubDisease: 'ఆకును స్కాన్ చేయండి',
    gridSubCrop: 'ప్రస్తుత స్థితి',
    historyTabSub: 'గత స్కాన్‌లు మరియు సలహాలు',
    modalIrrigationTitle: '💧 నీటి పారుదల వివరాలు',
    modalCropTitle: '🌱 పంట ఆరోగ్యం',
    modalHistoryTitle: '📜 సలహా చరిత్ర',
    recommendedDepth: 'సూచించిన నీటి పరిమాణం',
    soilMoisture: 'నేల తేమ',
    weatherForecast: 'వాతావరణ సూచన',
    cropTypeLabel: 'పంట రకం',
    fieldAreaLabel: 'పొలం విస్తీర్ణం',
    growthPhaseLabel: 'పెరుగుదల దశ',
    scanErrorTitle: '⚠️ స్కాన్ విఫలమైంది',
    scanErrorBody: 'ఫోటోను సర్వర్‌కు పంపలేకపోయాము. మీ ఇంటర్నెట్ కనెక్షన్‌ను చూసి, మళ్ళీ ప్రయత్నించండి.',
    retryBtn: '🔄 మళ్ళీ ప్రయత్నించండి',
  },
  hi: {
    splashTagline: 'स्मार्ट AI कृषि सलाहकार',
    getStarted: 'शुरू करें ➔',
    selectLang: 'भाषा चुनें',
    continue: 'आगे बढ़ें ➔',
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
    urgentPriority: '🚨 अत्यंत महत्वपूर्ण सलाह',
    todayAction: 'आज का कार्य',
    listen: '🔊 सुनें',
    scanLeaf: '📸 पत्ती का फोटो लेकर रोग जांच करें',
    scanTitle: 'पत्ती रोग विश्लेषण (AI Scan)',
    pickGallery: '🖼️ गैलरी से चुनें',
    takePhoto: '📷 कैमरा से फोटो लें',
    analyzing: 'AI पत्ती के रोग की जांच कर रहा है...',
    confirmLangTitle: 'स्थानीय भाषा पुष्टि',
    confirmLangBtn: '✅ पुष्टि करें और आगे बढ़ें',
    changeLangBtn: '🔄 दूसरी भाषा चुनें',
    tabHome: 'मुख्य पृष्ठ',
    tabScan: 'पत्ती स्कैन',
    tabHistory: 'इतिहास',
    tabAdvisories: 'सलाहें',
    embeddedCamTitle: 'कैमरा दृश्य',
    closeCam: '✕ बंद करें',
    scanLeafSub: 'पत्ती की फोटो लेकर रोग जांचें',
    scanTabSub: 'पत्ती पर रोग की पहचान',
    embeddedCamSub: 'पत्ती को फ्रेम के भीतर रखें',
    gridSubIrrigation: 'आज की सलाह',
    gridSubDisease: 'पत्ती स्कैन करें',
    gridSubCrop: 'वर्तमान स्थिति',
    historyTabSub: 'पिछले स्कैन और सलाह',
    modalIrrigationTitle: '💧 सिंचाई विवरण',
    modalCropTitle: '🌱 फसल स्वास्थ्य',
    modalHistoryTitle: '📜 सलाह इतिहास',
    recommendedDepth: 'सुझाई गई पानी की मात्रा',
    soilMoisture: 'मिट्टी की नमी',
    weatherForecast: 'मौसम पूर्वानुमान',
    cropTypeLabel: 'फसल प्रकार',
    fieldAreaLabel: 'खेत का क्षेत्र',
    growthPhaseLabel: 'बढ़वार चरण',
    scanErrorTitle: '⚠️ स्कैन विफल',
    scanErrorBody: 'फोटो सर्वर तक नहीं पहुंच पाई। कृपया अपना इंटरनेट कनेक्शन जांचें और फिर से प्रयास करें।',
    retryBtn: '🔄 फिर से प्रयास करें',
  },
  en: {
    splashTagline: 'Smart AI Agricultural Companion',
    getStarted: 'Get Started ➔',
    selectLang: 'Select Language',
    continue: 'Continue ➔',
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
    urgentPriority: '🚨 HIGH PRIORITY',
    todayAction: "Today's Action",
    listen: '🔊 Listen',
    scanLeaf: '📸 Scan Leaf Image (AI Disease Scanner)',
    scanTitle: 'AI Leaf Disease Scanner',
    pickGallery: '🖼️ Choose from Gallery',
    takePhoto: '📷 Take Camera Photo',
    analyzing: 'Analyzing leaf image with AI model...',
    confirmLangTitle: 'Confirm Local Language',
    confirmLangBtn: '✅ Confirm & Proceed',
    changeLangBtn: '🔄 Choose Different Language',
    tabHome: 'Home',
    tabScan: 'AI Scan',
    tabHistory: 'History',
    tabAdvisories: 'Advisories',
    embeddedCamTitle: 'Camera View',
    closeCam: '✕ Close',
    scanLeafSub: 'Take a photo of the leaf to check for disease',
    scanTabSub: 'Disease detection on a leaf photo',
    embeddedCamSub: 'Position the leaf inside the frame',
    gridSubIrrigation: "Today's recommendation",
    gridSubDisease: 'Scan a leaf',
    gridSubCrop: 'Current status',
    historyTabSub: 'Past scans and advisories',
    modalIrrigationTitle: '💧 Irrigation Details',
    modalCropTitle: '🌱 Crop Health',
    modalHistoryTitle: '📜 Advisory History',
    recommendedDepth: 'Recommended Water Depth',
    soilMoisture: 'Soil Moisture',
    weatherForecast: 'Weather Forecast',
    cropTypeLabel: 'Crop Type',
    fieldAreaLabel: 'Field Area',
    growthPhaseLabel: 'Growth Phase',
    scanErrorTitle: "⚠️ Scan Couldn't Complete",
    scanErrorBody: "We couldn't reach the server to analyze this photo. Check your internet connection and try again.",
    retryBtn: '🔄 Try Again',
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

  const [screen, setScreen] = useState<'SPLASH' | 'LANG_CONFIRM' | 'LANG_PICKER' | 'AUTH' | 'HOME'>('SPLASH');
  const [language, setLanguage] = useState<LangKey>('te');
  // Module 27: farmer identity/session now comes from the backend's
  // Name+Phone+OTP /v2/auth/* endpoints (signed session cookie), not
  // Supabase Auth -- see decisions/0023-name-phone-otp-auth.md.
  const [farmer, setFarmer] = useState<{ id: string; name: string; phone: string | null } | null>(null);

  // Location & Permission State
  const [locationName, setLocationName] = useState<string>('Andhra Pradesh / Telangana');
  const [detectedLang, setDetectedLang] = useState<LangKey>('te');
  const [isDetectingLocation, setIsDetectingLocation] = useState<boolean>(false);

  // Auth state: two-step Name+Phone+OTP flow
  const [authStep, setAuthStep] = useState<'ENTER_PHONE' | 'ENTER_OTP'>('ENTER_PHONE');
  const [nameInput, setNameInput] = useState('');
  const [phoneInput, setPhoneInput] = useState('');
  const [otpInput, setOtpInput] = useState('');
  const [authError, setAuthError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);

  // Navigation & Tab state
  const [activeTab, setActiveTab] = useState<'home' | 'scan' | 'history' | 'advisories'>('home');
  const [embeddedCameraVisible, setEmbeddedCameraVisible] = useState(false);
  const [cameraFlash, setCameraFlash] = useState<FlashMode>('off');
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [scanHistory, setScanHistory] = useState<any[]>([
    {
      id: 'h1',
      date: '2026-09-11 10:30 AM',
      disease: 'Corn (maize): Common rust',
      risk_level: 'severe',
      confidence: 0.9992,
      field: 'North Field (Cotton)',
      image_uri: null,
      recommendation: 'Scout immediately; apply fungicide per local extension guidance.'
    },
    {
      id: 'h2',
      date: '2026-09-10 04:15 PM',
      disease: 'Tomato: Early blight',
      risk_level: 'moderate',
      confidence: 0.9415,
      field: 'North Field (Cotton)',
      image_uri: null,
      recommendation: 'Ensure adequate foliage airflow and monitor soil moisture.'
    }
  ]);

  // Home State
  const [fields, setFields] = useState<any[]>([]);
  const [selectedField, setSelectedField] = useState<any>(null);
  const [advisories, setAdvisories] = useState<any[]>([]);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [playingAdvisoryId, setPlayingAdvisoryId] = useState<string | null>(null);
  const [sound, setSound] = useState<AudioPlayer | null>(null);

  // Leaf Disease Image Scan Modal State
  const [scanModalVisible, setScanModalVisible] = useState(false);
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
          setFarmer({ id: data.id, name: data.name, phone: data.phone ?? null });
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
      setScreen('LANG_CONFIRM');
    } catch (err: any) {
      console.log('Location detection exception:', err.message);
      setLocationName('Andhra Pradesh / Telangana');
      setDetectedLang('te');
      setLanguage('te');
      setScreen('LANG_CONFIRM');
    } finally {
      setIsDetectingLocation(false);
    }
  };

  const fetchBackendData = async () => {
    setIsLoading(true);
    try {
      console.log(`Fetching backend data from ${API_BASE_URL}/v2/fields`);
      const fieldsRes = await fetch(`${API_BASE_URL}/v2/fields`, {
        headers: { 'Accept': 'application/json' }
      });

      let loadedFields: any[] = [];
      if (fieldsRes.ok) {
        const data = await fieldsRes.json();
        loadedFields = Array.isArray(data) ? data : (data.fields || []);
      }

      if (loadedFields.length === 0) {
        loadedFields = [
          { 
            id: 'f1', 
            name: language === 'kn' ? 'ಉತ್ತರ ಹೊಲ' : (language === 'te' ? 'ఉత్తర పొలం' : (language === 'hi' ? 'उत्तर खेत' : 'North Field (Cotton)')), 
            crop_type: 'cotton', 
            crop: 'cotton', 
            area_acres: 3.5, 
            location: locationName 
          }
        ];
      }

      setFields(loadedFields);
      const activeField = loadedFields[0];
      setSelectedField(activeField);

      // Advisories are per-field (GET /v2/fields/{field_id}/advisories) --
      // there is no bare GET /v2/advisories in the API (see
      // specs/core/openapi.yaml). Only real backend-issued fields have an
      // id the backend recognizes; the 'f1' placeholder above is a local
      // fallback with no backend counterpart, so skip the advisories call
      // for it rather than requesting a field id that will 404/404-ish.
      let loadedAdvisories: any[] = [];
      if (activeField && activeField.id !== 'f1') {
        const advRes = await fetch(`${API_BASE_URL}/v2/fields/${activeField.id}/advisories`, {
          headers: { 'Accept': 'application/json' }
        });
        if (advRes.ok) {
          const advData = await advRes.json();
          const rawAdvisories = Array.isArray(advData) ? advData : (advData.items || advData.advisories || []);
          loadedAdvisories = rawAdvisories.map((a: any) => ({ ...a, _remote: true }));
        }
      }

      if (loadedAdvisories.length === 0) {
        loadedAdvisories = [
          {
            id: 'adv-001',
            title: t.todayAction,
            body: language === 'kn' 
              ? 'ನಿಮ್ಮ ಹತ್ತಿ ಬೆಳೆಗೆ ಇಂದು 25mm ನೀರು ನೀಡಿ. ಮಣ್ಣಿನಲ್ಲಿ ತೇವಾಂಶ ಕಡಿಮೆಯಾಗಿದೆ.' 
              : (language === 'te' 
                ? 'మీ పత్తి పొలానికి ఈ రోజు ఇరవై ఐదు మిల్లీమీటర్ల నీరు అందించండి. పొలంలో తేమ తక్కువగా ఉంది.' 
                : (language === 'hi' 
                  ? 'अपनी कपास की फसल में आज 25 मिलीमीटर सिंचाई करें। मिट्टी में नमी कम है।' 
                  : 'Apply 25mm irrigation to Cotton field today. Soil moisture is low.')),
            urgency: 'high',
            type: 'irrigation'
          },
          {
            id: 'adv-002',
            title: t.disease,
            body: language === 'kn' 
              ? 'ಎಲೆ ಚುಕ್ಕೆ ರೋಗದ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿವೆ. ತಾಮ್ರದ ಶಿಲೀಂಧ್ರನಾಶಕ ಸಿಂಪಡಿಸಿ.' 
              : (language === 'te' 
                ? 'ఆకు మచ్చ తెగులు లక్షణాలు కనిపిస్తున్నాయి. దయచేసి ఆర్గానిక్ కాపర్ ఫంగిసైడ్ మందును పిచికారీ చేయండి.' 
                : (language === 'hi' 
                  ? 'पत्ती धब्बा रोग के लक्षण दिखे हैं। जैविक कॉपर फफूंदनाशी का छिड़काव करें।' 
                  : 'Environmental conditions indicate leaf spot risk. Apply organic fungicide.')),
            urgency: 'moderate',
            type: 'disease'
          }
        ];
      }

      setAdvisories(loadedAdvisories);
    } catch (err: any) {
      console.log('Backend fetch warning:', err.message);
      setFields([
        { id: 'f1', name: 'North Field (Cotton)', crop_type: 'cotton', crop: 'cotton' }
      ]);
      setAdvisories([
        {
          id: 'adv-001',
          title: t.todayAction,
          body: language === 'te' 
            ? 'మీ పత్తి పొలానికి ఈ రోజు ఇరవై ఐదు మిల్లీమీటర్ల నీరు అందించండి. పొలంలో తేమ తక్కువగా ఉంది.'
            : 'Apply 25mm irrigation to Cotton field today. Soil moisture is low.',
          urgency: 'high'
        }
      ]);
    } finally {
      setIsLoading(false);
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
      Alert.alert('Permission Required', 'Gallery permission is needed to pick crop leaf images.');
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

  const takeCameraPhoto = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permission Required', 'Camera permission is needed to capture crop leaf photos.');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
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
        Alert.alert('Permission Required', 'Camera permission is needed to scan crop leaf photos.');
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
      Alert.alert('Capture Failed', 'Could not capture the photo. Please try again.');
    }
  };

  const analyzeLeafImage = async (imageUri: string) => {
    setIsAnalyzingImage(true);
    setScanResult(null);
    setScanError(false);
    try {
      const fieldId = selectedField?.id || 'f1';

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
      setFarmer({ id: data.id, name: data.name, phone: data.phone ?? null });
      await fetchBackendData();
      setScreen('HOME');
    } catch (err: any) {
      console.error('verify-otp error:', err);
      setAuthError(err.message || t.invalidOtp);
    } finally {
      setIsLoading(false);
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

  // Screen 0.8: Language Auto-Detection Confirmation Screen
  if (screen === 'LANG_CONFIRM') {
    const langNames: Record<LangKey, string> = {
      kn: 'ಕನ್ನಡ (Kannada)',
      te: 'తెలుగు (Telugu)',
      hi: 'हिंदी (Hindi)',
      en: 'English'
    };

    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor={THEME.brand900} />

        <View style={styles.onboardingHeader}>
          <AgroMiraiLogo size={90} useCropped={true} />
          <Text style={{ color: THEME.brand100, fontWeight: 'bold', fontSize: 16, marginTop: 4 }}>
            {t.confirmLangTitle}
          </Text>
        </View>

        <View style={{ flex: 1, padding: 20, justifyContent: 'center', alignItems: 'center' }}>
          <View style={styles.confirmCard}>
            <Text style={{ fontSize: 44, marginBottom: 10 }}>📍</Text>
            <Text style={styles.locationTitle}>{locationName}</Text>
            
            <View style={styles.langPillBadge}>
              <Text style={styles.langPillBadgeText}>🌐 Detected: {langNames[detectedLang]}</Text>
            </View>

            <Text style={styles.confirmPromptText}>
              We set your regional language to <Text style={{ fontWeight: 'bold', color: THEME.brand900 }}>{langNames[detectedLang]}</Text>. Is this correct?
            </Text>

            <TouchableOpacity 
              style={[styles.primaryButton, { marginTop: 20 }]}
              onPress={() => {
                previewLanguageSample(detectedLang);
                if (farmer) {
                  setScreen('HOME');
                } else {
                  setScreen('AUTH');
                }
              }}
            >
              <Text style={styles.primaryButtonText}>{t.confirmLangBtn}</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={styles.changeLangOutlineBtn}
              onPress={() => setScreen('LANG_PICKER')}
            >
              <Text style={styles.changeLangOutlineBtnText}>{t.changeLangBtn}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

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
            <TouchableOpacity style={styles.previewBtn} onPress={() => previewLanguageSample('kn')}>
              <Text style={styles.previewBtnText}>🔊 Listen / ಕೇಳಿ</Text>
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
            <TouchableOpacity style={styles.previewBtn} onPress={() => previewLanguageSample('te')}>
              <Text style={styles.previewBtnText}>🔊 Listen / వినండి</Text>
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
            <TouchableOpacity style={styles.previewBtn} onPress={() => previewLanguageSample('hi')}>
              <Text style={styles.previewBtnText}>🔊 Listen / सुनें</Text>
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
            <TouchableOpacity style={styles.previewBtn} onPress={() => previewLanguageSample('en')}>
              <Text style={styles.previewBtnText}>🔊 Listen</Text>
            </TouchableOpacity>
          </TouchableOpacity>
        </ScrollView>

        <View style={[styles.footerBar, { paddingBottom: Math.max(16, insets.bottom + 8) }]}>
          <TouchableOpacity 
            style={styles.primaryButton}
            onPress={() => {
              if (farmer) {
                setScreen('HOME');
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

          <TouchableOpacity style={styles.langCyclePill} onPress={cycleLanguage}>
            <Text style={styles.langCycleText}>🌐 {language.toUpperCase()}</Text>
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
      </SafeAreaView>
    );
  }

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
          <TouchableOpacity style={styles.dashLangToggle} onPress={cycleLanguage}>
            <Text style={styles.dashLangText}>🌐 {language.toUpperCase()}</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.dashLogoutCircle} onPress={handleSignOut}>
            <Text style={styles.dashLogoutIcon}>🚪</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Field Selector Pill */}
      <View style={styles.fieldSelectorContainer}>
        <TouchableOpacity style={styles.fieldSelectorPill}>
          <Text style={styles.fieldSelectorIcon}>🌾</Text>
          <Text style={styles.fieldSelectorText} numberOfLines={1}>
            {selectedField ? (selectedField.name || selectedField.crop_type || t.selectField) : t.selectField}
          </Text>
          <Text style={styles.fieldSelectorArrow}>▼</Text>
        </TouchableOpacity>
      </View>

      {/* Main Tab Screen Content Container */}
      <View style={{ flex: 1 }}>
        {/* --- TAB 1: HOME --- */}
        {activeTab === 'home' && (
          <ScrollView 
            contentContainerStyle={[styles.dashScrollContent, { paddingHorizontal: isSmallDevice ? 12 : 16 }]} 
            showsVerticalScrollIndicator={false}
          >
            {/* Embedded AI Leaf Disease Scanner Launcher */}
            <TouchableOpacity
              style={styles.scanLeafBanner}
              onPress={() => openEmbeddedCamera()}
              activeOpacity={0.85}
            >
              <Text style={styles.scanLeafIcon}>📷</Text>
              <View style={{ flex: 1 }}>
                <Text style={[styles.scanLeafTitle, { fontSize: isSmallDevice ? 14 : 16 }]}>{t.scanLeaf}</Text>
                <Text style={styles.scanLeafSub}>{t.scanLeafSub}</Text>
              </View>
              <Text style={styles.scanLeafArrow}>➔</Text>
            </TouchableOpacity>

            {/* Zone 1 — Hero Audio Advisory Banner */}
            <View style={styles.heroBannerCard}>
              <View style={styles.heroBannerHeader}>
                <View style={styles.heroBadgeUrgent}>
                  <Text style={styles.heroBadgeUrgentText}>{t.urgentPriority}</Text>
                </View>
                <Text style={styles.heroDateText}>{t.todayAction}</Text>
              </View>

              <TouchableOpacity 
                style={[styles.heroAudioPlayBar, isPlayingAudio && styles.heroAudioPlayBarActive]}
                onPress={() => playAdvisoryVoice(urgentAdvisory)}
                activeOpacity={0.85}
              >
                <View style={styles.heroPlayCircle}>
                  <Text style={styles.heroPlaySymbol}>{isPlayingAudio ? '⏸' : '▶'}</Text>
                </View>
                <View style={styles.heroAudioMeta}>
                  <Text style={styles.heroAudioTitle}>
                    {isPlayingAudio ? t.playingAudio : t.todayAdvisory}
                  </Text>
                  <Text style={styles.heroAudioWaveText}>━━━━━━━●━━━━━ 0:25</Text>
                </View>
              </TouchableOpacity>

              {urgentAdvisory && (
                <View style={styles.heroTranscriptBox}>
                  <Text style={styles.heroTranscriptBody}>{urgentAdvisory.body}</Text>
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
                  onPress={() => setActiveModal('irrigation')}
                >
                  <View style={[styles.gridDot, { backgroundColor: THEME.statusCaution }]} />
                  <View style={[styles.gridIconBg, { backgroundColor: '#E0F2FE' }]}>
                    <Text style={styles.gridIcon}>💧</Text>
                  </View>
                  <Text style={styles.gridTitle}>{t.irrigation}</Text>
                  <Text style={styles.gridSub}>{t.gridSubIrrigation}</Text>
                </TouchableOpacity>

                {/* Disease Risk / Scanner */}
                <TouchableOpacity
                  style={[styles.gridCard, { width: gridCardWidth }]}
                  activeOpacity={0.8}
                  onPress={() => openEmbeddedCamera()}
                >
                  <View style={[styles.gridDot, { backgroundColor: THEME.statusUrgent }]} />
                  <View style={[styles.gridIconBg, { backgroundColor: '#FEE2E2' }]}>
                    <Text style={styles.gridIcon}>🍂</Text>
                  </View>
                  <Text style={styles.gridTitle}>{t.disease}</Text>
                  <Text style={styles.gridSub}>{t.gridSubDisease}</Text>
                </TouchableOpacity>

                {/* Crop Health */}
                <TouchableOpacity
                  style={[styles.gridCard, { width: gridCardWidth }]}
                  activeOpacity={0.8}
                  onPress={() => setActiveModal('crop')}
                >
                  <View style={[styles.gridDot, { backgroundColor: THEME.statusGood }]} />
                  <View style={[styles.gridIconBg, { backgroundColor: '#DCFCE7' }]}>
                    <Text style={styles.gridIcon}>🌱</Text>
                  </View>
                  <Text style={styles.gridTitle}>{t.crop}</Text>
                  <Text style={styles.gridSub}>{t.gridSubCrop}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </ScrollView>
        )}

        {/* --- TAB 2: AI SCAN --- */}
        {activeTab === 'scan' && (
          <ScrollView contentContainerStyle={styles.tabContentContainer} showsVerticalScrollIndicator={false}>
            <View style={styles.tabHeaderCard}>
              <Text style={styles.tabHeaderTitle}>📸 {t.scanTitle}</Text>
              <Text style={styles.tabHeaderSub}>{t.scanTabSub}</Text>
            </View>

            <TouchableOpacity
              style={styles.bigScanLauncherBtn}
              onPress={() => openEmbeddedCamera()}
              activeOpacity={0.85}
            >
              <Text style={{ fontSize: 44, marginBottom: 8 }}>📷</Text>
              <Text style={styles.bigScanLauncherTitle}>{t.scanLeaf}</Text>
              <Text style={styles.bigScanLauncherSub}>{t.embeddedCamSub}</Text>
            </TouchableOpacity>

            <View style={{ flexDirection: 'row', gap: 12, marginTop: 12 }}>
              <TouchableOpacity style={[modalStyles.pickerBtn, { flex: 1 }]} onPress={pickImageFromGallery}>
                <Text style={modalStyles.pickerBtnText}>{t.pickGallery}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[modalStyles.pickerBtn, { flex: 1, backgroundColor: THEME.brand800 }]} onPress={takeCameraPhoto}>
                <Text style={[modalStyles.pickerBtnText, { color: '#FFF' }]}>{t.takePhoto}</Text>
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
                      <Text style={modalStyles.diseaseResultTitle}>🍂 {scanResult.disease_name || scanResult.disease || 'Leaf Disease'}</Text>
                      <Text style={modalStyles.confidenceBadge}>{((scanResult.confidence || 0.95) * 100).toFixed(0)}% AI Match</Text>
                    </View>
                    <Text style={modalStyles.recommendationBody}>{scanResult.recommendation || scanResult.recommended_action}</Text>
                    <TouchableOpacity
                      style={modalStyles.playResultVoiceBtn}
                      onPress={() => playAdvisoryVoice({ id: 'scan-tab-adv', body: scanResult.recommendation || scanResult.recommended_action })}
                    >
                      <Text style={modalStyles.playResultVoiceText}>🔊 {t.listenVoice}</Text>
                    </TouchableOpacity>
                  </View>
                ) : null}
              </View>
            )}
          </ScrollView>
        )}

        {/* --- TAB 3: HISTORY --- */}
        {activeTab === 'history' && (
          <ScrollView contentContainerStyle={styles.tabContentContainer} showsVerticalScrollIndicator={false}>
            <View style={styles.tabHeaderCard}>
              <Text style={styles.tabHeaderTitle}>📜 {t.tabHistory}</Text>
              <Text style={styles.tabHeaderSub}>{t.historyTabSub}</Text>
            </View>

            {scanHistory.map((item) => (
              <View key={item.id} style={styles.historyCard}>
                <View style={styles.historyHeader}>
                  <Text style={styles.historyDate}>{item.date}</Text>
                  <View style={[styles.urgencyBadge, { backgroundColor: item.risk_level === 'severe' ? THEME.statusUrgent : THEME.statusCaution }]}>
                    <Text style={styles.urgencyBadgeText}>{(item.risk_level || 'NORMAL').toUpperCase()}</Text>
                  </View>
                </View>
                <Text style={styles.historyDiseaseTitle}>🍂 {item.disease}</Text>
                <Text style={styles.historyFieldSub}>Field: {item.field} • Confidence: {((item.confidence || 0.9) * 100).toFixed(0)}%</Text>
                <Text style={styles.historyRecBody}>{item.recommendation}</Text>
                <TouchableOpacity 
                  style={styles.historyListenBtn}
                  onPress={() => playAdvisoryVoice({ id: item.id, body: item.recommendation })}
                >
                  <Text style={styles.historyListenText}>🔊 {t.listenVoice}</Text>
                </TouchableOpacity>
              </View>
            ))}
          </ScrollView>
        )}

        {/* --- TAB 4: ADVISORIES --- */}
        {activeTab === 'advisories' && (
          <ScrollView contentContainerStyle={styles.tabContentContainer} showsVerticalScrollIndicator={false}>
            <View style={styles.tabHeaderCard}>
              <Text style={styles.tabHeaderTitle}>📢 {t.tabAdvisories}</Text>
              <Text style={styles.tabHeaderSub}>Daily Agronomist & Environmental Guidance</Text>
            </View>

            {advisories.map((adv, idx) => (
              <View key={adv.id || idx} style={styles.feedCardContainer}>
                <View style={styles.feedCardHeader}>
                  <View style={[
                    styles.feedUrgencyPill,
                    { backgroundColor: (adv.urgency === 'high' || adv.urgency === 'urgent') ? THEME.statusUrgent : THEME.statusCaution }
                  ]}>
                    <Text style={styles.feedUrgencyPillText}>{(adv.urgency || 'HIGH').toUpperCase()}</Text>
                  </View>
                  <Text style={styles.feedCardTitle}>{adv.title || t.todayAction}</Text>
                </View>

                <TouchableOpacity 
                  style={styles.feedVoiceBar}
                  onPress={() => playAdvisoryVoice(adv)}
                  activeOpacity={0.8}
                >
                  <View style={styles.feedVoiceIconCircle}>
                    <Text style={styles.feedVoiceIconSymbol}>
                      {playingAdvisoryId === adv.id && isPlayingAudio ? '⏸' : '▶'}
                    </Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.feedVoiceWave}>━━━━━━●━━━━━━━━ 0:15</Text>
                  </View>
                </TouchableOpacity>

                <Text style={styles.feedCardBody}>{adv.body}</Text>
              </View>
            ))}
          </ScrollView>
        )}
      </View>

      {/* --- 4-TAB BOTTOM NAVIGATION BAR --- */}
      <View style={[styles.bottomTabBar, { paddingBottom: Math.max(10, insets.bottom) }]}>
        <TouchableOpacity 
          style={[styles.tabItem, activeTab === 'home' && styles.activeTabItem]}
          onPress={() => setActiveTab('home')}
        >
          <Text style={[styles.tabIcon, activeTab === 'home' && styles.activeTabIcon]}>🌾</Text>
          <Text style={[styles.tabLabel, activeTab === 'home' && styles.activeTabLabel]}>{t.tabHome}</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={[styles.tabItem, activeTab === 'scan' && styles.activeTabItem]}
          onPress={() => setActiveTab('scan')}
        >
          <Text style={[styles.tabIcon, activeTab === 'scan' && styles.activeTabIcon]}>📸</Text>
          <Text style={[styles.tabLabel, activeTab === 'scan' && styles.activeTabLabel]}>{t.tabScan}</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={[styles.tabItem, activeTab === 'history' && styles.activeTabItem]}
          onPress={() => setActiveTab('history')}
        >
          <Text style={[styles.tabIcon, activeTab === 'history' && styles.activeTabIcon]}>📜</Text>
          <Text style={[styles.tabLabel, activeTab === 'history' && styles.activeTabLabel]}>{t.tabHistory}</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={[styles.tabItem, activeTab === 'advisories' && styles.activeTabItem]}
          onPress={() => setActiveTab('advisories')}
        >
          <Text style={[styles.tabIcon, activeTab === 'advisories' && styles.activeTabIcon]}>📢</Text>
          <Text style={[styles.tabLabel, activeTab === 'advisories' && styles.activeTabLabel]}>{t.tabAdvisories}</Text>
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
              <Text style={{ fontSize: 24 }}>🖼️</Text>
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
              <Text style={{ fontSize: 24 }}>⚡</Text>
            </TouchableOpacity>
          </BlurView>
        </View>
      </Modal>

      {/* --- AI LEAF DISEASE SCANNER MODAL --- */}
      <Modal
        visible={scanModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setScanModalVisible(false)}
      >
        <View style={modalStyles.modalOverlay}>
          <View style={[modalStyles.modalCard, { maxHeight: windowHeight * 0.85 }]}>
            <View style={modalStyles.modalHeader}>
              <Text style={modalStyles.modalTitle}>{t.scanTitle}</Text>
              <TouchableOpacity onPress={() => setScanModalVisible(false)}>
                <Text style={modalStyles.closeBtn}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              {selectedImageUri ? (
                <Image source={{ uri: selectedImageUri }} style={modalStyles.previewImage} />
              ) : (
                <View style={modalStyles.placeholderBox}>
                  <Text style={{ fontSize: 44 }}>🍃</Text>
                  <Text style={modalStyles.placeholderText}>Select or capture leaf photo</Text>
                </View>
              )}

              {isAnalyzingImage ? (
                <View style={{ marginVertical: 20, alignItems: 'center' }}>
                  <ActivityIndicator size="large" color={THEME.brand800} />
                  <Text style={{ marginTop: 10, color: THEME.brand900, fontWeight: '600' }}>{t.analyzing}</Text>
                </View>
              ) : scanError ? (
                <View style={{ marginVertical: 20, alignItems: 'center' }}>
                  <Text style={{ color: THEME.statusUrgent, fontWeight: '700', marginBottom: 6, textAlign: 'center' }}>{t.scanErrorTitle}</Text>
                  <Text style={{ color: THEME.ink600, textAlign: 'center', marginBottom: 12 }}>{t.scanErrorBody}</Text>
                  <TouchableOpacity style={modalStyles.pickerBtn} onPress={() => selectedImageUri && analyzeLeafImage(selectedImageUri)}>
                    <Text style={modalStyles.pickerBtnText}>{t.retryBtn}</Text>
                  </TouchableOpacity>
                </View>
              ) : scanResult ? (
                <View style={modalStyles.resultBox}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <Text style={modalStyles.diseaseResultTitle}>🍂 {scanResult.disease_name || 'Leaf Disease'}</Text>
                    <Text style={modalStyles.confidenceBadge}>{(scanResult.confidence * 100).toFixed(0)}% AI Confidence</Text>
                  </View>
                  <Text style={modalStyles.recommendationBody}>{scanResult.recommendation}</Text>

                  <TouchableOpacity 
                    style={modalStyles.playResultVoiceBtn}
                    onPress={() => playAdvisoryVoice({ id: 'scan-adv', body: scanResult.recommendation })}
                  >
                    <Text style={modalStyles.playResultVoiceText}>🔊 {t.listenVoice}</Text>
                  </TouchableOpacity>
                </View>
              ) : null}
            </ScrollView>

            <View style={modalStyles.actionBtnRow}>
              <TouchableOpacity style={modalStyles.pickerBtn} onPress={pickImageFromGallery}>
                <Text style={modalStyles.pickerBtnText}>{t.pickGallery}</Text>
              </TouchableOpacity>

              <TouchableOpacity style={[modalStyles.pickerBtn, { backgroundColor: THEME.brand800 }]} onPress={takeCameraPhoto}>
                <Text style={[modalStyles.pickerBtnText, { color: '#FFF' }]}>{t.takePhoto}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* --- CATEGORY DETAIL MODALS --- */}
      <Modal
        visible={activeModal !== null}
        animationType="fade"
        transparent={true}
        onRequestClose={() => setActiveModal(null)}
      >
        <View style={modalStyles.modalOverlay}>
          <View style={modalStyles.modalCard}>
            <View style={modalStyles.modalHeader}>
              <Text style={modalStyles.modalTitle}>
                {activeModal === 'irrigation' ? t.modalIrrigationTitle : (activeModal === 'crop' ? t.modalCropTitle : t.modalHistoryTitle)}
              </Text>
              <TouchableOpacity onPress={() => setActiveModal(null)}>
                <Text style={modalStyles.closeBtn}>✕</Text>
              </TouchableOpacity>
            </View>

            {activeModal === 'irrigation' && (
              <View style={{ gap: 12, paddingVertical: 10 }}>
                <Text style={{ fontSize: 16, color: THEME.ink900, lineHeight: 24 }}>
                  <Text style={{ fontWeight: 'bold' }}>{t.recommendedDepth}:</Text> 25 mm today
                </Text>
                <Text style={{ fontSize: 16, color: THEME.ink900, lineHeight: 24 }}>
                  <Text style={{ fontWeight: 'bold' }}>{t.soilMoisture}:</Text> Low (18%)
                </Text>
                <Text style={{ fontSize: 16, color: THEME.ink900, lineHeight: 24 }}>
                  <Text style={{ fontWeight: 'bold' }}>{t.weatherForecast}:</Text> 31°C, Clear Sky
                </Text>
                <TouchableOpacity 
                  style={modalStyles.playResultVoiceBtn}
                  onPress={() => playAdvisoryVoice({ id: 'modal-irrig', body: language === 'te' ? 'మీ పత్తి పొలానికి ఈ రోజు 25 మిమి నీరు అందించండి.' : 'Apply 25mm irrigation today.' })}
                >
                  <Text style={modalStyles.playResultVoiceText}>🔊 {t.listenVoice}</Text>
                </TouchableOpacity>
              </View>
            )}

            {activeModal === 'crop' && (
              <View style={{ gap: 12, paddingVertical: 10 }}>
                <Text style={{ fontSize: 16, color: THEME.ink900, lineHeight: 24 }}>
                  <Text style={{ fontWeight: 'bold' }}>{t.cropTypeLabel}:</Text> Cotton (ಹತ್ತಿ / పత్తి / कपास)
                </Text>
                <Text style={{ fontSize: 16, color: THEME.ink900, lineHeight: 24 }}>
                  <Text style={{ fontWeight: 'bold' }}>{t.fieldAreaLabel}:</Text> 3.5 Acres
                </Text>
                <Text style={{ fontSize: 16, color: THEME.ink900, lineHeight: 24 }}>
                  <Text style={{ fontWeight: 'bold' }}>{t.growthPhaseLabel}:</Text> Flowering Stage
                </Text>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// --- Responsive Modal & Screen Styles ---
const modalStyles = StyleSheet.create({
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
    fontSize: 11,
    fontWeight: 'bold',
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
    paddingBottom: 40,
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
    borderRadius: 20,
    padding: 16,
    marginBottom: 18,
    shadowColor: THEME.brand900,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
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
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(45, 106, 79, 0.15)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
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
    borderTopWidth: 1,
    borderTopColor: THEME.glassBorder,
    paddingTop: 8,
    paddingHorizontal: 6,
    shadowColor: THEME.shadowColor,
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.06,
    shadowRadius: 10,
    elevation: 10,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
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
    paddingBottom: 40,
  },
  tabHeaderCard: {
    backgroundColor: THEME.brand900,
    borderRadius: 24,
    padding: 18,
    marginBottom: 16,
  },
  tabHeaderTitle: {
    fontSize: 18,
    fontWeight: 'bold',
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
