-- Module: Ask AI conversation history persistence in PostgreSQL / Supabase.
CREATE TABLE IF NOT EXISTS "conversations" (
  "id" uuid PRIMARY KEY,
  "farmer_id" uuid NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "field_id" uuid REFERENCES "fields"("id") ON DELETE CASCADE,
  "question" text NOT NULL,
  "answer" text NOT NULL,
  "language" text NOT NULL,
  "created_at" timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_conversations_farmer_id" ON "conversations"("farmer_id");
CREATE INDEX IF NOT EXISTS "idx_conversations_field_id" ON "conversations"("field_id");
