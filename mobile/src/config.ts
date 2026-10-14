import Constants from 'expo-constants';
import { Platform } from 'react-native';

// Backend port only -- the *host* is derived at runtime, never hardcoded,
// since it changes with whatever Wi-Fi network the dev machine is on.
const BACKEND_PORT = 5000;

/**
 * Derives the backend's base URL from wherever this app's own JS bundle
 * was loaded from, instead of a hardcoded IP:
 *   - Web (Expo web / browser): the page's own hostname
 *     (window.location.hostname) -- if the browser can load this page
 *     from that host, the backend on the same machine is reachable at the
 *     same host.
 *   - Native via Expo Go / a dev client: Metro's `hostUri`
 *     (Constants.expoConfig?.hostUri, e.g. "10.105.30.242:8081") -- the
 *     same IP the phone used to fetch the JS bundle, so it's guaranteed
 *     reachable from the phone right now, on whatever network it's on.
 *   - Native standalone (a built APK/IPA, no Metro/hostUri): falls back
 *     to PRODUCTION_API_BASE_URL below, since there's no bundle-load host
 *     to infer from at all.
 *
 * This means every developer/tester gets a working API_BASE_URL for
 * their current network automatically, with nothing to hand-edit here.
 */
function resolveApiBaseUrl(): string {
  const override = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (override) return override.replace(/\/+$/, '');

  // If explicitly configured for local development, resolve dev machine IP
  if (process.env.EXPO_PUBLIC_USE_LOCAL_BACKEND === 'true') {
    if (Platform.OS === 'web') {
      if (typeof window !== 'undefined' && window.location?.hostname) {
        return `http://${window.location.hostname}:${BACKEND_PORT}`;
      }
    } else {
      const hostUri = Constants.expoConfig?.hostUri;
      if (hostUri) {
        const host = hostUri.split(':')[0];
        if (host) {
          return `http://${host}:${BACKEND_PORT}`;
        }
      }
    }
  }

  // Default to live verified production cloud backend (Render)
  return PRODUCTION_API_BASE_URL;
}

const PRODUCTION_API_BASE_URL = 'https://agro-mirai.onrender.com';


export const API_BASE_URL = resolveApiBaseUrl();

// Module 27: farmer auth moved to the backend's Name+Phone+OTP endpoints
// (decisions/0023-name-phone-otp-auth.md) -- the app no longer talks to
// Supabase Auth directly, so no Supabase client/keys belong here. The
// previous version of this file shipped a Supabase **service-role** key
// (full DB admin, bypasses RLS) in client code, a real security issue
// flagged and rotated separately from this fix. If this app ever needs
// direct Supabase access again for something other than auth, use the
// anon key only, never the service-role key, in client code.
