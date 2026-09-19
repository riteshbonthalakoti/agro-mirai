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
  // Build-time override (EXPO_PUBLIC_* is inlined by Metro at bundle time), so
  // a standalone release APK can be pointed at a specific backend with no
  // Metro/hostUri to infer from -- e.g. EXPO_PUBLIC_API_BASE_URL=http://<host>:5000
  const override = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (override) return override.replace(/\/+$/, '');

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

  console.warn(
    'Could not derive API_BASE_URL from the dev server host (no hostUri/window.location available -- ' +
      'likely a standalone production build). Falling back to PRODUCTION_API_BASE_URL.'
  );
  return PRODUCTION_API_BASE_URL;
}

// Set this once a real backend is deployed (Render, etc.) so a standalone
// production build (no Metro dev server to infer a host from) still has
// somewhere to call. Empty today because no production deploy exists yet
// -- see decisions/0019-deployment-architecture.md.
const PRODUCTION_API_BASE_URL = '';

export const API_BASE_URL = resolveApiBaseUrl();

// Module 27: farmer auth moved to the backend's Name+Phone+OTP endpoints
// (decisions/0023-name-phone-otp-auth.md) -- the app no longer talks to
// Supabase Auth directly, so no Supabase client/keys belong here. The
// previous version of this file shipped a Supabase **service-role** key
// (full DB admin, bypasses RLS) in client code, a real security issue
// flagged and rotated separately from this fix. If this app ever needs
// direct Supabase access again for something other than auth, use the
// anon key only, never the service-role key, in client code.
