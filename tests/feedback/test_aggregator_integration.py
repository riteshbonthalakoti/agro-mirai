"""Integration tests for FeedbackAggregator: seed SQLite, run aggregator,
verify report reflects what was seeded.

Uses the synthetic feedback seed (tests/fixtures/feedback_seed.json).
All data is synthetic — see the seed file's _note field.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agro_mirai.feedback.aggregator import FeedbackAggregator
from agro_mirai.persistence.models import Advisory, Farmer, FeedbackEntry, Field_
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

ROOT = Path(__file__).resolve().parent.parent.parent
SEED_PATH = ROOT / "tests" / "fixtures" / "feedback_seed.json"


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


@pytest.fixture
def seeded_store() -> SQLiteDataStore:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    store = SQLiteDataStore(":memory:")

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

    return store


def _get_report(store: SQLiteDataStore, farmer_id: str):
    feedback_entries = store.list_feedback_for_farmer(farmer_id)
    advisory_ids = {e.advisory_id for e in feedback_entries}
    advisory_map = {}
    for aid in advisory_ids:
        adv = store.get_advisory(farmer_id, aid)
        if adv:
            advisory_map[aid] = adv
    pairs = [(e, advisory_map[e.advisory_id]) for e in feedback_entries if e.advisory_id in advisory_map]
    return FeedbackAggregator.aggregate(pairs)


FARMER_ID = "11111111-1111-4111-8111-111111111111"


def test_report_total_entry_count(seeded_store):
    report = _get_report(seeded_store, FARMER_ID)
    assert report.total_entries == 15


def test_report_mean_rating_is_in_range(seeded_store):
    report = _get_report(seeded_store, FARMER_ID)
    assert report.mean_rating is not None
    assert 1.0 <= report.mean_rating <= 5.0


def test_report_helpful_rate_in_range(seeded_store):
    report = _get_report(seeded_store, FARMER_ID)
    assert report.helpful_rate is not None
    assert 0.0 <= report.helpful_rate <= 1.0


def test_high_severity_lower_rating_than_low(seeded_store):
    """Design property of the seed: low-severity advisories got higher ratings
    than high/severe ones — the aggregator should surface this."""
    report = _get_report(seeded_store, FARMER_ID)
    sev_map = {b.severity: b for b in report.by_severity}
    assert "low" in sev_map
    assert "high" in sev_map or "severe" in sev_map
    low_rating = sev_map["low"].mean_rating
    high_or_severe = sev_map.get("high") or sev_map.get("severe")
    assert low_rating is not None
    assert high_or_severe is not None
    assert low_rating > high_or_severe.mean_rating


def test_rating_distribution_sums_to_total(seeded_store):
    report = _get_report(seeded_store, FARMER_ID)
    assert sum(report.rating_distribution.values()) == report.total_entries


def test_by_field_contains_seeded_field(seeded_store):
    report = _get_report(seeded_store, FARMER_ID)
    field_ids = {b.field_id for b in report.by_field}
    assert "22222222-2222-4222-8222-222222222222" in field_ids


def test_empty_store_produces_zero_report():
    store = SQLiteDataStore(":memory:")
    farmer = Farmer(
        id="empty-farmer",
        name="Empty",
        preferred_language="en",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    store.save_farmer(farmer)
    report = _get_report(store, "empty-farmer")
    assert report.total_entries == 0
    assert report.mean_rating is None
    assert report.helpful_rate is None


def test_single_feedback_entry_store():
    store = SQLiteDataStore(":memory:")
    farmer_id = "single-farmer"
    farmer = Farmer(
        id=farmer_id,
        name="Single",
        preferred_language="en",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    store.save_farmer(farmer)
    field = Field_(
        id="fld-1",
        farmer_id=farmer_id,
        name="Field 1",
        latitude=13.0,
        longitude=77.0,
        area_ha=1.0,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    store.save_field(farmer_id, field)
    adv = Advisory(
        id="adv-1",
        field_id="fld-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        language="en",
        title="Single advisory",
        body="Body.",
        severity="low",
    )
    store.save_advisory(farmer_id, adv)
    entry = FeedbackEntry(
        id="fe-1",
        farmer_id=farmer_id,
        advisory_id="adv-1",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        rating=3,
        helpful=True,
    )
    store.save_feedback_entry(farmer_id, entry)
    report = _get_report(store, farmer_id)
    assert report.total_entries == 1
    assert report.mean_rating == 3.0
    assert report.helpful_rate == 1.0
