"""Unit tests for FeedbackAggregator — pure function over known inputs."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agro_mirai.feedback.aggregator import FeedbackAggregator
from agro_mirai.persistence.models import Advisory, FeedbackEntry

_T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _entry(id: str, advisory_id: str, rating: int, helpful: bool, comment: str | None = None) -> FeedbackEntry:
    return FeedbackEntry(
        id=id,
        farmer_id="farmer-1",
        advisory_id=advisory_id,
        created_at=_T0,
        rating=rating,
        helpful=helpful,
        comment=comment,
    )


def _advisory(id: str, field_id: str, severity: str) -> Advisory:
    return Advisory(
        id=id,
        field_id=field_id,
        created_at=_T0,
        language="en",
        title="Test advisory",
        body="Test body.",
        severity=severity,
    )


# --- edge cases ---

def test_empty_input_returns_zero_report():
    report = FeedbackAggregator.aggregate([])
    assert report.total_entries == 0
    assert report.mean_rating is None
    assert report.helpful_rate is None
    assert report.by_severity == []
    assert report.by_field == []
    assert report.rating_distribution == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


def test_all_five_star():
    adv = _advisory("a1", "f1", "low")
    pairs = [(_entry(f"e{i}", "a1", 5, True), adv) for i in range(3)]
    report = FeedbackAggregator.aggregate(pairs)
    assert report.total_entries == 3
    assert report.mean_rating == 5.0
    assert report.helpful_rate == 1.0
    assert report.rating_distribution[5] == 3
    assert report.rating_distribution[1] == 0


def test_all_one_star():
    adv = _advisory("a1", "f1", "severe")
    pairs = [(_entry(f"e{i}", "a1", 1, False), adv) for i in range(4)]
    report = FeedbackAggregator.aggregate(pairs)
    assert report.total_entries == 4
    assert report.mean_rating == 1.0
    assert report.helpful_rate == 0.0
    assert report.rating_distribution[1] == 4


# --- correctness ---

def test_mean_rating_computed_correctly():
    adv = _advisory("a1", "f1", "moderate")
    # ratings 1 2 3 4 5 -> mean 3.0
    pairs = [(_entry(f"e{i}", "a1", i + 1, True), adv) for i in range(5)]
    report = FeedbackAggregator.aggregate(pairs)
    assert report.mean_rating == 3.0


def test_helpful_rate_partial():
    adv = _advisory("a1", "f1", "moderate")
    pairs = [
        (_entry("e1", "a1", 5, True), adv),
        (_entry("e2", "a1", 3, False), adv),
        (_entry("e3", "a1", 4, True), adv),
        (_entry("e4", "a1", 2, False), adv),
    ]
    report = FeedbackAggregator.aggregate(pairs)
    assert report.helpful_rate == 0.5


def test_rating_distribution_counts():
    adv = _advisory("a1", "f1", "low")
    pairs = [
        (_entry("e1", "a1", 1, False), adv),
        (_entry("e2", "a1", 3, True), adv),
        (_entry("e3", "a1", 3, True), adv),
        (_entry("e4", "a1", 5, True), adv),
    ]
    report = FeedbackAggregator.aggregate(pairs)
    assert report.rating_distribution == {1: 1, 2: 0, 3: 2, 4: 0, 5: 1}


def test_by_severity_breakdown():
    adv_low = _advisory("a1", "f1", "low")
    adv_high = _advisory("a2", "f1", "high")
    pairs = [
        (_entry("e1", "a1", 5, True), adv_low),
        (_entry("e2", "a1", 4, True), adv_low),
        (_entry("e3", "a2", 2, False), adv_high),
    ]
    report = FeedbackAggregator.aggregate(pairs)
    sev_map = {b.severity: b for b in report.by_severity}
    assert sev_map["low"].count == 2
    assert sev_map["low"].mean_rating == 4.5
    assert sev_map["low"].helpful_rate == 1.0
    assert sev_map["high"].count == 1
    assert sev_map["high"].helpful_rate == 0.0


def test_by_field_breakdown():
    adv_f1 = _advisory("a1", "f1", "low")
    adv_f2 = _advisory("a2", "f2", "moderate")
    pairs = [
        (_entry("e1", "a1", 5, True), adv_f1),
        (_entry("e2", "a2", 2, False), adv_f2),
        (_entry("e3", "a2", 3, True), adv_f2),
    ]
    report = FeedbackAggregator.aggregate(pairs)
    field_map = {b.field_id: b for b in report.by_field}
    assert field_map["f1"].count == 1
    assert field_map["f2"].count == 2


def test_single_entry():
    adv = _advisory("a1", "f1", "moderate")
    pairs = [(_entry("e1", "a1", 4, True, "Good advice"), adv)]
    report = FeedbackAggregator.aggregate(pairs)
    assert report.total_entries == 1
    assert report.mean_rating == 4.0
    assert report.helpful_rate == 1.0
