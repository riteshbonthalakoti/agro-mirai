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
  try { await Speech.stop(); } catch {}
  try { player?.pause(); } catch {}
  try { player?.remove(); } catch {}
  player = null;
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

/** Server audio for an advisory (plain-language text, translated to `lang`,
 *  spoken by the voice service), downloaded with fetch() so it carries the
 *  session cookie, then played from a local file. If the server voice is
 *  unavailable it falls back to the phone's own TTS -- in English, because the
 *  phone has no translation -- and returns which one ran. */
export async function playAdvisory(
  id: string, lang: string, englishText: string, onDone: () => void,
): Promise<'server' | 'device' | 'cancelled'> {
  await stopAudio();
  const ticket = current;
  try {
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
    Speech.speak(englishText.replace(/\(.*?\)/g, ''), { language: 'en-IN', onDone, onError: onDone, onStopped: onDone });
    return 'device';
  }
}
