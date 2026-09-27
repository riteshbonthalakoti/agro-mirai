-- Module 50: admin dashboard v2 (Phase 1). Additive-only (hard rule 2):
-- a new "status" column on bug_reports (ALTER TABLE ADD COLUMN has no
-- IF NOT EXISTS in SQLite, applied statement-by-statement and tolerated
-- if already present -- same pattern as 002_auth_fields.sql) and a
-- brand new audit_log table.
ALTER TABLE "bug_reports" ADD COLUMN "status" TEXT NOT NULL DEFAULT 'open';

CREATE TABLE IF NOT EXISTS "audit_log" (
  "id" TEXT NOT NULL,
  "admin_farmer_id" TEXT NOT NULL REFERENCES "farmers"("id"),
  "action" TEXT NOT NULL,
  "target_type" TEXT NOT NULL,
  "target_id" TEXT NOT NULL,
  "before_json" TEXT,
  "after_json" TEXT,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "idx_audit_log_target" ON "audit_log"("target_type", "target_id");
CREATE INDEX IF NOT EXISTS "idx_audit_log_created_at" ON "audit_log"("created_at");
