-- Module 26 — migrate off the Module 19 bcrypt+session model onto
-- Supabase Auth. See decisions/0022-supabase-auth-migration.md.
--
-- Clean-slate reset (explicitly decided, not a silent data drop): every
-- existing farmer row's password_hash is now unusable (Supabase Auth
-- owns credentials, and there is no way to recover a plaintext password
-- from a bcrypt hash to re-register it there), and this project has only
-- seeded/test data at this stage. All existing farmers (and everything
-- that cascades from them — fields, advisories, feedback, etc.) are
-- wiped; farmers re-register fresh through the Supabase SDK, and Flask
-- auto-provisions a new profile row (keyed by the Supabase user id) on
-- their first authenticated request. A local SQLite dev DB is trivially
-- reproducible via tools/seed_fixture.py, so this is safe here; the
-- Postgres/Supabase twin of this migration does the same wipe.
DELETE FROM farmers;

-- ALTER TABLE DROP COLUMN needs SQLite >= 3.35 (2021); this project's
-- dev environment is well past that (3.49 verified). Tolerated the same
-- way ADD COLUMN is tolerated elsewhere in this migration chain
-- (sqlite_store.py's _apply_migration split-and-catch pattern) in case
-- an older SQLite is ever used to open this file directly.
ALTER TABLE farmers DROP COLUMN password_hash;
