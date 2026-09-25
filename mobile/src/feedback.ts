import { useEffect, useState } from 'react';
import { Platform, Vibration } from 'react-native';
import * as Haptics from 'expo-haptics';
import { AudioPlayer, createAudioPlayer } from 'expo-audio';
import { cacheGet, cacheSet } from './storage';

/** Touch feedback for the whole app: a light haptic on taps, and for the moments that matter
 *  (success, warning, error, clearing, shutter, new alert) a haptic plus a short synthesised sound.
 *
 *  Buttons and tabs vibrate lightly but stay silent (they are pressed hundreds of times);
 *  sounds are reserved for real events. One switch in Me turns everything off. Every call is
 *  fire-and-forget and swallows errors: feedback must never break a screen. */

type Sound = 'success' | 'warning' | 'error' | 'clear' | 'shutter' | 'notify';
const SRC: Record<Sound, number> = {
  success: require('../assets/sounds/success.wav'),
  warning: require('../assets/sounds/warning.wav'),
  error: require('../assets/sounds/error.wav'),
  clear: require('../assets/sounds/clear.wav'),
  shutter: require('../assets/sounds/shutter.wav'),
  notify: require('../assets/sounds/notify.wav'),
};

const KEY = 'feedbackOn';
let enabled = true;
const listeners = new Set<(on: boolean) => void>();
cacheGet<boolean>(KEY).then((v) => {
  if (v === false) {
    enabled = false;
    listeners.forEach((f) => f(false));
  }
});

export const feedbackEnabled = () => enabled;
export function setFeedbackEnabled(on: boolean) {
  enabled = on;
  cacheSet(KEY, on);
  listeners.forEach((f) => f(on));
}
/** For the settings switch: current value, kept in step with changes and with the saved preference loading. */
export function useFeedbackEnabled(): boolean {
  const [on, setOn] = useState(enabled);
  useEffect(() => {
    listeners.add(setOn);
    setOn(enabled);
    return () => { listeners.delete(setOn); };
  }, []);
  return on;
}

const players: Partial<Record<Sound, AudioPlayer>> = {};
function play(name: Sound, volume = 0.7) {
  try {
    let p = players[name];
    if (!p) {
      p = createAudioPlayer(SRC[name]);
      players[name] = p;
    }
    p.volume = volume;
    p.seekTo(0).catch(() => {});
    p.play();
  } catch {}
}

const safe = (p: Promise<unknown>) => { p.catch(() => {}); };

export const feedback = {
  /** every button, chip and tab: a light tick, no sound */
  tap() {
    if (enabled) safe(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
  },
  /** picking one option out of several */
  select() {
    if (enabled) safe(Haptics.selectionAsync());
  },
  success() {
    if (!enabled) return;
    safe(Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
    play('success');
  },
  warning() {
    if (!enabled) return;
    safe(Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning));
    play('warning');
  },
  error() {
    if (!enabled) return;
    safe(Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));
    play('error');
  },
  /** clearing notifications / lists: a smooth downward swish and two soft pulses */
  clear() {
    if (!enabled) return;
    play('clear', 0.8);
    if (Platform.OS === 'android') Vibration.vibrate([0, 30, 60, 30]);
    else safe(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
  },
  shutter() {
    if (!enabled) return;
    play('shutter', 0.9);
    safe(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy));
  },
  /** an alert arrived while the phone cannot show a system notification (Expo Go) */
  notify() {
    if (!enabled) return;
    play('notify');
    if (Platform.OS === 'android') Vibration.vibrate([0, 40, 80, 40]);
    else safe(Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
  },
};
