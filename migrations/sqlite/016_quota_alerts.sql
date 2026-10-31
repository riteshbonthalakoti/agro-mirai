-- Module 60: dedup record for the quota-near-limit email alert -- at most
-- one email per pool per day, regardless of how often the sweep cron runs.
CREATE TABLE IF NOT EXISTS "quota_alerts_sent" (
  "pool" text NOT NULL,
  "alert_date" text NOT NULL,
  "sent_at" text NOT NULL,
  PRIMARY KEY ("pool", "alert_date")
);
