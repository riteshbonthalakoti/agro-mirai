-- Module: Ask AI conversation history persistence in database.
CREATE TABLE IF NOT EXISTS "conversations" (
  "id" text PRIMARY KEY,
  "farmer_id" text NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "field_id" text REFERENCES "fields"("id") ON DELETE CASCADE,
  "question" text NOT NULL,
  "answer" text NOT NULL,
  "language" text NOT NULL,
  "created_at" text NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_conversations_farmer_id" ON "conversations"("farmer_id");
CREATE INDEX IF NOT EXISTS "idx_conversations_field_id" ON "conversations"("field_id");
