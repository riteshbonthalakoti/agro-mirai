# Admin Dashboard v2 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the read-only `/v2/admin` dashboard into a production-grade, multi-tab, write-capable admin dashboard (farmer/field/bug-report CRUD, audit log, live bug-report feed), reachable at both `agromirai-admin.vercel.app` and `agromirai.vercel.app/admin/*`.

**Architecture:** Backend gains a handful of new `DataStore` methods (both SQLite and Supabase), new write routes under `/v2/admin` guarded by the existing `require_admin` decorator, an `audit_log` table logging every write, and one SSE endpoint for live bug-report updates. Frontend is a from-scratch React + Vite SPA (`web/admin`) replacing the current vanilla-JS app, built with relative asset paths so the same bundle serves correctly from either public URL.

**Tech Stack:** Flask (existing), SQLite + Supabase Postgres (existing `DataStore` implementations), React + Vite (new for `web/admin`), Server-Sent Events (native `EventSource`/Flask streaming `Response`, no new dependency).

**Spec:** [docs/superpowers/specs/2026-09-28-admin-dashboard-v2-design.md](../specs/2026-09-28-admin-dashboard-v2-design.md)

## Global Constraints

- Additive-only data contracts (hard rule 2): every schema change is a new table or a nullable/defaulted new column, via `migrations/{sqlite,postgres}/010_*.sql`.
- No module talks to a database engine directly (hard rule 3): every new operation goes through `DataStore` (`src/agro_mirai/persistence/store.py`), implemented in both `SQLiteDataStore` and `SupabaseDataStore`.
- Every `/v2/admin` write route stays behind `@require_admin` (session-cookie auth, `role == "admin"`).
- Cross-tenant/not-found behavior returns 404, never a 500 or a leaked record, matching this project's existing convention (`tests/api/test_v2_value_endpoints.py`'s pattern).
- `specs/core/openapi.yaml` must list every new path; `python tools/check_specs.py` must pass.
- Vite build for `web/admin` uses `base: "./"` (relative paths) — required for the dual-URL requirement (`agromirai-admin.vercel.app/` unprefixed, `agromirai.vercel.app/admin/*` prefixed).

## Review Focus

- **Deleting a farmer who owns fields with scans/advisories/feedback** — a reasonable admin expects the cascade to actually remove all of it, not leave orphaned rows; pinned by Task 3's cascade test.
- **PATCH/DELETE on a field or bug report id that doesn't exist** — should 404, not 500 or silently no-op; pinned in Task 4/5's route tests.
- **Two admins (or one admin double-clicking) deleting the same farmer concurrently** — the second delete should 404 cleanly (already gone), not error; pinned in Task 3's route test.
- **A bug report's `status` PATCH with an invalid value** (not one of `open/triaged/in_progress/resolved`) — should 400, not silently store garbage; pinned in Task 5.
- **The SSE stream when no new bug reports ever arrive** — must not hang the test suite or leak a connection; pinned in Task 6 by testing the generator function directly with `max_iterations`, never the live route in a blocking way.

---

## Task 1: `audit_log` table + `bug_reports.status` column (migration)

**Files:**
- Create: `migrations/sqlite/010_admin_write_actions.sql`
- Create: `migrations/postgres/010_admin_write_actions.sql`
- Modify: `src/agro_mirai/persistence/models.py` (add `AuditLogEntry`, add `status` field to `BugReport`)
- Modify: `src/agro_mirai/persistence/sqlite_store.py:1,90-108` (register new migration path + apply method)
- Test: `tests/persistence/test_admin_write_migration.py`

**Interfaces:**
- Produces: `AuditLogEntry` dataclass — `id: str`, `admin_farmer_id: str`, `action: str`, `target_type: str`, `target_id: str`, `before_json: str | None`, `after_json: str | None`, `created_at: datetime`.
- Produces: `BugReport.status: str = "open"` (new field, default preserves every existing caller).

- [ ] **Step 1: Write the failing test**

```python
# tests/persistence/test_admin_write_migration.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/persistence/test_admin_write_migration.py -v`
Expected: FAIL — `audit_log` table does not exist / `status` column missing.

- [ ] **Step 3: Write the migration files**

```sql
-- migrations/sqlite/010_admin_write_actions.sql
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
```

```sql
-- migrations/postgres/010_admin_write_actions.sql
-- Module 50: admin dashboard v2 (Phase 1). Additive-only (hard rule 2).
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
```

- [ ] **Step 4: Add `AuditLogEntry` and `BugReport.status` to models.py**

In `src/agro_mirai/persistence/models.py`, add `status: str = "open"` as the last field of the existing `BugReport` dataclass, and add a new dataclass:

```python
@dataclass
class AuditLogEntry:
    """One row per admin write action (Module 50). before_json/after_json
    are JSON-encoded snapshots of the target record, or None (before is
    None on create, after is None on delete)."""

    id: str
    admin_farmer_id: str
    action: str
    target_type: str
    target_id: str
    created_at: datetime
    before_json: str | None = None
    after_json: str | None = None
```

- [ ] **Step 5: Wire the migration into `SQLiteDataStore`**

In `src/agro_mirai/persistence/sqlite_store.py`, add near the other `*_MIGRATION_PATH` constants:

```python
ADMIN_WRITE_MIGRATION_PATH = ROOT / "migrations" / "sqlite" / "010_admin_write_actions.sql"
```

In `_apply_migration`, add after `self._apply_bug_reports_migration()`:

```python
        self._apply_admin_write_migration()
```

Add the method next to `_apply_bug_reports_migration`:

```python
    def _apply_admin_write_migration(self) -> None:
        """Module 50: ALTER TABLE ADD COLUMN (bug_reports.status) has no
        IF NOT EXISTS in SQLite, applied statement-by-statement with the
        "duplicate column name" failure tolerated -- same pattern as
        _apply_auth_migration. audit_log is CREATE TABLE IF NOT EXISTS,
        safe to re-run via executescript."""
        sql = ADMIN_WRITE_MIGRATION_PATH.read_text(encoding="utf-8")
        conn = self._conn
        for statement in sql.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise
        conn.commit()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/persistence/test_admin_write_migration.py -v`
Expected: PASS

- [ ] **Step 7: Run the full main suite to check for regressions**

Run: `PYTHONPATH=src pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice -q`
Expected: same pass count as before plus the 2 new tests, 0 new failures.

- [ ] **Step 8: Commit**

```bash
git add migrations/sqlite/010_admin_write_actions.sql migrations/postgres/010_admin_write_actions.sql src/agro_mirai/persistence/models.py src/agro_mirai/persistence/sqlite_store.py tests/persistence/test_admin_write_migration.py
git commit -m "add audit_log table and bug_reports.status column (Module 50)"
```

---

## Task 2: `DataStore` protocol additions + `SQLiteDataStore` implementation

**Files:**
- Modify: `src/agro_mirai/persistence/store.py` (add 8 new Protocol methods)
- Modify: `src/agro_mirai/persistence/sqlite_store.py` (implement all 8)
- Modify: `specs/core/repository-interface.md` (document the new admin-only unscoped methods)
- Test: `tests/persistence/test_admin_write_store.py`

