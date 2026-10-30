-- Module 59: Android push notifications (Expo push tokens per device).
CREATE TABLE IF NOT EXISTS "push_tokens" (
  "id" uuid PRIMARY KEY,
  "farmer_id" uuid NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "token" text NOT NULL UNIQUE,
  "platform" text NOT NULL DEFAULT 'android',
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_push_tokens_farmer_id" ON "push_tokens"("farmer_id");

ALTER TABLE "push_tokens" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "push_tokens_farmer_isolation" ON "push_tokens"
  FOR ALL USING (farmer_id = auth.uid());
