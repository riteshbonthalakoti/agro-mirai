-- Module: Row-Level Security for all application tables.
-- Every table is locked down to the owning farmer via auth.uid().
-- Tables without a direct farmer_id column use a sub-select through fields.
-- audit_log is service_role-only (admin write path never goes through the
-- mobile client; it is reached only by the backend service account).

-- ─── farmers ────────────────────────────────────────────────────────────────
ALTER TABLE "farmers" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "farmers_farmer_isolation" ON "farmers"
  FOR ALL USING (id = auth.uid());

-- ─── fields ─────────────────────────────────────────────────────────────────
ALTER TABLE "fields" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "fields_farmer_isolation" ON "fields"
  FOR ALL USING (farmer_id = auth.uid());

-- ─── conversations ───────────────────────────────────────────────────────────
ALTER TABLE "conversations" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "conversations_farmer_isolation" ON "conversations"
  FOR ALL USING (farmer_id = auth.uid());

-- ─── advisories (linked via field_id → fields.farmer_id) ────────────────────
ALTER TABLE "advisories" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "advisories_farmer_isolation" ON "advisories"
  FOR ALL USING (
    field_id IN (
      SELECT id FROM fields WHERE farmer_id = auth.uid()
    )
  );

-- ─── crop_recommendations (linked via field_id → fields.farmer_id) ──────────
ALTER TABLE "crop_recommendations" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "crop_recommendations_farmer_isolation" ON "crop_recommendations"
  FOR ALL USING (
    field_id IN (
      SELECT id FROM fields WHERE farmer_id = auth.uid()
    )
  );

-- ─── disease_risk_alerts (linked via field_id → fields.farmer_id) ───────────
ALTER TABLE "disease_risk_alerts" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "disease_risk_alerts_farmer_isolation" ON "disease_risk_alerts"
  FOR ALL USING (
    field_id IN (
      SELECT id FROM fields WHERE farmer_id = auth.uid()
    )
  );

-- ─── irrigation_advices (linked via field_id → fields.farmer_id) ────────────
ALTER TABLE "irrigation_advices" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "irrigation_advices_farmer_isolation" ON "irrigation_advices"
  FOR ALL USING (
    field_id IN (
      SELECT id FROM fields WHERE farmer_id = auth.uid()
    )
  );

-- ─── feedback_entries ───────────────────────────────────────────────────────
ALTER TABLE "feedback_entries" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "feedback_entries_farmer_isolation" ON "feedback_entries"
  FOR ALL USING (farmer_id = auth.uid());

-- ─── bug_reports ────────────────────────────────────────────────────────────
-- Bug reports are submitted by farmers but reviewed by admins.
-- Farmers can submit/read their own; service_role covers admin reads.
ALTER TABLE "bug_reports" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "bug_reports_farmer_isolation" ON "bug_reports"
  FOR ALL USING (farmer_id = auth.uid());

CREATE POLICY "bug_reports_service_only" ON "bug_reports"
  FOR ALL USING (auth.role() = 'service_role');

-- ─── audit_log (admin/service only — no farmer_id column) ───────────────────
ALTER TABLE "audit_log" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_log_service_only" ON "audit_log"
  FOR ALL USING (auth.role() = 'service_role');
