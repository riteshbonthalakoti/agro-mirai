from __future__ import annotations

from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def test_bug_reports_table_has_status_column_defaulted_open():
    store = SQLiteDataStore(":memory:")
    row = store._conn.execute("PRAGMA table_info(bug_reports)").fetchall()
    columns = {r["name"]: r for r in row}
    assert "status" in columns


def test_audit_log_table_exists_with_expected_columns():
    store = SQLiteDataStore(":memory:")
    row = store._conn.execute("PRAGMA table_info(audit_log)").fetchall()
    columns = {r["name"] for r in row}
    assert columns == {
        "id", "admin_farmer_id", "action", "target_type", "target_id",
        "before_json", "after_json", "created_at",
    }
