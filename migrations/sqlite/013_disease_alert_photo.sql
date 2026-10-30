-- Scan photo persistence (2026-10-30) -- stored server-side so a farmer's
-- scan history survives a reinstall/new device/re-login, not just the local
-- on-device cache it previously relied on entirely. Same base64-data-URI
-- pattern as 006_farmer_photo.sql (no file-storage service exists yet).

ALTER TABLE disease_risk_alerts ADD COLUMN photo_url TEXT;
