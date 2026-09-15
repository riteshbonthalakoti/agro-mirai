-- Module 30 -- farmer profile photo. See sqlite/006_farmer_photo.sql for
-- the full reasoning (base64 data URI, no file-storage service yet).

ALTER TABLE "farmers" ADD COLUMN IF NOT EXISTS "photo_url" text;
