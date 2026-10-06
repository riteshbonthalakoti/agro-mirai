import { requireNativeModule } from 'expo-modules-core';
import { Platform } from 'react-native';

type SmsRetrieverNativeModule = {
  startSmsRetriever(): Promise<string | null>;
  stopSmsRetriever(): Promise<void>;
  getAppSignatures(): string[];
};

// Expo Go has no custom native modules at all -- this module only exists in
// a dev-client/production build that was prebuilt with it. requireNativeModule
// throws synchronously if it's missing, so this must never crash app startup
// under Expo Go; auto-fill just silently stays unavailable there (manual
// entry still works everywhere).
let NativeModule: SmsRetrieverNativeModule | null = null;
if (Platform.OS === 'android') {
  try {
    NativeModule = requireNativeModule('SmsRetriever');
  } catch {
    NativeModule = null;
  }
}

/**
 * Starts listening for the next SMS carrying this app's signature hash
 * and resolves with its full text, or null/throws if unsupported
 * (iOS, or Google Play Services unavailable) -- callers must keep the
 * existing manual-entry path as the fallback, never block on this.
 */
export async function startSmsRetriever(): Promise<string | null> {
  if (!NativeModule) return null;
  try {
    return await NativeModule.startSmsRetriever();
  } catch {
    return null;
  }
}

export async function stopSmsRetriever(): Promise<void> {
  await NativeModule?.stopSmsRetriever();
}

/** Dev utility: logs the hash to append as SMS_APP_HASH on the backend. */
export function getAppSignatures(): string[] {
  return NativeModule?.getAppSignatures() ?? [];
}

/** First 6 consecutive digits in the SMS body -- our OTP format is "123456 is your AGRO MIRAI login code...". */
export function extractOtpCode(smsBody: string): string | null {
  const match = smsBody.match(/\b(\d{6})\b/);
  return match ? match[1] : null;
}
