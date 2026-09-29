import * as Updates from 'expo-updates';

/** Silent, non-blocking OTA update check -- called once on app launch.
 *  Never throws into the caller: a failed check (offline, EAS unreachable,
 *  or running in Expo Go / a dev-client session where custom update
 *  servers aren't supported) is exactly as unremarkable as "no update
 *  available" -- the app just keeps running on its current bundle,
 *  matching this project's degrade-never-fail doctrine. The downloaded
 *  update applies on the *next* app launch, per expo-updates' own
 *  default behavior -- this function never force-reloads mid-session. */
export async function checkForAppUpdate(): Promise<void> {
  if (!Updates.isEnabled) return; // Expo Go / dev-client / no update server configured
  try {
    const result = await Updates.checkForUpdateAsync();
    if (result.isAvailable) {
      await Updates.fetchUpdateAsync();
    }
  } catch {
    // Silent by design -- see doc comment above.
  }
}
