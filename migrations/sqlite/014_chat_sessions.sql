-- Module 58: floating chatbot assistant -- persisted chat sessions/messages.
CREATE TABLE IF NOT EXISTS "chat_sessions" (
  "id" text PRIMARY KEY,
  "farmer_id" text NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "title" text,
  "created_at" text NOT NULL,
  "updated_at" text NOT NULL
);

CREATE TABLE IF NOT EXISTS "chat_messages" (
  "id" text PRIMARY KEY,
  "session_id" text NOT NULL REFERENCES "chat_sessions"("id") ON DELETE CASCADE,
  "farmer_id" text NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "role" text NOT NULL,
  "content" text NOT NULL,
  "chart_json" text,
  "cards_json" text,
  "created_at" text NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_chat_sessions_farmer_id" ON "chat_sessions"("farmer_id");
CREATE INDEX IF NOT EXISTS "idx_chat_messages_session_id" ON "chat_messages"("session_id");
CREATE INDEX IF NOT EXISTS "idx_chat_messages_farmer_id" ON "chat_messages"("farmer_id");
