-- Module 27 — Name+Phone+OTP auth: phone must be unique so
-- get_farmer_by_phone resolves to at most one farmer. Mirrors
-- migrations/sqlite/005_phone_unique.sql. Apply out-of-band via the
-- Supabase CLI (this project's SupabaseDataStore never runs DDL itself,
-- CLAUDE.md hard rule #1/#3):
--
--   supabase db execute --file migrations/postgres/005_phone_unique.sql
--
-- (or `psql "$SUPABASE_DB_URL" -f migrations/postgres/005_phone_unique.sql`
-- if `supabase db execute` is unavailable in the installed CLI version).

CREATE UNIQUE INDEX IF NOT EXISTS idx_farmers_phone ON farmers(phone) WHERE phone IS NOT NULL;