**Interfaces:**
- Consumes: `AuditLogEntry`, `BugReport` (Task 1).
- Produces (all admin-only, unscoped — callers must gate behind `require_admin`, same convention as `list_all_farmers`):
  - `delete_farmer(farmer_id: str) -> bool`
  - `get_field_by_id(field_id: str) -> Field_ | None`
  - `list_all_bug_reports(limit: int = 500) -> list[BugReport]`
  - `get_bug_report_by_id(bug_report_id: str) -> BugReport | None`
  - `update_bug_report_status(bug_report_id: str, status: str) -> BugReport | None`
  - `delete_bug_report_by_id(bug_report_id: str) -> bool`
  - `save_audit_log_entry(entry: AuditLogEntry) -> AuditLogEntry`
  - `list_audit_log(limit: int = 200) -> list[AuditLogEntry]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/persistence/test_admin_write_store.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/persistence/test_admin_write_store.py -v`
Expected: FAIL — `AttributeError`, methods don't exist yet.

- [ ] **Step 3: Add the 8 methods to the `DataStore` Protocol**

In `src/agro_mirai/persistence/store.py`, add `AuditLogEntry` to the import from `agro_mirai.persistence.models`, and add after the `list_all_feedback_with_advisories` method:

```python
    def delete_farmer(self, farmer_id: str) -> bool:
        """Module 50, admin-only. Hard delete; cascades to fields/scans/
        advisories/feedback/bug_reports via each table's own FK. Returns
        False if the farmer did not exist."""
        ...

    def get_field_by_id(self, field_id: str) -> Field_ | None:
        """Module 50, admin-only, unscoped -- the admin dashboard knows a
        field's id but not always its owning farmer_id up front."""
        ...

    def list_all_bug_reports(self, limit: int = 500) -> list[BugReport]:
        """Module 50, admin-only, unscoped across every farmer."""
        ...

    def get_bug_report_by_id(self, bug_report_id: str) -> BugReport | None:
        """Module 50, admin-only, unscoped."""
        ...

    def update_bug_report_status(
        self, bug_report_id: str, status: str
    ) -> BugReport | None:
        """Module 50, admin-only. Returns the updated BugReport, or None
        if bug_report_id does not exist."""
        ...

    def delete_bug_report_by_id(self, bug_report_id: str) -> bool:
        """Module 50, admin-only. Returns False if it did not exist."""
        ...

    def save_audit_log_entry(self, entry: AuditLogEntry) -> AuditLogEntry:
        """Module 50, admin-only. Insert-only -- audit rows are never
        updated or deleted through this interface."""
        ...

    def list_audit_log(self, limit: int = 200) -> list[AuditLogEntry]:
        """Module 50, admin-only. Newest first."""
        ...
```

- [ ] **Step 4: Implement all 8 in `SQLiteDataStore`**

Add near `delete_field` in `src/agro_mirai/persistence/sqlite_store.py`:

```python
    def delete_farmer(self, farmer_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM farmers WHERE id = ?", (farmer_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_field_by_id(self, field_id: str) -> Field_ | None:
        row = self._conn.execute(
            "SELECT * FROM fields WHERE id = ?", (field_id,)
        ).fetchone()
        return self._row_to_field(row) if row else None
```

Add near `list_bug_reports_for_farmer`:

```python
    def list_all_bug_reports(self, limit: int = 500) -> list["BugReport"]:
        rows = self._conn.execute(
            "SELECT * FROM bug_reports ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_bug_report(r) for r in rows]

    def get_bug_report_by_id(self, bug_report_id: str) -> "BugReport | None":
        row = self._conn.execute(
            "SELECT * FROM bug_reports WHERE id = ?", (bug_report_id,)
        ).fetchone()
        return self._row_to_bug_report(row) if row else None

    def update_bug_report_status(self, bug_report_id: str, status: str) -> "BugReport | None":
        cur = self._conn.execute(
            "UPDATE bug_reports SET status = ? WHERE id = ?", (status, bug_report_id)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            return None
        return self.get_bug_report_by_id(bug_report_id)

    def delete_bug_report_by_id(self, bug_report_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM bug_reports WHERE id = ?", (bug_report_id,))
        self._conn.commit()
        return cur.rowcount > 0
```

Update `_row_to_bug_report` to include `status`:

```python
    @staticmethod
    def _row_to_bug_report(row: sqlite3.Row) -> "BugReport":
        keys = row.keys()
        return BugReport(
            id=row["id"],
            farmer_id=row["farmer_id"],
            created_at=_text_to_dt(row["created_at"]),
            category=row["category"],
            message=row["message"],
            photo_url=row["photo_url"],
            app_version=row["app_version"],
            platform=row["platform"],
            status=(row["status"] if "status" in keys and row["status"] else "open"),
        )
```

Add near `ping`, and import `AuditLogEntry` in the top-of-file import from `agro_mirai.persistence.models`:

```python
    def save_audit_log_entry(self, entry: AuditLogEntry) -> AuditLogEntry:
        self._conn.execute(
            """
            INSERT INTO audit_log
                (id, admin_farmer_id, action, target_type, target_id,
                 before_json, after_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id, entry.admin_farmer_id, entry.action, entry.target_type,
                entry.target_id, entry.before_json, entry.after_json,
                _dt_to_text(entry.created_at),
            ),
        )
        self._conn.commit()
        return entry

    def list_audit_log(self, limit: int = 200) -> list[AuditLogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            AuditLogEntry(
                id=r["id"], admin_farmer_id=r["admin_farmer_id"], action=r["action"],
                target_type=r["target_type"], target_id=r["target_id"],
                before_json=r["before_json"], after_json=r["after_json"],
                created_at=_text_to_dt(r["created_at"]),
            )
            for r in rows
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/persistence/test_admin_write_store.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Document the new methods in `specs/core/repository-interface.md`**

Add a short subsection (matching the doc's existing style for Module 19's admin-only methods) noting these 8 methods are admin-only and unscoped, same convention as `list_all_farmers`/`list_all_fields`.

- [ ] **Step 7: Commit**

```bash
git add src/agro_mirai/persistence/store.py src/agro_mirai/persistence/sqlite_store.py specs/core/repository-interface.md tests/persistence/test_admin_write_store.py
git commit -m "add admin write methods to DataStore + SQLiteDataStore (Module 50)"
```

---

## Task 3: `SupabaseDataStore` implementation of the same 8 methods

**Files:**
- Modify: `src/agro_mirai/persistence/supabase_store.py`
- Test: `tests/persistence/contract/test_admin_write_contract.py` (parity test, runs against both backends — follow the existing pattern in `tests/persistence/contract/`)

**Interfaces:**
- Consumes: same 8 methods from Task 2's Protocol.
- Produces: nothing new — this task only makes `SupabaseDataStore` satisfy the same contract `SQLiteDataStore` already does.

- [ ] **Step 1: Read the existing contract test file to match its fixture pattern**

Run: `cat tests/persistence/contract/test_field_contract.py` (or whichever existing contract test file is closest — inspect `tests/persistence/contract/` directory listing first with `ls tests/persistence/contract/`) and mirror its `@pytest.fixture(params=["sqlite", "supabase"])`-style parametrization (skipping Supabase when no live credentials are configured, matching that file's existing skip condition).

- [ ] **Step 2: Write the failing parity test**

```python
# tests/persistence/contract/test_admin_write_contract.py
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agro_mirai.persistence.models import AuditLogEntry, BugReport, Farmer, Field_


