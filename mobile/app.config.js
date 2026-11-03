// Extends app.json (the static config, left as the source of truth for
// everything that doesn't need JS) with the one thing that genuinely
// requires it: the EAS Update channel. app.json is pure JSON -- it cannot
// read process.env at all, so an env var alone (the original, wrong
// approach here) can never reach it. expo-updates reads the channel from
// an `expo-channel-name` request header, which has to be set through a
// dynamic config file to vary by build. See docs/TOOLING.md's "OTA
// updates" section for how this is set at prebuild time.
//
// runtimeVersion is a fixed, manually-bumped string, not the "fingerprint"
// policy -- see decisions/0032-runtime-version-policy.md. fingerprint's
// hash turned out to not be reproducible outside the exact machine/moment
// a given APK was built (confirmed twice, independently, on real shipped
// APKs), so OTA updates were silently failing to reach installed builds
// with no error anywhere. A plain string means a JS-only change always
// reaches every build still on this version, with zero fingerprint
// guesswork -- the cost is remembering to bump this by hand on an actual
// native change (new native module, permission, config plugin, native
// SDK upgrade). See the ADR for the full incident writeup.
module.exports = ({ config }) => ({
  ...config,
  runtimeVersion: '1.0.0',
  updates: {
    ...config.updates,
    requestHeaders: {
      'expo-channel-name': process.env.APP_CHANNEL || 'staging',
    },
  },
});
