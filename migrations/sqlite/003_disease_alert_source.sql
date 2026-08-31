-- Module 21: additive "source" column on disease_risk_alerts.
-- Same pattern as 002_auth_fields.sql: 001_init.sql already creates this
-- column on a fresh database, and this file is the migration path for a
-- database created before Module 21. SQLite's ALTER TABLE ADD COLUMN has
-- no IF NOT EXISTS, so SQLiteDataStore applies it and tolerates a
-- "duplicate column" error (see _apply_disease_source_migration).

ALTER TABLE disease_risk_alerts ADD COLUMN source TEXT;
