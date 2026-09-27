from __future__ import annotations

from datetime import datetime, timezone

from agro_mirai.persistence.models import AuditLogEntry, BugReport, Farmer, Field_
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _farmer(id_="f1"):
    return Farmer(id=id_, created_at=datetime.now(timezone.utc),
                  updated_at=datetime.now(timezone.utc), name="A",
                  preferred_language="en")


def test_delete_farmer_cascades_fields_and_bug_reports():
    store = SQLiteDataStore(":memory:")
    store.save_farmer(_farmer())
    store.save_field("f1", Field_(id="fl1", farmer_id="f1",
                                   created_at=datetime.now(timezone.utc),
                                   updated_at=datetime.now(timezone.utc),
                                   name="Plot", latitude=1.0, longitude=1.0, area_ha=1.0))
    store.save_bug_report("f1", BugReport(id="b1", farmer_id="f1",
                                           created_at=datetime.now(timezone.utc)))

    assert store.delete_farmer("f1") is True
    assert store.get_farmer("f1") is None
    assert store.get_field_by_id("fl1") is None
    assert store.get_bug_report_by_id("b1") is None


def test_delete_farmer_returns_false_when_not_found():
    store = SQLiteDataStore(":memory:")
    assert store.delete_farmer("nope") is False


def test_get_field_by_id_unscoped():
    store = SQLiteDataStore(":memory:")
    store.save_farmer(_farmer())
    store.save_field("f1", Field_(id="fl1", farmer_id="f1",
                                   created_at=datetime.now(timezone.utc),
                                   updated_at=datetime.now(timezone.utc),
                                   name="Plot", latitude=1.0, longitude=1.0, area_ha=1.0))
    found = store.get_field_by_id("fl1")
    assert found is not None
    assert found.farmer_id == "f1"
    assert store.get_field_by_id("missing") is None


def test_bug_report_status_lifecycle():
    store = SQLiteDataStore(":memory:")
    store.save_farmer(_farmer())
    store.save_bug_report("f1", BugReport(id="b1", farmer_id="f1",
                                           created_at=datetime.now(timezone.utc)))
    assert store.get_bug_report_by_id("b1").status == "open"

    updated = store.update_bug_report_status("b1", "resolved")
    assert updated.status == "resolved"
    assert store.get_bug_report_by_id("b1").status == "resolved"
    assert store.update_bug_report_status("missing", "resolved") is None

    assert {b.id for b in store.list_all_bug_reports()} == {"b1"}
    assert store.delete_bug_report_by_id("b1") is True
    assert store.get_bug_report_by_id("b1") is None
    assert store.delete_bug_report_by_id("b1") is False


def test_audit_log_save_and_list():
    store = SQLiteDataStore(":memory:")
    store.save_farmer(_farmer())
    entry = AuditLogEntry(id="a1", admin_farmer_id="f1", action="farmer.delete",
                           target_type="farmer", target_id="x",
                           created_at=datetime.now(timezone.utc),
                           before_json='{"id": "x"}', after_json=None)
    saved = store.save_audit_log_entry(entry)
    assert saved.id == "a1"

    rows = store.list_audit_log()
    assert len(rows) == 1
    assert rows[0].action == "farmer.delete"
    assert rows[0].before_json == '{"id": "x"}'