def test_delete_farmer_cascades(data_store):
    store = data_store
    farmer = Farmer(id="cw-f1", created_at=datetime.now(timezone.utc),
                     updated_at=datetime.now(timezone.utc), name="A",
                     preferred_language="en")
    store.save_farmer(farmer)
    store.save_field("cw-f1", Field_(id="cw-fl1", farmer_id="cw-f1",
                                      created_at=datetime.now(timezone.utc),
                                      updated_at=datetime.now(timezone.utc),
                                      name="Plot", latitude=1.0, longitude=1.0, area_ha=1.0))

    assert store.delete_farmer("cw-f1") is True
    assert store.get_farmer("cw-f1") is None
    assert store.get_field_by_id("cw-fl1") is None


def test_bug_report_status_and_audit_log_roundtrip(data_store):
    store = data_store
    farmer = Farmer(id="cw-f2", created_at=datetime.now(timezone.utc),
                     updated_at=datetime.now(timezone.utc), name="B",
                     preferred_language="en")
    store.save_farmer(farmer)
    store.save_bug_report("cw-f2", BugReport(id="cw-b1", farmer_id="cw-f2",
                                              created_at=datetime.now(timezone.utc)))
    updated = store.update_bug_report_status("cw-b1", "resolved")
    assert updated.status == "resolved"
    assert store.delete_bug_report_by_id("cw-b1") is True

    entry = AuditLogEntry(id="cw-a1", admin_farmer_id="cw-f2", action="test.action",
                           target_type="bug_report", target_id="cw-b1",
                           created_at=datetime.now(timezone.utc))
    store.save_audit_log_entry(entry)
    rows = store.list_audit_log()
    assert any(r.id == "cw-a1" for r in rows)

    # Cleanup: delete the farmer, which cascades the audit_log's own FK
    # target (admin_farmer_id) is fine to leave dangling only if the
    # schema allows it; delete audit row explicitly is not exposed, so
    # clean up by deleting the farmer last.
    store.delete_farmer("cw-f2")
```

- [ ] **Step 3: Run to verify failure on Supabase (skip if no live credentials — confirm via `echo $SUPABASE_URL` first)**

Run: `PYTHONPATH=src pytest tests/persistence/contract/test_admin_write_contract.py -v`
Expected: FAIL for the Supabase-parametrized case (SQLite case may also fail if Task 2 wasn't committed first — run after Task 2).

- [ ] **Step 4: Implement the 8 methods in `SupabaseDataStore`**

Mirror the existing `delete_field`/`get_field`/`save_bug_report` methods' style (`self._client.table(...)`) — add near `delete_field`:

```python
    def delete_farmer(self, farmer_id: str) -> bool:
        res = self._client.table("farmers").delete().eq("id", farmer_id).execute()
        return len(res.data) > 0

    def get_field_by_id(self, field_id: str) -> Field_ | None:
        res = self._client.table("fields").select("*").eq("id", field_id).execute()
        return self._row_to_field(res.data[0]) if res.data else None
```

Add near `save_bug_report`/`list_bug_reports_for_farmer` (inspect that method's exact `self._client.table("bug_reports")` call first to match column names and `_row_to_bug_report`-equivalent conversion used there):

```python
    def list_all_bug_reports(self, limit: int = 500) -> list[BugReport]:
        res = (
            self._client.table("bug_reports").select("*")
            .order("created_at", desc=True).limit(limit).execute()
        )
        return [self._row_to_bug_report(r) for r in res.data]

    def get_bug_report_by_id(self, bug_report_id: str) -> BugReport | None:
        res = self._client.table("bug_reports").select("*").eq("id", bug_report_id).execute()
        return self._row_to_bug_report(res.data[0]) if res.data else None

    def update_bug_report_status(self, bug_report_id: str, status: str) -> BugReport | None:
        res = (
            self._client.table("bug_reports").update({"status": status})
            .eq("id", bug_report_id).execute()
        )
        if not res.data:
            return None
        return self._row_to_bug_report(res.data[0])

    def delete_bug_report_by_id(self, bug_report_id: str) -> bool:
        res = self._client.table("bug_reports").delete().eq("id", bug_report_id).execute()
        return len(res.data) > 0
