-- AI cascade restructure: additive "source" column on advisories and
-- crop_recommendations, same pattern as 003_disease_alert_source.sql.
-- SQLite's ALTER TABLE ADD COLUMN has no IF NOT EXISTS, so
-- SQLiteDataStore applies this statement-by-statement and tolerates a
-- "duplicate column" error (see _apply_cascade_source_migration).

ALTER TABLE advisories ADD COLUMN source TEXT;
ALTER TABLE crop_recommendations ADD COLUMN source TEXT;
