-- Module: mobile bug-report flow. Additive-only (hard rule 2): a brand
-- new table, no change to any existing table/column. Deliberately NOT
-- reusing "feedback_entries" -- that table's advisory_id/rating/helpful
-- are all NOT NULL (a per-advisory star rating), and a bug report has
-- none of those, so bending it would mean loosening an existing
-- constraint (a breaking change) rather than adding one additively.
-- Safe to re-run: CREATE TABLE/INDEX IF NOT EXISTS, same pattern as
-- 001_init.sql.
CREATE TABLE IF NOT EXISTS "bug_reports" (
  "id" TEXT NOT NULL,
  "farmer_id" TEXT NOT NULL REFERENCES "farmers"("id") ON DELETE CASCADE,
  "created_at" TEXT NOT NULL,
  "category" TEXT,
  "message" TEXT,
  "photo_url" TEXT,
  "app_version" TEXT,
  "platform" TEXT,
  PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "idx_bug_reports_farmer_id" ON "bug_reports"("farmer_id");
