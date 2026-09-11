"""Dataclass -> JSON dict helpers matching ``specs/core/schema.yaml``'s
``date-time``/``date`` string formats.
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime


def _fmt(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def to_json(record) -> dict:
    data = dataclasses.asdict(record)
    return {k: _fmt(v) for k, v in data.items()}


def farmer_to_public_json(farmer) -> dict:
    """Module 19: like to_json, but strips any auth-material fields.
    Module 26 removed password_hash from Farmer entirely (Supabase Auth
    owns credentials now), but every /v2 route that returns a Farmer
    still goes through this helper rather than raw to_json, so a future
    auth-related field added to Farmer doesn't leak by default."""
    return to_json(farmer)
