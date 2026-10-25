-- AI cascade restructure — additive `source` column on advisories and
-- crop_recommendations (Postgres/Supabase). Mirrors
-- migrations/sqlite/012_cascade_source.sql.

ALTER TABLE advisories ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE crop_recommendations ADD COLUMN IF NOT EXISTS source TEXT;
