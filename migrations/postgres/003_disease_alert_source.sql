-- Module 21 — additive `source` column on disease_risk_alerts (Postgres/Supabase).
-- Mirrors migrations/sqlite/003_disease_alert_source.sql. Apply out-of-band:
--
--   supabase db execute --file migrations/postgres/003_disease_alert_source.sql

ALTER TABLE disease_risk_alerts ADD COLUMN IF NOT EXISTS source TEXT;
