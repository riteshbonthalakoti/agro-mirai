-- Module 19 — multi-tenant auth fields on farmers (Postgres/Supabase).
-- Hand-written, mirrors migrations/sqlite/002_auth_fields.sql. Postgres
-- supports IF NOT EXISTS on ADD COLUMN, so this is idempotent as-is.
-- Apply out-of-band via the Supabase CLI per docs/TOOLING.md /
-- decisions/0005-migration-generation.md -- this project's SupabaseDataStore
-- never runs DDL itself (CLAUDE.md hard rule #1/#3):
--
--   supabase db execute --file migrations/postgres/002_auth_fields.sql
--
-- (or apply via `psql "$SUPABASE_DB_URL" -f migrations/postgres/002_auth_fields.sql`
-- if the `supabase db execute` subcommand is unavailable in the
-- installed CLI version -- check `supabase --version` / `supabase db --help`).

ALTER TABLE farmers ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE farmers ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE farmers ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'farmer';

CREATE UNIQUE INDEX IF NOT EXISTS idx_farmers_email ON farmers(email) WHERE email IS NOT NULL;
