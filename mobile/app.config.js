// Extends app.json (the static config, left as the source of truth for
// everything that doesn't need JS) with the one thing that genuinely
// requires it: the EAS Update channel. app.json is pure JSON -- it cannot
// read process.env at all, so an env var alone (the original, wrong
// approach here) can never reach it. expo-updates reads the channel from
// an `expo-channel-name` request header, which has to be set through a
// dynamic config file to vary by build. See docs/TOOLING.md's "OTA
// updates" section for how this is set at prebuild time.
//
// Also switches runtimeVersion to the "fingerprint" policy instead of
// "appVersion": fingerprint is computed from the actual native code, so
// an update can never be silently offered to a binary with a mismatched
// native module set just because someone forgot to bump `version` in
// app.json (a real, easy-to-miss maintenance burden `appVersion` would
// have left on every future native change).
module.exports = ({ config }) => ({
  ...config,
  runtimeVersion: { policy: 'fingerprint' },
  updates: {
    ...config.updates,
    requestHeaders: {
      'expo-channel-name': process.env.APP_CHANNEL || 'staging',
    },
  },
});
