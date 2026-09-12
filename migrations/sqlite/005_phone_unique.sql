-- Module 27 — Name+Phone+OTP auth: phone must be unique so
-- get_farmer_by_phone resolves to at most one farmer. 001_init.sql's
-- `phone TEXT` column already exists on every database (Module 01), so
-- this is index-only, safe to re-run (CREATE UNIQUE INDEX IF NOT EXISTS).
-- Partial (WHERE phone IS NOT NULL) so /v1-only farmers with no phone set
-- don't collide with each other under the index.

CREATE UNIQUE INDEX IF NOT EXISTS idx_farmers_phone ON farmers(phone) WHERE phone IS NOT NULL;
