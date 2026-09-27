import { AudioPlayer, createAudioPlayer, setAudioModeAsync } from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import * as Speech from 'expo-speech';
import { advisoryAudioUrl } from './api';

let player: AudioPlayer | null = null;

// Every play request gets a ticket. Stopping (or starting another request)
// bumps `current`, so a request that is still downloading/synthesizing when
// the user taps Stop sees its ticket is stale and never starts playing. This
// was the "Stop does nothing" bug: Stop only removed the player, while the
// in-flight download kept going and played afterwards.
let current = 0;

export async function stopAudio() {
  current += 1;
  // stop the audio player first, synchronously; never let a slow TTS engine hold up the caller
  try { player?.pause(); } catch {}
  try { player?.remove(); } catch {}
  player = null;
  try { Promise.resolve(Speech.stop()).catch(() => {}); } catch {}
}

async function playUri(uri: string, ticket: number, onDone: () => void) {
  if (ticket !== current) return;
  await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
  if (ticket !== current) return;
  try { player?.remove(); } catch {}
  const p = createAudioPlayer({ uri });
  player = p;
  p.addListener('playbackStatusUpdate', (s: any) => {
    if (s.didJustFinish && ticket === current) onDone();
  });
  p.play();
}

/** Bundled onboarding clips (mobile/assets/audio) -- static requires, since RN
 *  needs the asset graph at bundle time; no network, no server, no API key.
 *  Missing files (e.g. a language added without recording it yet) resolve to
 *  null so callers can skip playback instead of crashing. */
const ONBOARDING_CLIPS: Record<string, Record<string, number>> = {
  welcome: {
    en: require('../assets/audio/welcome_en.mp3'), kn: require('../assets/audio/welcome_kn.mp3'),
    te: require('../assets/audio/welcome_te.mp3'), hi: require('../assets/audio/welcome_hi.mp3'),
  },
  tour_home: {
    en: require('../assets/audio/tour_home_en.mp3'), kn: require('../assets/audio/tour_home_kn.mp3'),
    te: require('../assets/audio/tour_home_te.mp3'), hi: require('../assets/audio/tour_home_hi.mp3'),
  },
  tour_data: {
    en: require('../assets/audio/tour_data_en.mp3'), kn: require('../assets/audio/tour_data_kn.mp3'),
    te: require('../assets/audio/tour_data_te.mp3'), hi: require('../assets/audio/tour_data_hi.mp3'),
  },
  tour_advice: {
    en: require('../assets/audio/tour_advice_en.mp3'), kn: require('../assets/audio/tour_advice_kn.mp3'),
    te: require('../assets/audio/tour_advice_te.mp3'), hi: require('../assets/audio/tour_advice_hi.mp3'),
  },
  tour_scan: {
    en: require('../assets/audio/tour_scan_en.mp3'), kn: require('../assets/audio/tour_scan_kn.mp3'),
    te: require('../assets/audio/tour_scan_te.mp3'), hi: require('../assets/audio/tour_scan_hi.mp3'),
  },
};
export type OnboardingClip = keyof typeof ONBOARDING_CLIPS;

/** Plays a bundled onboarding clip fully offline. Resolves once playback
 *  starts (not once it finishes) unless `onDone` is given. */
export async function playOnboardingClip(clip: OnboardingClip, lang: string, onDone?: () => void): Promise<boolean> {
  const src = ONBOARDING_CLIPS[clip]?.[lang] ?? ONBOARDING_CLIPS[clip]?.en;
  if (src === undefined) return false;
  const ticket = ++current;
  try { player?.remove(); } catch {}
  await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
  if (ticket !== current) return false;
  const p = createAudioPlayer(src);
  player = p;
  if (onDone) {
    p.addListener('playbackStatusUpdate', (s: any) => {
      if (s.didJustFinish && ticket === current) onDone();
    });
  }
  p.play();
  return true;
}

/** File extension matching the server's audio type (players pick the decoder from it). */
function extFor(mime?: string | null): string {
  const m = (mime || '').toLowerCase();
  if (m.includes('ogg')) return 'ogg';
  if (m.includes('wav')) return 'wav';
  if (m.includes('mp4') || m.includes('aac')) return 'm4a';
  return 'mp3';
}

