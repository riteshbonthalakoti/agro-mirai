"""tools/backup_supabase.py: exports every core table to a timestamped
local JSON file, keyed by a fake Supabase client with the same
``.table(name).select("*").execute().data`` shape SupabaseDataStore uses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import backup_supabase


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, _cols):
        return self

    def execute(self):
        return _FakeResult(self._rows)


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables

    def table(self, name: str):
        return _FakeTable(self._tables.get(name, []))


def test_export_tables_fetches_every_table():
    client = _FakeClient({"farmers": [{"id": "f1"}], "fields": [{"id": "fd1"}]})
    dump = backup_supabase.export_tables(client, tables=("farmers", "fields"))
    assert dump == {"farmers": [{"id": "f1"}], "fields": [{"id": "fd1"}]}


def test_export_tables_covers_every_declared_table_by_default():
    seen = []

    class _RecordingClient:
        def table(self, name):
            seen.append(name)
            return _FakeTable([])

    backup_supabase.export_tables(_RecordingClient())
    assert set(seen) == set(backup_supabase.TABLES)


def test_write_backup_creates_timestamped_json_file(tmp_path):
    dump = {"farmers": [{"id": "f1", "name": "Ravi"}]}
    path = backup_supabase.write_backup(dump, tmp_path, "20260829T000000Z")

    assert path.name == "agro_mirai_backup_20260829T000000Z.json"
    assert path.parent == tmp_path
    assert json.loads(path.read_text()) == dump


def test_write_backup_creates_out_dir_if_missing(tmp_path):
    out_dir = tmp_path / "nested" / "backups"
    path = backup_supabase.write_backup({}, out_dir, "ts")
    assert path.exists()


def test_main_end_to_end_writes_backup_file(tmp_path, monkeypatch):
    fake_client = _FakeClient({"farmers": [{"id": "f1"}]})
    monkeypatch.setattr(backup_supabase, "_build_client", lambda: fake_client)
    monkeypatch.setattr(backup_supabase, "TABLES", ("farmers",))

    exit_code = backup_supabase.main(["--out-dir", str(tmp_path)])

    assert exit_code == 0
    files = list(tmp_path.glob("agro_mirai_backup_*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text()) == {"farmers": [{"id": "f1"}]}
