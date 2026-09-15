-- Module 33: drop a leftover FK constraint from the reverted Module 26
-- (Supabase Auth) design. The live hosted Supabase project's `farmers`
-- table still carried `farmers_id_fkey_auth_users` (farmers.id ->
-- auth.users.id), but decisions/0023-name-phone-otp-auth.md moved farmer
-- auth to self-owned Name+Phone+OTP: farmers now get a self-issued UUID
-- with no corresponding auth.users row, so this constraint rejects every
-- farmer insert made via SupabaseDataStore. Confirmed live during Module
-- 33's Supabase round-trip test (ConflictError 23503 on every
-- save_farmer call) before being dropped here.
ALTER TABLE farmers DROP CONSTRAINT IF EXISTS farmers_id_fkey_auth_users;
