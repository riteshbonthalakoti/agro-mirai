#!/usr/bin/env python3
"""Export the core Supabase tables to a timestamped local JSON file.

Manual/ad-hoc backup for the Render free-tier deployment, which has no
easy access to a scheduled cron job (see docs/BACKUPS.md for how and how
often to run this). Reads SUPABASE_URL/SUPABASE_KEY the same way
SupabaseDataStore does; run against the same credentials as the deployed
instance to back up its actual data.

    python tools/backup_supabase.py [--out-dir backups]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Every table SupabaseDataStore writes to (migrations/postgres/001_init.sql).
TABLES = (
    "farmers",
    "fields",
    "weather_readings",
    "soil_samples",
    "ndvi_readings",
    "crop_recommendations",
    "irrigation_advices",
    "disease_risk_alerts",
    "advisories",
    "feedback_entries",
)


def export_tables(client, tables=TABLES) -> dict[str, list[dict]]:
    """Fetch every row of every table via the Supabase client's PostgREST
    ``select("*")`` call. ``client`` only needs a ``.table(name).select("*")
    .execute()`` chain returning an object with a ``.data`` list — this is
    the same shape ``SupabaseDataStore`` already depends on, and a fake
    with that shape is all a test needs to provide.
    """
    return {name: client.table(name).select("*").execute().data for name in tables}


def write_backup(dump: dict, out_dir: Path, timestamp: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"agro_mirai_backup_{timestamp}.json"
    path.write_text(json.dumps(dump, indent=2, default=str))
    return path


def _build_client():
    from agro_mirai.persistence.supabase_store import SupabaseDataStore

    return SupabaseDataStore()._client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "backups")
    args = parser.parse_args(argv)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client = _build_client()
    dump = export_tables(client, tables=TABLES)
    path = write_backup(dump, args.out_dir, timestamp)

    total_rows = sum(len(rows) for rows in dump.values())
    print(f"Backed up {len(dump)} tables, {total_rows} rows, to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
