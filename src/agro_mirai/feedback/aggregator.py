"""``FeedbackAggregator`` — aggregate ``FeedbackEntry`` records into summary stats.

Pure function over data the caller supplies; no ``DataStore`` calls,
no network, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from agro_mirai.persistence.models import Advisory, FeedbackEntry


@dataclass
class SeverityBucket:
    severity: str
    count: int
    mean_rating: float | None
    helpful_rate: float | None


@dataclass
class FieldBucket:
    field_id: str
    count: int
    mean_rating: float | None
    helpful_rate: float | None


@dataclass
class FeedbackReport:
    total_entries: int
    mean_rating: float | None
    helpful_rate: float | None
    rating_distribution: dict[int, int]
    by_severity: list[SeverityBucket]
    by_field: list[FieldBucket]


def _mean_or_none(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def _helpful_rate(entries: list[FeedbackEntry]) -> float | None:
    if not entries:
        return None
    return round(sum(1 for e in entries if e.helpful) / len(entries), 4)


class FeedbackAggregator:
    """Aggregate a list of ``(FeedbackEntry, Advisory)`` pairs into a report.

    The Advisory is needed for its ``severity`` and ``field_id`` dimensions.
    Pass ``advisory_map`` — a dict from ``advisory_id`` to ``Advisory`` — or
    use the convenience ``aggregate(pairs)`` class method.
    """

    @staticmethod
    def aggregate(
        pairs: Sequence[tuple[FeedbackEntry, Advisory]],
    ) -> FeedbackReport:
        if not pairs:
            return FeedbackReport(
                total_entries=0,
                mean_rating=None,
                helpful_rate=None,
                rating_distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                by_severity=[],
                by_field=[],
            )

        entries = [e for e, _ in pairs]
        advisories = {adv.id: adv for _, adv in pairs}

        # Overall
        total = len(entries)
        rating_dist: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for e in entries:
            rating_dist[e.rating] = rating_dist.get(e.rating, 0) + 1

        overall_mean = _mean_or_none([e.rating for e in entries])
        overall_helpful = _helpful_rate(entries)

        # By severity
        by_sev: dict[str, list[FeedbackEntry]] = {}
        for e in entries:
            sev = advisories.get(e.advisory_id, None)
            sev_label = sev.severity if sev else "unknown"
            by_sev.setdefault(sev_label, []).append(e)

        severity_buckets = [
            SeverityBucket(
                severity=sev,
                count=len(grp),
                mean_rating=_mean_or_none([e.rating for e in grp]),
                helpful_rate=_helpful_rate(grp),
            )
            for sev, grp in sorted(by_sev.items())
        ]

        # By field
        by_field: dict[str, list[FeedbackEntry]] = {}
        for e in entries:
            adv = advisories.get(e.advisory_id, None)
            fid = adv.field_id if adv else "unknown"
            by_field.setdefault(fid, []).append(e)

        field_buckets = [
            FieldBucket(
                field_id=fid,
                count=len(grp),
                mean_rating=_mean_or_none([e.rating for e in grp]),
                helpful_rate=_helpful_rate(grp),
            )
            for fid, grp in sorted(by_field.items())
        ]

        return FeedbackReport(
            total_entries=total,
            mean_rating=overall_mean,
            helpful_rate=overall_helpful,
            rating_distribution=rating_dist,
            by_severity=severity_buckets,
            by_field=field_buckets,
        )
