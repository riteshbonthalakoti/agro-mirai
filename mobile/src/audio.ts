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
