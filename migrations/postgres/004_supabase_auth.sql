-- Module 26 — migrate off the Module 19 bcrypt+session model onto
-- Supabase Auth. See decisions/0022-supabase-auth-migration.md.
-- Apply out-of-band via the Supabase CLI (this project's SupabaseDataStore
-- never runs DDL itself, CLAUDE.md hard rule #1/#3):
--
--   supabase db execute --file migrations/postgres/004_supabase_auth.sql
--
-- Clean-slate reset (explicitly decided, not a silent data drop): every
-- existing farmer row's password_hash is now unusable (Supabase Auth owns
-- credentials; a bcrypt hash cannot be turned back into a plaintext
-- password to re-register in Supabase Auth), and this project has only
-- seeded/test data at this stage. Every farmer row (and everything that
-- cascades from it via ON DELETE CASCADE — fields, advisories, feedback,
-- etc.) is wiped; farmers re-register fresh through the Supabase SDK, and
-- Flask auto-provisions a new profile row (keyed by the Supabase-issued
-- auth.users.id) on their first authenticated request.
DELETE FROM farmers;

ALTER TABLE farmers DROP COLUMN IF EXISTS password_hash;

-- farmers.id is now the Supabase-issued auth.users.id for every farmer
-- registered from this point forward (Module 26's re-keying decision —
-- see the ADR for why no separate mapping/auth_id column was needed).
-- This FK makes that real: it is enforced at the database level, and
-- deleting a Supabase user cleans up their farmer profile (and
-- everything that cascades from it) automatically instead of leaving an
-- orphaned row. NOT VALID + a separate VALIDATE step would be needed on
-- a table with existing rows that violate it; since this migration just
-- wiped every row above, ADD CONSTRAINT can validate immediately.
ALTER TABLE farmers
  ADD CONSTRAINT farmers_id_fkey_auth_users
  FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;
