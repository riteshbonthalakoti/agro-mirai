-- Module 59: Android push notifications (Expo push tokens per device).
-- A farmer can have multiple tokens (multiple devices/reinstalls) -- the
-- token itself is the natural dedup key, not a per-farmer single row.
CREATE TABLE IF NOT EXISTS "push_tokens" (
  "id" text PRIMARY KEY,
  "farmer_id" text NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "token" text NOT NULL UNIQUE,
  "platform" text NOT NULL DEFAULT 'android',
  "created_at" text NOT NULL,
  "updated_at" text NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_push_tokens_farmer_id" ON "push_tokens"("farmer_id");
