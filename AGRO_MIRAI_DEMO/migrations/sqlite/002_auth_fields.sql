-- Module 19 — multi-tenant auth fields on farmers.
-- Hand-written (not gen_migrations.py output): 001_init.sql already
-- creates email/password_hash/role on a FRESH database (CREATE TABLE IF
-- NOT EXISTS picks them up automatically once schema.yaml is
-- regenerated). This file is the migration path for a database file
-- created before Module 19 -- e.g. an existing local agro_mirai.db or
-- seed_fixture.db -- where those columns don't exist yet. SQLite's
-- ALTER TABLE ADD COLUMN has no IF NOT EXISTS, so SQLiteDataStore
-- applies each statement individually and tolerates "duplicate column"
-- errors (see _apply_migration in sqlite_store.py), making this file
-- safe to re-run against both old and already-migrated databases.

ALTER TABLE farmers ADD COLUMN email TEXT;
ALTER TABLE farmers ADD COLUMN password_hash TEXT;
ALTER TABLE farmers ADD COLUMN role TEXT NOT NULL DEFAULT 'farmer';

CREATE UNIQUE INDEX IF NOT EXISTS idx_farmers_email ON farmers(email) WHERE email IS NOT NULL;
