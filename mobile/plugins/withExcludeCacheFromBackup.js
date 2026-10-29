// Field finding (2026-10-27): the AndroidManifest points
// android:fullBackupContent/android:dataExtractionRules at
// @xml/secure_store_backup_rules and @xml/secure_store_data_extraction_rules,
// which are resources *bundled inside the expo-secure-store library itself*
// (node_modules/expo-secure-store/android/src/main/res/xml/) -- they only
// exclude expo-secure-store's own "SecureStore" shared-prefs file and
// blanket *include* every other shared-prefs file. That's exactly where
// @react-native-async-storage/async-storage keeps its data on Android (the
// "RKStorage" shared-prefs file). Android's auto backup/restore then
// silently restores the app's local cache (scan history, etc.) after a
// fresh install whenever the device has "Backup by Google One" on and is
// signed into the same account -- uninstalling the app never actually
// cleared it, which looked exactly like a hardcoded/stuck result.
//
// Fix: write app-module copies of the SAME two resource names. Android's
// resource merging lets the app module's own res/xml files override a
// library's resources of the same name, so these win over
// expo-secure-store's versions without touching that package.
const fs = require('fs');
const path = require('path');
const { withDangerousMod } = require('expo/config-plugins');

const BACKUP_RULES = `<?xml version="1.0" encoding="utf-8"?>
<!-- Auto Backup configuration for Android 11 and lower -->
<full-backup-content>
  <include domain="sharedpref" path="."/>
  <exclude domain="sharedpref" path="SecureStore"/>
  <exclude domain="sharedpref" path="RKStorage.xml"/>
</full-backup-content>
`;

const DATA_EXTRACTION_RULES = `<?xml version="1.0" encoding="utf-8"?>
<!-- Auto Backup configuration for Android 12 and higher -->
<data-extraction-rules>
  <cloud-backup>
    <include domain="sharedpref" path="."/>
    <exclude domain="sharedpref" path="SecureStore"/>
    <exclude domain="sharedpref" path="RKStorage.xml"/>
  </cloud-backup>
  <device-transfer>
    <include domain="sharedpref" path="."/>
    <exclude domain="sharedpref" path="SecureStore"/>
    <exclude domain="sharedpref" path="RKStorage.xml"/>
  </device-transfer>
</data-extraction-rules>
`;

module.exports = function withExcludeCacheFromBackup(config) {
  return withDangerousMod(config, [
    'android',
    (cfg) => {
      const xmlDir = path.join(cfg.modRequest.platformProjectRoot, 'app/src/main/res/xml');
      fs.mkdirSync(xmlDir, { recursive: true });
      fs.writeFileSync(path.join(xmlDir, 'secure_store_backup_rules.xml'), BACKUP_RULES, 'utf8');
      fs.writeFileSync(
        path.join(xmlDir, 'secure_store_data_extraction_rules.xml'),
        DATA_EXTRACTION_RULES,
        'utf8',
      );
      return cfg;
    },
  ]);
};
