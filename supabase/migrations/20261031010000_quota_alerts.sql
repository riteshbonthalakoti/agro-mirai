-- Module 60: dedup record for the quota-near-limit email alert.
CREATE TABLE IF NOT EXISTS "quota_alerts_sent" (
  "pool" text NOT NULL,
  "alert_date" text NOT NULL,
  "sent_at" timestamptz NOT NULL,
  PRIMARY KEY ("pool", "alert_date")
);
