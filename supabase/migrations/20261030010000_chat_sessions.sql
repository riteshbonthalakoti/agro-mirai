-- Module 58: floating chatbot assistant -- persisted chat sessions/messages.
CREATE TABLE IF NOT EXISTS "chat_sessions" (
  "id" uuid PRIMARY KEY,
  "farmer_id" uuid NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "title" text,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS "chat_messages" (
  "id" uuid PRIMARY KEY,
  "session_id" uuid NOT NULL REFERENCES "chat_sessions"("id") ON DELETE CASCADE,
  "farmer_id" uuid NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "role" text NOT NULL,
  "content" text NOT NULL,
  "chart_json" text,
  "cards_json" text,
  "created_at" timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_chat_sessions_farmer_id" ON "chat_sessions"("farmer_id");
CREATE INDEX IF NOT EXISTS "idx_chat_messages_session_id" ON "chat_messages"("session_id");
CREATE INDEX IF NOT EXISTS "idx_chat_messages_farmer_id" ON "chat_messages"("farmer_id");

ALTER TABLE "chat_sessions" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chat_sessions_farmer_isolation" ON "chat_sessions"
  FOR ALL USING (farmer_id = auth.uid());

ALTER TABLE "chat_messages" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chat_messages_farmer_isolation" ON "chat_messages"
  FOR ALL USING (farmer_id = auth.uid());
