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
    """Module 19: like to_json, but drops password_hash. Every /v2 route
    that returns a Farmer uses this, never the raw to_json, so a hash
    can't leak into a response by accident."""
    data = to_json(farmer)
    data.pop("password_hash", None)
    return data
