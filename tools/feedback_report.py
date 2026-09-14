"""CLI: run FeedbackAggregator against a SQLite DataStore and print the report as JSON.

Usage:
    python tools/feedback_report.py --db <path-to.db> --farmer-id <uuid>
    python tools/feedback_report.py --seed   # seed feedback_seed.json into :memory: and report

The --seed flag is intended for demo/testing only; it seeds synthetic data
(tests/fixtures/feedback_seed.json) into an in-memory SQLite DB and prints
the resulting report without touching any real database.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agro_mirai.feedback.aggregator import FeedbackAggregator
from agro_mirai.persistence.models import Advisory, FeedbackEntry, Farmer, Field_
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _load_seed() -> dict:
    seed_path = ROOT / "tests" / "fixtures" / "feedback_seed.json"
    with open(seed_path, encoding="utf-8") as f:
        return json.load(f)


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _seed_into_store(store: SQLiteDataStore, seed: dict) -> None:
    farmer = Farmer(
        id=seed["farmer_id"],
        name="Synthetic Farmer (seed)",
        preferred_language="en",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    store.save_farmer(farmer)

    field = Field_(
        id=seed["field_id"],
        farmer_id=seed["farmer_id"],
        name="Synthetic Field (seed)",
        latitude=13.0,
        longitude=77.0,
        area_ha=2.0,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    store.save_field(seed["farmer_id"], field)

    for a in seed["advisories"]:
        advisory = Advisory(
            id=a["id"],
            field_id=a["field_id"],
            created_at=_dt(a["created_at"]),
            language=a["language"],
            title=a["title"],
            body=a["body"],
            severity=a["severity"],
            source_refs=a.get("source_refs", []),
        )
        store.save_advisory(seed["farmer_id"], advisory)

    for fe in seed["feedback_entries"]:
        entry = FeedbackEntry(
            id=fe["id"],
            farmer_id=fe["farmer_id"],
            advisory_id=fe["advisory_id"],
            created_at=_dt(fe["created_at"]),
            rating=fe["rating"],
            helpful=bool(fe["helpful"]),
            comment=fe.get("comment"),
        )
        store.save_feedback_entry(seed["farmer_id"], entry)


def _run(store: SQLiteDataStore, farmer_id: str) -> None:
    feedback_entries = store.list_feedback_for_farmer(farmer_id)
    if not feedback_entries:
        print(json.dumps({"total_entries": 0, "message": "No feedback entries found."}, indent=2))
        return

    advisory_ids = {e.advisory_id for e in feedback_entries}
    advisory_map: dict[str, Advisory] = {}
    for aid in advisory_ids:
        adv = store.get_advisory(farmer_id, aid)
        if adv:
            advisory_map[aid] = adv

    pairs = [(e, advisory_map[e.advisory_id]) for e in feedback_entries if e.advisory_id in advisory_map]

    report = FeedbackAggregator.aggregate(pairs)

    out = {
        "total_entries": report.total_entries,
        "mean_rating": report.mean_rating,
        "helpful_rate": report.helpful_rate,
        "rating_distribution": report.rating_distribution,
        "by_severity": [
            {
                "severity": b.severity,
                "count": b.count,
                "mean_rating": b.mean_rating,
                "helpful_rate": b.helpful_rate,
            }
            for b in report.by_severity
        ],
        "by_field": [
            {
                "field_id": b.field_id,
                "count": b.count,
                "mean_rating": b.mean_rating,
                "helpful_rate": b.helpful_rate,
            }
            for b in report.by_field
        ],
    }
    print(json.dumps(out, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Print feedback aggregation report.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", action="store_true", help="Seed synthetic data and report (demo/test)")
    group.add_argument("--db", metavar="PATH", help="Path to SQLite .db file")
    parser.add_argument("--farmer-id", metavar="UUID", help="Farmer ID (required with --db)")
    args = parser.parse_args()

    if args.seed:
        store = SQLiteDataStore(":memory:")
        seed = _load_seed()
        _seed_into_store(store, seed)
        _run(store, seed["farmer_id"])
    else:
        if not args.farmer_id:
            parser.error("--farmer-id is required when using --db")
        store = SQLiteDataStore(args.db)
        _run(store, args.farmer_id)


if __name__ == "__main__":
    main()
