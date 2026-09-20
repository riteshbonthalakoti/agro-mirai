"""Common adapter interface for external data sources (Module 03).

Every external data source AGRO MIRAI consumes — weather, soil, NDVI —
is wrapped in an :class:`Adapter`. Downstream modules (05+) depend on
this shared shape, **never** on a raw ``requests`` call or the
``earthengine-api`` client. That keeps the source swappable and the
outputs schema-conformant.

An adapter's :meth:`Adapter.fetch` takes a :class:`FieldInput` (a
Field-shaped value; lat/long at minimum, per ``specs/core/schema.yaml``
``Field``) and returns a list of dicts, each conforming exactly to one
entity in ``schema.yaml`` (``WeatherReading`` / ``SoilSample`` /
``NDVIReading``). Field names, types, units and the timestamp format all
follow ``docs/conventions.md`` — not per-adapter judgement.

Failures are typed (:class:`AcquisitionError` and subclasses), never a
silent empty list. The one deliberate exception to "fail loudly" is the
NDVI adapter's live→cache fallback (CLAUDE.md hard rule #4), which is a
*successful* result served from a different path, not a failure.
"""
from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


# --------------------------------------------------------------------------
# Field-shaped input
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldInput:
    """The minimal slice of a ``Field`` an adapter needs.

    Mirrors ``specs/core/schema.yaml`` ``Field``: latitude/longitude are
    required (WGS84 decimal degrees); ``field_id`` is optional but, when
    present, is used to stamp ``field_id`` on returned records and as the
    primary NDVI cache key.
    """

    latitude: float
    longitude: float
    field_id: str | None = None

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"longitude out of range: {self.longitude}")

    @classmethod
    def from_field(cls, field: dict[str, Any]) -> "FieldInput":
        """Build a :class:`FieldInput` from a full ``Field`` record dict."""
        return cls(
            latitude=field["latitude"],
            longitude=field["longitude"],
            field_id=field.get("id"),
        )


# --------------------------------------------------------------------------
# Typed exceptions
# --------------------------------------------------------------------------
class AcquisitionError(Exception):
    """Base class for every adapter failure. Never raised silently."""


class SourceUnavailableError(AcquisitionError):
    """An external source could not be reached, or failed after retry.

    Carries the original exception (if any) as ``__cause__`` so callers
    can log the root cause.
    """


class SourceResponseError(AcquisitionError):
    """The source responded, but the payload could not be mapped to schema."""


# --------------------------------------------------------------------------
# Adapter interface
# --------------------------------------------------------------------------
class Adapter(abc.ABC):
    """Shared shape implemented by every data-acquisition adapter.

    Concrete adapters set the class attribute :attr:`source` to the
    ``*_source`` enum value they stamp on their records (e.g.
    ``open_meteo``), and implement :meth:`fetch`.
    """

    #: The enum value written to each record's ``source`` field.
    source: str = ""

    @abc.abstractmethod
    def fetch(self, field: FieldInput) -> list[dict[str, Any]]:
        """Return schema-conformant records for ``field``.

        Raises :class:`AcquisitionError` (or a subclass) on failure; the
        NDVI adapter is the sole exception, falling back to a local cache
        rather than raising (CLAUDE.md hard rule #4).
        """
        raise NotImplementedError


# --------------------------------------------------------------------------
# Shared helpers (id + timestamp conventions, docs/conventions.md §1, §2)
# --------------------------------------------------------------------------
def new_id() -> str:
    """A fresh UUIDv4 string in the canonical hyphenated form."""
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    """Current instant as ISO 8601 UTC, second precision, ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_from_date(date_str: str) -> str:
    """Anchor a bare ``YYYY-MM-DD`` to ``YYYY-MM-DDT00:00:00Z``.

    Open-Meteo's daily arrays and archive endpoint are date-granular; we
    anchor them at 00:00:00Z so the value is a valid ``timestamp`` per
    ``docs/conventions.md`` §2.
    """
    datetime.strptime(date_str, "%Y-%m-%d")  # validate
    return f"{date_str}T00:00:00Z"


def iso_from_minute(ts: str) -> str:
    """Normalise Open-Meteo's minute-precision ``time`` to second+``Z``.

    Open-Meteo (with ``timezone=UTC``) returns e.g. ``2026-08-25T17:45``.
    We append ``:00Z``. A value already carrying seconds/``Z`` is passed
    through after validation.
    """
    if ts.endswith("Z"):
        datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        return ts
    # minute precision "YYYY-MM-DDTHH:MM"
    datetime.strptime(ts, "%Y-%m-%dT%H:%M")
    return f"{ts}:00Z"