/** Plays base64 audio (the /v2/voice/ask answer); `mime` is the server-reported type. */
export async function playBase64(b64: string, mime: string | null | undefined, onDone: () => void) {
  const ticket = ++current;
  try { await Speech.stop(); } catch {}
  const f = new File(Paths.cache, `answer-${ticket}.${extFor(mime)}`);
  if (f.exists) f.delete();
  f.create();
  f.write(b64, { encoding: 'base64' } as any);
  await playUri(f.uri, ticket, onDone);
}

const DEVICE_LOCALE: Record<string, string> = { en: 'en-IN', kn: 'kn-IN', te: 'te-IN', hi: 'hi-IN' };

/** The phone's own TTS locale for `lang`, or null when the phone has no voice for it
 *  (Android's built-in engine coverage of kn/te/hi varies by device). English always
 *  resolves, falling back to the engine default. */
export async function deviceVoiceLocale(lang: string): Promise<string | null> {
  const want = DEVICE_LOCALE[lang];
  if (!want) return null;
  try {
    const voices = await Speech.getAvailableVoicesAsync();
    const norm = (l: string) => l.replace('_', '-').toLowerCase();
    const hit = voices.find((v) => norm(v.language) === norm(want))
      ?? voices.find((v) => norm(v.language).startsWith(lang));
    if (hit) return hit.language;
  } catch {}
  return lang === 'en' ? want : null;
}

/** Dev-only switch to exercise the fallback without touching the real voice
 *  service / Sarvam quota: set EXPO_PUBLIC_FORCE_VOICE_503=1 and restart Metro. */
const FORCE_VOICE_503 = __DEV__ && process.env.EXPO_PUBLIC_FORCE_VOICE_503 === '1';

export type AdvisoryPlayback = 'server' | 'device' | 'text-only' | 'cancelled';

/** Server audio for an advisory (plain-language text, translated to `lang`,
 *  spoken by the voice service), downloaded with fetch() so it carries the
 *  session cookie, then played from a local file. If the server voice is
 *  unavailable it falls back to the phone's own TTS reading `displayText` (the
 *  text already on screen, in `lang`). If the phone has no voice for `lang`, or
 *  the text never got translated, nothing is spoken ('text-only') rather than
 *  reading it in the wrong language. */
export async function playAdvisory(
  id: string, lang: string, displayText: string, translated: boolean, onDone: () => void,
): Promise<AdvisoryPlayback> {
  await stopAudio();
  const ticket = current;
  try {
    if (FORCE_VOICE_503) throw new Error('HTTP 503 (forced)');
    const res = await fetch(advisoryAudioUrl(id, lang));
    if (ticket !== current) return 'cancelled';
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const bytes = new Uint8Array(await res.arrayBuffer());
    if (ticket !== current) return 'cancelled';
    if (!bytes.length) throw new Error('empty audio');
    const f = new File(Paths.cache, `advisory-${id}-${lang}-${bytes.length}.${extFor(res.headers.get('content-type'))}`);
    if (f.exists) f.delete();
    f.create();
    f.write(bytes);
    await playUri(f.uri, ticket, onDone);
    return ticket === current ? 'server' : 'cancelled';
  } catch {
    if (ticket !== current) return 'cancelled';
    const locale = (lang === 'en' || translated) ? await deviceVoiceLocale(lang) : null;
    if (ticket !== current) return 'cancelled';
    if (!locale) { onDone(); return 'text-only'; }
    Speech.speak(displayText.replace(/\(.*?\)/g, ''), { language: locale, onDone, onError: onDone, onStopped: onDone });
    return 'device';
  }
}

/** Reads `text` with the phone's own voice in `lang` (used when the server voice is down).
 *  Returns false, speaking nothing, when the phone has no voice for that language. */
export async function speakOnDevice(text: string, lang: string, onDone: () => void): Promise<boolean> {
  const locale = await deviceVoiceLocale(lang);
  if (!locale) return false;
  Speech.speak(text.replace(/\(.*?\)/g, ''), { language: locale, onDone, onError: onDone, onStopped: onDone });
  return true;
}
