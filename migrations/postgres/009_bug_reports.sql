-- Module: mobile bug-report flow. Additive-only (hard rule 2): a brand
-- new table, no change to any existing table/column -- mirrors
-- migrations/sqlite/009_bug_reports.sql. Not reusing feedback_entries;
-- see that file's header comment for why.
CREATE TABLE IF NOT EXISTS bug_reports (
  id text PRIMARY KEY,
  farmer_id text NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL,
  category text,
  message text,
  photo_url text,
  app_version text,
  platform text
);

CREATE INDEX IF NOT EXISTS idx_bug_reports_farmer_id ON bug_reports(farmer_id);
