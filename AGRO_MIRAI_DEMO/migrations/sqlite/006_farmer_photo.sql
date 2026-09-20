-- Module 30 -- farmer profile photo. No file-storage service exists yet
-- (no S3/Supabase storage bucket wired up), so the photo is stored as a
-- base64 data URI directly in this column -- simplest thing that works
-- for a small profile picture, no new infra needed. Same ADD-COLUMN
-- tolerant pattern as 002_auth_fields.sql: safe to re-run against both
-- old and already-migrated databases.

ALTER TABLE farmers ADD COLUMN photo_url TEXT;
