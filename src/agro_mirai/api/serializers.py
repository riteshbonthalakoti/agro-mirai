"""Dataclass -> JSON dict helpers matching ``specs/core/schema.yaml``'s
``date-time``/``date`` string formats.
"""
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


def drop_unset_source(data: dict) -> dict:
    """AI cascade restructure: ``Advisory.source``/``CropRecommendation.source``/
    ``DiseaseRiskAlert.source`` are additive optional fields, and
    ``specs/core/enums.md`` documents them as ABSENT (not JSON ``null``)
    on any record predating the field -- the same convention
    ``disease_alert_source`` already established. ``to_json`` itself isn't
    changed (it's shared by every entity in the API; dropping every
    ``None``-valued key everywhere would be a much bigger behavior change
    than this one field needs), so callers that serialize one of these
    three entities pass the result through this first."""
    if data.get("source") is None:
        data.pop("source", None)
    return data


def farmer_to_public_json(farmer) -> dict:
    """Module 19: like to_json, but drops password_hash. Every /v2 route
    that returns a Farmer uses this, never the raw to_json, so a hash
    can't leak into a response by accident."""
    data = to_json(farmer)
    data.pop("password_hash", None)
    return data
