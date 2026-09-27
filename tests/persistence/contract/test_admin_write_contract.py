"""Parity contract suite for the Module 50 admin write methods.

Mirrors ``test_contract.py``'s ``store`` fixture pattern exactly: SQLite
always runs (in-memory), Supabase is skipped cleanly when
``SUPABASE_URL``/``SUPABASE_KEY`` are not set or the project is
unreachable.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

from agro_mirai.persistence.models import AuditLogEntry, BugReport, Farmer, Field_
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture(params=["sqlite", "supabase"])
def store(request):
    backend = request.param
    if backend == "sqlite":
        s = SQLiteDataStore(":memory:")
        yield s
        s.close()
        return

    # backend == "supabase"
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        pytest.skip("SUPABASE_URL/SUPABASE_KEY not set — skipping Supabase parity tests")
    from agro_mirai.persistence.supabase_store import SupabaseDataStore

    s = SupabaseDataStore()
    if not s.ping():
        pytest.skip("Supabase project unreachable (may be auto-paused) — skipping")
    yield s


class TestAdminWriteContract:
    def test_delete_farmer_cascades(self, store):
        farmer = Farmer(
            id=_new_uuid(), created_at=_now(), updated_at=_now(),
            name="A", preferred_language="en",
        )
        store.save_farmer(farmer)
        field = Field_(
            id=_new_uuid(), farmer_id=farmer.id, created_at=_now(), updated_at=_now(),
            name="Plot", latitude=1.0, longitude=1.0, area_ha=1.0,
        )
        store.save_field(farmer.id, field)

        assert store.delete_farmer(farmer.id) is True
        assert store.get_farmer(farmer.id) is None
        assert store.get_field_by_id(field.id) is None

    def test_delete_farmer_missing_returns_false(self, store):
        assert store.delete_farmer(_new_uuid()) is False

    def test_get_field_by_id_missing_returns_none(self, store):
        assert store.get_field_by_id(_new_uuid()) is None

    def test_bug_report_status_and_audit_log_roundtrip(self, store):
        farmer = Farmer(
            id=_new_uuid(), created_at=_now(), updated_at=_now(),
            name="B", preferred_language="en",
        )
        store.save_farmer(farmer)
        bug_report_id = _new_uuid()
        store.save_bug_report(
            farmer.id,
            BugReport(id=bug_report_id, farmer_id=farmer.id, created_at=_now()),
        )

        assert any(r.id == bug_report_id for r in store.list_all_bug_reports())
        fetched = store.get_bug_report_by_id(bug_report_id)
        assert fetched is not None
        assert fetched.status == "open"

        updated = store.update_bug_report_status(bug_report_id, "resolved")
        assert updated is not None
        assert updated.status == "resolved"
        assert store.get_bug_report_by_id(bug_report_id).status == "resolved"

        entry = AuditLogEntry(
            id=_new_uuid(), admin_farmer_id=farmer.id, action="test.action",
            target_type="bug_report", target_id=bug_report_id, created_at=_now(),
        )
        store.save_audit_log_entry(entry)
        rows = store.list_audit_log()
        assert any(r.id == entry.id for r in rows)

        assert store.delete_bug_report_by_id(bug_report_id) is True
        assert store.get_bug_report_by_id(bug_report_id) is None
        assert store.delete_bug_report_by_id(bug_report_id) is False

        # No cleanup delete_farmer here: audit_log.admin_farmer_id is a plain
        # REFERENCES farmers(id) with no ON DELETE CASCADE (migrations/sqlite/
        # 010_admin_write_actions.sql), and list_audit_log exposes no delete —
        # deleting the farmer here would raise a FK IntegrityError. The farmer
        # row is left behind in this in-memory/isolated test store.

    def test_update_bug_report_status_missing_returns_none(self, store):
        assert store.update_bug_report_status(_new_uuid(), "resolved") is None

    def test_delete_bug_report_missing_returns_false(self, store):
        assert store.delete_bug_report_by_id(_new_uuid()) is False
