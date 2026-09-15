-- Module 33: the live hosted Supabase project's originally-applied init
-- migration (2026-08-25) predates Module 18's regional-suitability fields,
-- even though the local migrations/postgres/001_init.sql source already
-- has them -- confirmed live during Module 33's Supabase round-trip test
-- (PGRST204 "Could not find the 'out_of_region' column"). Backfills the
-- two columns to match 001_init.sql exactly.
ALTER TABLE crop_recommendations ADD COLUMN IF NOT EXISTS "out_of_region" boolean;
ALTER TABLE crop_recommendations ADD COLUMN IF NOT EXISTS "regional_alternative" text;
