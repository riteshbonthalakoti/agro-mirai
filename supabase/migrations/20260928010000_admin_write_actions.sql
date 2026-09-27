-- Module 50: admin dashboard v2 (Phase 1). Additive-only (hard rule 2).
-- Mirrors migrations/postgres/010_admin_write_actions.sql -- see that
-- file and decisions/0030-admin-write-actions.md for the full reasoning.
ALTER TABLE "bug_reports" ADD COLUMN IF NOT EXISTS "status" text NOT NULL DEFAULT 'open';

CREATE TABLE IF NOT EXISTS "audit_log" (
  "id" uuid PRIMARY KEY,
  "admin_farmer_id" uuid NOT NULL REFERENCES "farmers"("id"),
  "action" text NOT NULL,
  "target_type" text NOT NULL,
  "target_id" uuid NOT NULL,
  "before_json" text,
  "after_json" text,
  "created_at" timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_audit_log_target" ON "audit_log"("target_type", "target_id");
CREATE INDEX IF NOT EXISTS "idx_audit_log_created_at" ON "audit_log"("created_at");
