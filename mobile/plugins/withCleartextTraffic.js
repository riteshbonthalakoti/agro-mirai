// Release builds block plain-http by default (Android 9+). The backend is
// currently reached over http on a LAN/dev host, so without this every API
// call in a release APK fails. REMOVE once the backend is served over HTTPS.
const { withAndroidManifest } = require('expo/config-plugins');

module.exports = function withCleartextTraffic(config) {
  return withAndroidManifest(config, (cfg) => {
    cfg.modResults.manifest.application[0].$['android:usesCleartextTraffic'] = 'true';
    return cfg;
  });
};