```

Add a `_row_to_bug_report` static method if one does not already exist on `SupabaseDataStore` (check first — if `save_bug_report`/`list_bug_reports_for_farmer` already convert rows inline rather than via a shared helper, add one now for reuse, matching `_row_to_field`'s existing pattern):

```python
    @staticmethod
    def _row_to_bug_report(row: dict) -> BugReport:
        return BugReport(
            id=row["id"], farmer_id=row["farmer_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            category=row.get("category"), message=row.get("message"),
            photo_url=row.get("photo_url"), app_version=row.get("app_version"),
            platform=row.get("platform"), status=row.get("status") or "open",
        )
```

Add near `ping`:

```python
    def save_audit_log_entry(self, entry: AuditLogEntry) -> AuditLogEntry:
        self._client.table("audit_log").insert({
            "id": entry.id, "admin_farmer_id": entry.admin_farmer_id,
            "action": entry.action, "target_type": entry.target_type,
            "target_id": entry.target_id, "before_json": entry.before_json,
            "after_json": entry.after_json, "created_at": entry.created_at.isoformat(),
        }).execute()
        return entry

    def list_audit_log(self, limit: int = 200) -> list[AuditLogEntry]:
        res = (
            self._client.table("audit_log").select("*")
            .order("created_at", desc=True).limit(limit).execute()
        )
        return [
            AuditLogEntry(
                id=r["id"], admin_farmer_id=r["admin_farmer_id"], action=r["action"],
                target_type=r["target_type"], target_id=r["target_id"],
                before_json=r.get("before_json"), after_json=r.get("after_json"),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in res.data
        ]
```

Add `AuditLogEntry` to the top-of-file import from `agro_mirai.persistence.models`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/persistence/contract/test_admin_write_contract.py -v`
Expected: PASS (SQLite case always; Supabase case if live credentials are configured in this environment, otherwise skipped per the existing contract-test skip condition).

- [ ] **Step 6: Commit**

```bash
git add src/agro_mirai/persistence/supabase_store.py tests/persistence/contract/test_admin_write_contract.py
git commit -m "implement admin write methods in SupabaseDataStore (Module 50)"
```

---

## Task 4: Audit-log write helper + farmer/field write routes

**Files:**
- Create: `src/agro_mirai/api/audit.py`
- Modify: `src/agro_mirai/api/routes/admin.py`
- Test: `tests/api/test_admin_write_routes.py`

**Interfaces:**
- Consumes: Task 2/3's `DataStore` methods; `g.farmer_id` from `require_admin` (session_auth.py).
- Produces: `write_audit_log(store, admin_farmer_id, action, target_type, target_id, before, after) -> None` — `before`/`after` are dataclass instances or `None`, JSON-encoded internally via `dataclasses.asdict` + `json.dumps` (reusing the existing `to_json`-style serialization for datetime/date fields, but audit rows store the raw dict as JSON text, not the API's date-string format, so use `json.dumps(dataclasses.asdict(x), default=str)`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_admin_write_routes.py
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def _admin_session(client, store, phone="+919000000090"):
    from _otp_helpers import register_and_login

    register_and_login(client, phone, name="Admin")
    admin = store.get_farmer_by_phone(phone)
    admin.role = "admin"
    store.save_farmer(admin)
    register_and_login(client, phone, name="Admin")
    return admin


def test_patch_farmer_updates_fields_and_writes_audit_log():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    resp = client.patch(f"/v2/admin/farmers/{admin.id}", json={"district": "Bellary"})
    assert resp.status_code == 200
    assert resp.get_json()["district"] == "Bellary"

    audit = store.list_audit_log()
    assert len(audit) == 1
    assert audit[0].action == "farmer.update"
    assert audit[0].target_id == admin.id


def test_patch_farmer_404_when_not_found():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _admin_session(client, store)
    resp = client.patch("/v2/admin/farmers/does-not-exist", json={"district": "X"})
    assert resp.status_code == 404


def test_delete_farmer_removes_and_audits():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000091", name="Victim")
    victim = store.get_farmer_by_phone("+919000000091")
    register_and_login(client, "+919000000090", name="Admin")

    resp = client.delete(f"/v2/admin/farmers/{victim.id}")
    assert resp.status_code == 200
    assert store.get_farmer(victim.id) is None

    audit = [a for a in store.list_audit_log() if a.action == "farmer.delete"]
    assert len(audit) == 1
    assert audit[0].target_id == victim.id
    assert audit[0].after_json is None


def test_delete_farmer_404_second_time():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000092", name="Victim2")
    victim = store.get_farmer_by_phone("+919000000092")
    register_and_login(client, "+919000000090", name="Admin")

    assert client.delete(f"/v2/admin/farmers/{victim.id}").status_code == 200
    assert client.delete(f"/v2/admin/farmers/{victim.id}").status_code == 404


def test_non_admin_gets_403_on_write_routes():
    app, client = _app_and_client()
    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000093", name="Plain")
    resp = client.patch("/v2/admin/farmers/whatever", json={"district": "X"})
    assert resp.status_code == 403


def test_patch_field_and_delete_field():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000094", name="Owner")
    field_id = client.post(
        "/v2/fields", json={"name": "Plot", "latitude": 1.0, "longitude": 1.0, "area_ha": 1.0}
    ).get_json()["id"]
    register_and_login(client, "+919000000090", name="Admin")

    resp = client.patch(f"/v2/admin/fields/{field_id}", json={"current_crop": "cotton"})
    assert resp.status_code == 200
    assert resp.get_json()["current_crop"] == "cotton"

    resp = client.delete(f"/v2/admin/fields/{field_id}")
    assert resp.status_code == 200
    assert store.get_field_by_id(field_id) is None


def test_patch_field_404_when_not_found():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _admin_session(client, store)
    resp = client.patch("/v2/admin/fields/nope", json={"current_crop": "x"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/api/test_admin_write_routes.py -v`
Expected: FAIL — 404s on unregistered routes.

- [ ] **Step 3: Write `src/agro_mirai/api/audit.py`**

```python
"""Shared audit-logging helper for every /v2/admin write route (Module
50). One place writes audit_log rows so no route can forget to; see
decisions/0017-multi-tenant-v2.md (superseded in part by this module's
own ADR) for why this dashboard is no longer read-only-only.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import datetime, timezone


def write_audit_log(store, admin_farmer_id: str, action: str, target_type: str,
                     target_id: str, before=None, after=None) -> None:
    from agro_mirai.persistence.models import AuditLogEntry

    def _snapshot(record):
        if record is None:
            return None
        return json.dumps(dataclasses.asdict(record), default=str)

    store.save_audit_log_entry(
        AuditLogEntry(
            id=str(uuid.uuid4()),
            admin_farmer_id=admin_farmer_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_json=_snapshot(before),
            after_json=_snapshot(after),
            created_at=datetime.now(timezone.utc),
        )
    )
```

- [ ] **Step 4: Add the write routes to `src/agro_mirai/api/routes/admin.py`**

Update the module docstring (it currently claims every route is read-only — that claim is now false and the test asserting it, `test_admin_routes_are_read_only_no_write_methods_registered` in `tests/api/test_admin_routes.py`, must be deleted in this step since it directly contradicts this module's purpose):

```python
"""``/v2/admin`` — Admin dashboard API (Module 19, writes added Module 50).

Every write route here (PATCH/DELETE) is behind @require_admin and logs
an audit_log row via api/audit.write_audit_log -- see
decisions/0030-admin-write-actions.md for why the original read-only
scope (decisions/0017) was superseded.
"""
```

Add imports at the top (alongside the existing ones):

```python
import dataclasses

from flask import request

from agro_mirai.api.audit import write_audit_log
from agro_mirai.api.errors import ApiError
from agro_mirai.api.serializers import to_json
```

(`ApiError`/`to_json` may already be imported under different names — check the file's current imports first and merge rather than duplicate.)

Add the new routes after `list_fields`:

```python
_FARMER_PATCHABLE = {"name", "preferred_language", "phone", "district", "state"}


@admin_bp.patch("/farmers/<farmer_id>")
@require_admin
def patch_farmer(farmer_id):
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")
    before = farmer
    body = request.get_json(silent=True) or {}
    updates = {k: v for k, v in body.items() if k in _FARMER_PATCHABLE}
    updated = dataclasses.replace(farmer, **updates)
    saved = store.save_farmer(updated)
    write_audit_log(store, g.farmer_id, "farmer.update", "farmer", farmer_id, before, saved)
    return jsonify(farmer_to_public_json(saved)), 200


@admin_bp.delete("/farmers/<farmer_id>")
@require_admin
def delete_farmer(farmer_id):
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")
    store.delete_farmer(farmer_id)
    write_audit_log(store, g.farmer_id, "farmer.delete", "farmer", farmer_id, farmer, None)
    return jsonify({"deleted": True}), 200


_FIELD_PATCHABLE = {"name", "latitude", "longitude", "area_ha", "elevation_m",
                     "soil_type", "current_crop", "sown_on"}


@admin_bp.patch("/fields/<field_id>")
@require_admin
def patch_field(field_id):
    store = current_app.extensions["data_store"]
    field = store.get_field_by_id(field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    before = field
    body = request.get_json(silent=True) or {}
    updates = {k: v for k, v in body.items() if k in _FIELD_PATCHABLE}
    updated = dataclasses.replace(field, **updates)
    saved = store.save_field(field.farmer_id, updated)
    write_audit_log(store, g.farmer_id, "field.update", "field", field_id, before, saved)
    return jsonify(to_json(saved)), 200


@admin_bp.delete("/fields/<field_id>")
@require_admin
def delete_field_admin(field_id):
    store = current_app.extensions["data_store"]
    field = store.get_field_by_id(field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    store.delete_field(field.farmer_id, field_id)
    write_audit_log(store, g.farmer_id, "field.delete", "field", field_id, field, None)
    return jsonify({"deleted": True}), 200
```

Also add `g` to the `flask` import at the top of the file (`from flask import Blueprint, current_app, g, jsonify`).

Check `src/agro_mirai/api/errors.py` for `ApiError`'s exact constructor signature before using it (it's already used elsewhere, e.g. `session_auth.py` — match that signature exactly; the example above assumes `ApiError(status_code, code, message)` per that file's usage).

- [ ] **Step 5: Delete the now-contradictory read-only invariant test**

In `tests/api/test_admin_routes.py`, delete `test_admin_routes_are_read_only_no_write_methods_registered` entirely, and replace it with:

```python
def test_admin_routes_expose_exactly_the_documented_write_methods():
    app, _ = _app_and_client()
    expected_writes = {
        "/v2/admin/farmers/<farmer_id>": {"PATCH", "DELETE"},
        "/v2/admin/fields/<field_id>": {"PATCH", "DELETE"},
        "/v2/admin/bug-reports/<bug_report_id>": {"PATCH", "DELETE"},
    }
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/v2/admin"):
            continue
        methods = rule.methods - {"HEAD", "OPTIONS"}
        if rule.rule in expected_writes:
            assert methods == expected_writes[rule.rule], rule.rule
        else:
            assert methods <= {"GET"}, f"{rule.rule} exposes unexpected methods: {methods}"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/api/test_admin_write_routes.py tests/api/test_admin_routes.py -v`
Expected: PASS

- [ ] **Step 7: Run the full main suite**

Run: `PYTHONPATH=src pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice -q`
Expected: 0 new failures.

- [ ] **Step 8: Commit**

```bash
git add src/agro_mirai/api/audit.py src/agro_mirai/api/routes/admin.py tests/api/test_admin_write_routes.py tests/api/test_admin_routes.py
git commit -m "add farmer/field write routes with audit logging (Module 50)"
```

---

## Task 5: Bug-report write routes (list, patch status, delete)

**Files:**
- Modify: `src/agro_mirai/api/routes/admin.py`
- Test: `tests/api/test_admin_write_routes.py` (append)

**Interfaces:**
- Consumes: Task 2/3's `list_all_bug_reports`, `get_bug_report_by_id`, `update_bug_report_status`, `delete_bug_report_by_id`; Task 4's `write_audit_log`.
- Produces: `GET /v2/admin/bug-reports`, `PATCH /v2/admin/bug-reports/<id>` (body `{"status": "..."}`), `DELETE /v2/admin/bug-reports/<id>`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/api/test_admin_write_routes.py

_VALID_STATUSES = {"open", "triaged", "in_progress", "resolved"}


def test_list_bug_reports():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b1", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    resp = client.get("/v2/admin/bug-reports")
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert any(i["id"] == "b1" and i["status"] == "open" for i in items)


def test_patch_bug_report_status_valid_and_invalid():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)
    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b2", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    resp = client.patch("/v2/admin/bug-reports/b2", json={"status": "resolved"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "resolved"

    resp = client.patch("/v2/admin/bug-reports/b2", json={"status": "not-a-real-status"})
    assert resp.status_code == 400

    resp = client.patch("/v2/admin/bug-reports/does-not-exist", json={"status": "resolved"})
    assert resp.status_code == 404


def test_delete_bug_report():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)
    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b3", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    assert client.delete("/v2/admin/bug-reports/b3").status_code == 200
    assert client.delete("/v2/admin/bug-reports/b3").status_code == 404
    audit = [a for a in store.list_audit_log() if a.action == "bug_report.delete"]
    assert len(audit) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/api/test_admin_write_routes.py -v -k bug_report`
Expected: FAIL — 404 on unregistered routes.

- [ ] **Step 3: Add the routes to `src/agro_mirai/api/routes/admin.py`**

```python
_VALID_BUG_REPORT_STATUSES = {"open", "triaged", "in_progress", "resolved"}


@admin_bp.get("/bug-reports")
@require_admin
def list_bug_reports_admin():
    store = current_app.extensions["data_store"]
    reports = store.list_all_bug_reports()
    return jsonify({"items": [to_json(r) for r in reports]}), 200


@admin_bp.patch("/bug-reports/<bug_report_id>")
@require_admin
def patch_bug_report(bug_report_id):
    store = current_app.extensions["data_store"]
    before = store.get_bug_report_by_id(bug_report_id)
    if before is None:
        raise ApiError(404, "NOT_FOUND", "Bug report not found")
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in _VALID_BUG_REPORT_STATUSES:
        raise ApiError(400, "INVALID_STATUS",
                        f"status must be one of {sorted(_VALID_BUG_REPORT_STATUSES)}")
    updated = store.update_bug_report_status(bug_report_id, status)
    write_audit_log(store, g.farmer_id, "bug_report.status", "bug_report",
                     bug_report_id, before, updated)
    return jsonify(to_json(updated)), 200


@admin_bp.delete("/bug-reports/<bug_report_id>")
@require_admin
def delete_bug_report_admin(bug_report_id):
    store = current_app.extensions["data_store"]
    before = store.get_bug_report_by_id(bug_report_id)
    if before is None:
        raise ApiError(404, "NOT_FOUND", "Bug report not found")
    store.delete_bug_report_by_id(bug_report_id)
    write_audit_log(store, g.farmer_id, "bug_report.delete", "bug_report",
                     bug_report_id, before, None)
    return jsonify({"deleted": True}), 200


@admin_bp.get("/audit-log")
@require_admin
def get_audit_log():
    store = current_app.extensions["data_store"]
    entries = store.list_audit_log()
    return jsonify({"items": [to_json(e) for e in entries]}), 200
```

- [ ] **Step 4: Update the route-inventory test from Task 4**

In `tests/api/test_admin_routes.py`'s `expected_writes` dict, add:

```python
        "/v2/admin/bug-reports/<bug_report_id>": {"PATCH", "DELETE"},
```

(already present from Task 4's version if written correctly — verify it matches exactly.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/api/test_admin_write_routes.py tests/api/test_admin_routes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agro_mirai/api/routes/admin.py tests/api/test_admin_write_routes.py tests/api/test_admin_routes.py
git commit -m "add bug-report write routes and audit-log read route (Module 50)"
```

---

## Task 6: SSE live bug-report stream

**Files:**
- Modify: `src/agro_mirai/api/routes/admin.py`
- Test: `tests/api/test_admin_bug_report_stream.py`

**Interfaces:**
- Consumes: `list_all_bug_reports` (Task 2/3).
- Produces: `_bug_report_events(store, poll_interval=2.0, max_iterations=None)` — a generator, unit-testable directly without going through the live route; `GET /v2/admin/stream/bug-reports` — SSE route wrapping it.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_admin_bug_report_stream.py
from __future__ import annotations

from datetime import datetime, timezone

from agro_mirai.api.routes.admin import _bug_report_events
from agro_mirai.persistence.models import BugReport, Farmer
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def test_bug_report_events_yields_new_reports_only():
    store = SQLiteDataStore(":memory:")
    store.save_farmer(Farmer(id="f1", created_at=datetime.now(timezone.utc),
                              updated_at=datetime.now(timezone.utc), name="A",
                              preferred_language="en"))
    store.save_bug_report("f1", BugReport(id="b1", farmer_id="f1",
                                           created_at=datetime.now(timezone.utc)))

    gen = _bug_report_events(store, poll_interval=0, max_iterations=1)
    first_batch = list(gen)
    assert len(first_batch) == 1
    assert "b1" in first_batch[0]

    store.save_bug_report("f1", BugReport(id="b2", farmer_id="f1",
                                           created_at=datetime.now(timezone.utc)))
    gen2 = _bug_report_events(store, poll_interval=0, max_iterations=1, seen_ids={"b1"})
    second_batch = list(gen2)
    assert len(second_batch) == 1
    assert "b2" in second_batch[0]
    assert "b1" not in second_batch[0]


def test_stream_route_returns_event_stream_content_type():
    from agro_mirai.api.app import create_app
    from _otp_helpers import register_and_login

    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    client = app.test_client()
    register_and_login(client, "+919000000099", name="Admin")
    admin = store.get_farmer_by_phone("+919000000099")
    admin.role = "admin"
    store.save_farmer(admin)
    register_and_login(client, "+919000000099", name="Admin")

    resp = client.get("/v2/admin/stream/bug-reports",
                       headers={"Accept": "text/event-stream"})
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    resp.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src pytest tests/api/test_admin_bug_report_stream.py -v`
Expected: FAIL — `ImportError: cannot import name '_bug_report_events'`.

- [ ] **Step 3: Implement the generator and route**

Add to `src/agro_mirai/api/routes/admin.py`:

```python
import json
import time

from flask import Response


def _bug_report_events(store, poll_interval: float = 2.0, max_iterations: int | None = None,
                        seen_ids: set | None = None):
    """Yields SSE-formatted strings, one per newly-seen bug report, by
    polling list_all_bug_reports and diffing against ids already seen.
    Kept separate from the Flask route so it can be unit-tested directly
    without a real streaming HTTP connection or a real sleep."""
    seen = set(seen_ids) if seen_ids else set()
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        for report in store.list_all_bug_reports():
            if report.id not in seen:
                seen.add(report.id)
                yield f"data: {json.dumps(to_json(report))}\n\n"
        iterations += 1
        if max_iterations is None or iterations < max_iterations:
            time.sleep(poll_interval)


@admin_bp.get("/stream/bug-reports")
@require_admin
def stream_bug_reports():
    store = current_app.extensions["data_store"]
    # Seed "seen" with every bug report that already exists, so a client
    # opening the stream doesn't get flooded with history -- only truly
    # new reports are pushed from here on.
    seen = {r.id for r in store.list_all_bug_reports()}
    return Response(
        _bug_report_events(store, poll_interval=3.0, seen_ids=seen),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/api/test_admin_bug_report_stream.py -v`
Expected: PASS

- [ ] **Step 5: Run the full main suite**

Run: `PYTHONPATH=src pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice -q`
Expected: 0 new failures.

- [ ] **Step 6: Commit**

```bash
git add src/agro_mirai/api/routes/admin.py tests/api/test_admin_bug_report_stream.py
git commit -m "add SSE live bug-report stream (Module 50)"
```

---

## Task 7: `specs/core/openapi.yaml` + `check_specs.py` + ADR

**Files:**
- Modify: `specs/core/openapi.yaml`
- Create: `decisions/0030-admin-write-actions.md`
- Modify: `decisions/0017-multi-tenant-v2.md` (mark the read-only section superseded, same pattern Module 26 used on ADR 0022)

**Interfaces:**
- Consumes: nothing new — this task documents Tasks 4-6's routes.
- Produces: nothing consumed by later tasks — purely documentation + spec-validation.

- [ ] **Step 1: Add the new paths to `specs/core/openapi.yaml`**

Open `specs/core/openapi.yaml` and find the existing `/v2/admin/farmers` and `/v2/admin/fields` path entries (GET-only today). Add sibling entries for:
- `PATCH`/`DELETE` on `/v2/admin/farmers/{farmerId}`
- `PATCH`/`DELETE` on `/v2/admin/fields/{fieldId}`
- `GET`/`PATCH`/`DELETE` on `/v2/admin/bug-reports` and `/v2/admin/bug-reports/{bugReportId}`
- `GET` on `/v2/admin/audit-log`
- `GET` on `/v2/admin/stream/bug-reports`

Match the existing document's schema-reference style exactly (look at how `/v2/fields/{fieldId}` — the farmer-facing PATCH added in Module 23 — is documented, and mirror that structure for request/response bodies).

- [ ] **Step 2: Run the spec validator**

Run: `python tools/check_specs.py`
Expected: PASS (or a specific, fixable error naming exactly what's missing — fix and re-run until it passes).

- [ ] **Step 3: Write `decisions/0030-admin-write-actions.md`**

Document: why the dashboard moved from read-only (ADR 0017) to write-capable (Ritesh's explicit request, Module 50), the audit-log design, the type-to-confirm-on-delete UX decision (frontend-enforced, server-side backstop is the 404-on-missing behavior plus the audit trail — there is deliberately no server-side "confirm token" requirement, since the session-authenticated `require_admin` gate is already the real access control), and the known limitation (single shared admin account, still no per-admin attribution beyond the one account, per Module 49's open item).

- [ ] **Step 4: Update `decisions/0017-multi-tenant-v2.md`**

Add a note near its read-only-scope section: "Superseded in part by `decisions/0030-admin-write-actions.md` (Module 50) — the admin dashboard gained write actions; the multi-tenant data model and session-auth design in this ADR are otherwise unchanged."

- [ ] **Step 5: Commit**

```bash
git add specs/core/openapi.yaml decisions/0030-admin-write-actions.md decisions/0017-multi-tenant-v2.md
git commit -m "document admin write actions in openapi.yaml and a new ADR (Module 50)"
```

---

## Task 8: React + Vite scaffold for `web/admin` (shell, auth, Overview tab)

**Files:**
- Create: `web/admin/package.json`, `web/admin/vite.config.js`, `web/admin/index.html`, `web/admin/src/main.jsx`, `web/admin/src/App.jsx`, `web/admin/src/api.js`, `web/admin/src/theme.css`
- Delete: `web/admin/admin.js`, `web/admin/style.css`, `web/admin/dev-server.mjs` (superseded by Vite's own dev server)
- Modify: `web/admin/vercel.json` (add SPA fallback rewrite so client-side routes don't 404 on refresh)

**Interfaces:**
- Produces: an `apiFetch(path, opts)` helper in `src/api.js` (same-origin `fetch` with `credentials: "same-origin"`, throwing on non-2xx, matching the old `admin.js`'s `api()` helper's contract) used by every later tab.

- [ ] **Step 1: Scaffold the Vite project**

```bash
cd "web/admin"
npm create vite@latest . -- --template react
```

When prompted about the non-empty directory, proceed (existing files will be overwritten/removed per this task's file list above).

- [ ] **Step 2: Set `base: "./"` in `vite.config.js`**

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: './',
  plugins: [react()],
})
```

- [ ] **Step 3: Write `src/api.js`**

```js
// Same-origin fetch helper, credentials included so the session cookie
// (set by the Flask backend via either public URL's rewrite) is sent.
export class UnauthorizedError extends Error {}

export async function apiFetch(path, opts = {}) {
  const res = await fetch(path, { ...opts, credentials: 'same-origin' })
  if (res.status === 401) throw new UnauthorizedError('unauthorized')
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.error?.message || `${path} returned ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const login = (email, password) =>
  fetch('/admin/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ email, password }),
  })

export const logout = () =>
  fetch('/admin/logout', { method: 'POST', credentials: 'same-origin' })
```

- [ ] **Step 4: Write `src/theme.css`** (glassmorphism over the app's existing green/leaf palette — read `web/landing/index.html`'s `<style>` block first to pull the exact green hex values already used, so the admin dashboard visually matches the rest of the product rather than inventing a new palette)

```css
:root {
  --glass-bg: rgba(255, 255, 255, 0.55);
  --glass-border: rgba(255, 255, 255, 0.35);
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  min-height: 100vh;
}

.glass-panel {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 1.5rem;
}

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.tabs button {
  padding: 0.6rem 1.2rem;
  border-radius: 12px;
  border: 1px solid var(--glass-border);
  background: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  font-weight: 600;
}

.tabs button.active {
  background: #2e7d32;
  color: white;
}
```

- [ ] **Step 5: Write `src/App.jsx`** (shell with login gate + tab nav; Overview tab only in this task, other tabs stubbed and filled in Tasks 9-10)

```jsx
import { useEffect, useState } from 'react'
import { apiFetch, login, logout, UnauthorizedError } from './api'
import './theme.css'

const TABS = ['overview', 'farmers', 'fields', 'bug-reports', 'feedback', 'audit-log']

function LoginForm({ onLoggedIn }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    const res = await login(email, password)
    if (res.redirected || res.ok) onLoggedIn()
    else setError('Invalid email or password')
  }

  return (
    <form onSubmit={submit} className="glass-panel" style={{ maxWidth: 360, margin: '4rem auto' }}>
      <h2>Admin sign in</h2>
      {error && <p style={{ color: 'crimson' }}>{error}</p>}
      <input type="email" placeholder="Email" value={email}
             onChange={(e) => setEmail(e.target.value)} required />
      <input type="password" placeholder="Password" value={password}
             onChange={(e) => setPassword(e.target.value)} required />
      <button type="submit">Log in</button>
    </form>
  )
}

function Overview() {
  const [data, setData] = useState(null)
  useEffect(() => {
    Promise.all([apiFetch('/v2/admin/farmers'), apiFetch('/v2/admin/fields')])
      .then(([farmers, fields]) => setData({ farmers: farmers.items, fields: fields.items }))
  }, [])
  if (!data) return <p>Loading…</p>
  return (
    <div className="glass-panel">
      <h3>Overview</h3>
      <p>Farmers: {data.farmers.length} · Fields: {data.fields.length}</p>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(null)
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    apiFetch('/v2/admin/farmers').then(() => setAuthed(true))
      .catch((e) => setAuthed(e instanceof UnauthorizedError ? false : false))
  }, [])

  if (authed === null) return <p>Loading…</p>
  if (!authed) return <LoginForm onLoggedIn={() => setAuthed(true)} />

  return (
    <div style={{ padding: '2rem', maxWidth: 1100, margin: '0 auto' }}>
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
        <button onClick={() => logout().then(() => setAuthed(false))}>Log out</button>
      </div>
      {tab === 'overview' && <Overview />}
      {tab !== 'overview' && <p className="glass-panel">Coming in the next task.</p>}
    </div>
  )
}
```

- [ ] **Step 6: Write `src/main.jsx`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 7: Add SPA-fallback rewrite to `web/admin/vercel.json`**

```json
{
  "rewrites": [
    { "source": "/admin/:path*", "destination": "https://agro-mirai.onrender.com/admin/:path*" },
    { "source": "/v2/:path*", "destination": "https://agro-mirai.onrender.com/v2/:path*" },
    { "source": "/health", "destination": "https://agro-mirai.onrender.com/health" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

(The catch-all must stay last — Vercel matches rewrites in order, and the backend proxies above must win for `/admin/*`, `/v2/*`, `/health` before the SPA fallback catches everything else.)

- [ ] **Step 8: Run the dev server and verify login + Overview manually**

Run: `cd web/admin && npm run dev` (starts Vite locally; the real backend is on Render, so either point `.env.local`'s dev proxy at `agro-mirai.onrender.com` or run the local Flask server per `CLAUDE.md`'s dev-server command). Then open the Browser pane (`mcp__Claude_Browser__preview_start` with the Vite dev URL), log in with the real admin credentials, and confirm the Overview tab renders real farmer/field counts. This is this task's test cycle — there is no pytest coverage for `web/admin` (JS/React), per this project's existing convention of verifying frontend work live in a browser.

- [ ] **Step 9: Commit**

```bash
git add web/admin
git commit -m "rebuild web/admin as a React + Vite app with glassmorphism shell (Module 50)"
```

---

## Task 9: Farmers and Fields tabs (list, edit, delete with type-to-confirm)

**Files:**
- Create: `web/admin/src/tabs/Farmers.jsx`, `web/admin/src/tabs/Fields.jsx`, `web/admin/src/ConfirmDeleteModal.jsx`
- Modify: `web/admin/src/App.jsx` (wire the two tabs in)

**Interfaces:**
- Consumes: `apiFetch` (Task 8).
- Produces: `<ConfirmDeleteModal targetLabel targetId onConfirm onCancel />` — reused by Task 10's bug-reports tab too.

- [ ] **Step 1: Write `src/ConfirmDeleteModal.jsx`**

```jsx
import { useState } from 'react'

export default function ConfirmDeleteModal({ targetLabel, onConfirm, onCancel }) {
  const [typed, setTyped] = useState('')
  const matches = typed === targetLabel

  return (
    <div className="glass-panel" style={{
      position: 'fixed', top: '30%', left: '50%', transform: 'translateX(-50%)', zIndex: 10,
    }}>
      <p>Type <strong>{targetLabel}</strong> to confirm deletion. This cannot be undone.</p>
      <input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
      <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
        <button disabled={!matches} onClick={onConfirm}>Delete</button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write `src/tabs/Farmers.jsx`**

```jsx
import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import ConfirmDeleteModal from '../ConfirmDeleteModal'

export default function Farmers() {
  const [farmers, setFarmers] = useState([])
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = () => apiFetch('/v2/admin/farmers').then((r) => setFarmers(r.items))
  useEffect(() => { load() }, [])

  const save = async (farmer, patch) => {
    await apiFetch(`/v2/admin/farmers/${farmer.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    setEditing(null)
    load()
  }

  const doDelete = async (farmer) => {
    await apiFetch(`/v2/admin/farmers/${farmer.id}`, { method: 'DELETE' })
    setDeleting(null)
    load()
  }

  return (
    <div className="glass-panel">
      <h3>Farmers ({farmers.length})</h3>
      <table>
        <thead><tr><th>Name</th><th>Phone</th><th>District</th><th>Role</th><th /></tr></thead>
        <tbody>
          {farmers.map((f) => (
            <tr key={f.id}>
              <td>{f.name}</td><td>{f.phone}</td><td>{f.district || '—'}</td><td>{f.role}</td>
              <td>
                <button onClick={() => setEditing(f)}>Edit</button>
                <button onClick={() => setDeleting(f)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {editing && (
        <div className="glass-panel">
          <input defaultValue={editing.district || ''} placeholder="District"
                 onBlur={(e) => save(editing, { district: e.target.value })} />
          <button onClick={() => setEditing(null)}>Close</button>
        </div>
      )}

      {deleting && (
        <ConfirmDeleteModal
          targetLabel={deleting.name}
          onConfirm={() => doDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Write `src/tabs/Fields.jsx`** (same shape as Farmers, against `/v2/admin/fields/{id}`, editable field: `current_crop`; identical `ConfirmDeleteModal` reuse — mirror `Farmers.jsx` exactly, substituting the endpoint and displayed columns: name, farmer_id, soil_type, current_crop)

- [ ] **Step 4: Wire both tabs into `src/App.jsx`**

```jsx
import Farmers from './tabs/Farmers'
import Fields from './tabs/Fields'
// ...
      {tab === 'farmers' && <Farmers />}
      {tab === 'fields' && <Fields />}
```

(Remove the `tab !== 'overview'` catch-all fallback's coverage of these two tabs — keep it only for `bug-reports`/`feedback`/`audit-log` until Task 10 fills those in.)

- [ ] **Step 5: Verify live in the browser pane**

Log in, open Farmers, edit a district, confirm it saves and the audit log (verify via `curl -b <session cookie> https://agro-mirai.onrender.com/v2/admin/audit-log` or the Audit Log tab once Task 11 lands) records it. Try deleting a test farmer with the type-to-confirm modal; confirm the delete button stays disabled until the typed text matches exactly.

- [ ] **Step 6: Commit**

```bash
git add web/admin/src
git commit -m "add Farmers and Fields tabs with edit/delete (Module 50)"
```

---

## Task 10: Bug Reports tab with live SSE updates

**Files:**
- Create: `web/admin/src/tabs/BugReports.jsx`
- Modify: `web/admin/src/App.jsx`

**Interfaces:**
- Consumes: `apiFetch`, `ConfirmDeleteModal` (Tasks 8-9); `GET /v2/admin/bug-reports`, `PATCH`/`DELETE /v2/admin/bug-reports/{id}`, `GET /v2/admin/stream/bug-reports` (Tasks 5-6).

- [ ] **Step 1: Write `src/tabs/BugReports.jsx`**

```jsx
import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import ConfirmDeleteModal from '../ConfirmDeleteModal'

const STATUSES = ['open', 'triaged', 'in_progress', 'resolved']

export default function BugReports() {
  const [reports, setReports] = useState([])
  const [deleting, setDeleting] = useState(null)

  const load = () => apiFetch('/v2/admin/bug-reports').then((r) => setReports(r.items))
  useEffect(() => { load() }, [])

  useEffect(() => {
    const source = new EventSource('/v2/admin/stream/bug-reports')
    source.onmessage = (event) => {
      const report = JSON.parse(event.data)
      setReports((prev) => [report, ...prev.filter((r) => r.id !== report.id)])
    }
    return () => source.close()
  }, [])

  const setStatus = async (report, status) => {
    await apiFetch(`/v2/admin/bug-reports/${report.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    load()
  }

  const doDelete = async (report) => {
    await apiFetch(`/v2/admin/bug-reports/${report.id}`, { method: 'DELETE' })
    setDeleting(null)
    load()
  }

  return (
    <div className="glass-panel">
      <h3>Bug Reports ({reports.length})</h3>
      <table>
        <thead><tr><th>When</th><th>Category</th><th>Message</th><th>Status</th><th /></tr></thead>
        <tbody>
          {reports.map((r) => (
            <tr key={r.id}>
              <td>{r.created_at}</td><td>{r.category || '—'}</td><td>{r.message || '—'}</td>
              <td>
                <select value={r.status} onChange={(e) => setStatus(r, e.target.value)}>
                  {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </td>
              <td><button onClick={() => setDeleting(r)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {deleting && (
        <ConfirmDeleteModal
          targetLabel={deleting.id}
          onConfirm={() => doDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Wire into `src/App.jsx`**

```jsx
import BugReports from './tabs/BugReports'
// ...
      {tab === 'bug-reports' && <BugReports />}
```

- [ ] **Step 3: Verify live**

Submit a bug report from the mobile app (or directly via `POST /v2/bug-reports` against a logged-in farmer session, per the existing mobile bug-report flow) while the admin dashboard's Bug Reports tab is open in the browser pane; confirm it appears without a manual refresh. Change its status and confirm the dropdown persists after a reload. Delete one and confirm the type-to-confirm modal gates it.

- [ ] **Step 4: Commit**

```bash
git add web/admin/src
git commit -m "add live Bug Reports tab with SSE updates (Module 50)"
```

---

## Task 11: Feedback and Audit Log tabs (read-only, reskinned)

**Files:**
- Create: `web/admin/src/tabs/Feedback.jsx`, `web/admin/src/tabs/AuditLog.jsx`
- Modify: `web/admin/src/App.jsx`

**Interfaces:**
- Consumes: `apiFetch`; `GET /v2/admin/feedback` (existing), `GET /v2/admin/audit-log` (Task 5).

- [ ] **Step 1: Write `src/tabs/Feedback.jsx`** (renders `total_entries`, `mean_rating`, `helpful_rate` from the existing `/v2/admin/feedback` response shape — check that shape first via `curl` against the live backend or by reading `FeedbackAggregator.aggregate`'s return type, then render it in a `glass-panel`, no write actions)

- [ ] **Step 2: Write `src/tabs/AuditLog.jsx`**

```jsx
import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export default function AuditLog() {
  const [entries, setEntries] = useState([])
  useEffect(() => { apiFetch('/v2/admin/audit-log').then((r) => setEntries(r.items)) }, [])

  return (
    <div className="glass-panel">
      <h3>Audit Log ({entries.length})</h3>
      <table>
        <thead><tr><th>When</th><th>Action</th><th>Target</th></tr></thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td>{e.created_at}</td><td>{e.action}</td>
              <td>{e.target_type}:{e.target_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Wire both into `src/App.jsx`, remove the stub fallback entirely**

```jsx
      {tab === 'feedback' && <Feedback />}
      {tab === 'audit-log' && <AuditLog />}
```

- [ ] **Step 4: Verify live** — every tab now renders real data, none show the "Coming in the next task" stub.

- [ ] **Step 5: Commit**

```bash
git add web/admin/src
git commit -m "add Feedback and Audit Log tabs, complete all 6 tabs (Module 50)"
```

---

## Task 12: Dual-URL support via `web/landing/vercel.json`

**Files:**
- Create: `web/landing/vercel.json`

**Interfaces:**
- Consumes: nothing — pure infra config.
- Produces: `https://agromirai.vercel.app/admin/*` reverse-proxies to `https://agromirai-admin.vercel.app/*`.

- [ ] **Step 1: Write `web/landing/vercel.json`**

```json
{
  "redirects": [
    { "source": "/admin", "destination": "/admin/", "permanent": false }
  ],
  "rewrites": [
    { "source": "/admin/:path*", "destination": "https://agromirai-admin.vercel.app/:path*" }
  ]
}
```

- [ ] **Step 2: Deploy both projects**

```bash
cd web/admin && vercel deploy --prod --yes
cd ../landing && vercel deploy --prod --yes
```

- [ ] **Step 3: Verify live from both URLs**

```bash
curl -sI https://agromirai-admin.vercel.app/admin/login   # expect 200
curl -sI https://agromirai.vercel.app/admin                # expect 307/308 to /admin/
curl -sI https://agromirai.vercel.app/admin/login          # expect 200 (proxied through)
```

Then open both in the browser pane, log in from each, and confirm both work identically (same session backend, independent cookies per origin).

- [ ] **Step 4: Commit**

```bash
git add web/landing/vercel.json
git commit -m "proxy agromirai.vercel.app/admin/* to the admin dashboard (Module 50)"
```

---

## Task 13: Full regression pass + PROGRESS.md handoff entry

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run the full backend suite**

Run: `PYTHONPATH=src pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice -q`
Expected: all passing, count higher than before this module by the number of new tests added across Tasks 1-6.

- [ ] **Step 2: Run `check_specs.py`**

Run: `python tools/check_specs.py`
Expected: OK.

- [ ] **Step 3: Run `ruff` (non-blocking, but check for anything real)**

Run: `ruff check src tools tests`

- [ ] **Step 4: Write the Module 50 handoff entry in `PROGRESS.md`**, following this project's existing per-module entry convention (see the CLAUDE.md "Current phase" section's entries for Modules 48-49 as the template: what changed, why, test counts, live verification performed).

- [ ] **Step 5: Commit**

```bash
git add PROGRESS.md
git commit -m "document Module 50 (admin dashboard v2 Phase 1) in PROGRESS.md"
```
