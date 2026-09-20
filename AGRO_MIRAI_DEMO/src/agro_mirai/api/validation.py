"""Shared request-body validation helpers for POST/PUT routes.

Raises ``ApiError(400, "BAD_REQUEST", ...)`` on any violation so every
route returns the standard JSON error envelope instead of an unhandled
exception turning into a 500. Mirrors the constraints declared in
``specs/core/openapi.yaml`` for the relevant `*Create` schemas — kept in
this one module so route handlers stay thin.
"""
from __future__ import annotations

from datetime import date

from agro_mirai.api.errors import ApiError

SOIL_TYPES = {
    "alluvial", "black", "red", "laterite", "mountain", "desert",
    "saline", "peaty", "unknown",
}

CROP_TYPES = {
    "rice", "maize", "chickpea", "kidneybeans", "pigeonpeas", "mothbeans",
    "mungbean", "blackgram", "lentil", "pomegranate", "banana", "mango",
    "grapes", "watermelon", "muskmelon", "apple", "orange", "papaya",
    "coconut", "cotton", "jute", "coffee",
}


def _require_number(value, field: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, "BAD_REQUEST", f"{field} must be a number")
    if minimum is not None and value < minimum:
        raise ApiError(400, "BAD_REQUEST", f"{field} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ApiError(400, "BAD_REQUEST", f"{field} must be <= {maximum}")
    return value


def _require_string(value, field: str) -> str:
    if not isinstance(value, str):
        raise ApiError(400, "BAD_REQUEST", f"{field} must be a string")
    return value


def _require_enum(value, field: str, allowed: set[str]) -> str:
    _require_string(value, field)
    if value not in allowed:
        raise ApiError(400, "BAD_REQUEST", f"{field} must be one of: {', '.join(sorted(allowed))}")
    return value


def validate_field_create(body: dict) -> None:
    _require_string(body["name"], "name")
    _require_number(body["latitude"], "latitude", -90, 90)
    _require_number(body["longitude"], "longitude", -180, 180)
    _require_number(body["area_ha"], "area_ha", minimum=0)

    if "elevation_m" in body and body["elevation_m"] is not None:
        _require_number(body["elevation_m"], "elevation_m")
    if "soil_type" in body and body["soil_type"] is not None:
        _require_enum(body["soil_type"], "soil_type", SOIL_TYPES)
    if "current_crop" in body and body["current_crop"] is not None:
        _require_enum(body["current_crop"], "current_crop", CROP_TYPES)
    if body.get("sown_on"):
        _require_string(body["sown_on"], "sown_on")
        try:
            date.fromisoformat(body["sown_on"])
        except ValueError:
            raise ApiError(400, "BAD_REQUEST", "sown_on must be an ISO-8601 date (YYYY-MM-DD)")


_FIELD_UPDATE_KEYS = (
    "name", "latitude", "longitude", "area_ha", "elevation_m",
    "soil_type", "current_crop", "sown_on",
)


def validate_field_update(body: dict) -> None:
    """Module 23 (A5): partial-update validation for ``PATCH
    /v2/fields/{field_id}``. Every key is optional (that's the point of a
    partial update) but any key that *is* present must satisfy the same
    constraint ``validate_field_create`` applies to it — reuses the same
    per-field checks rather than duplicating them.
    """
    unknown = [k for k in body if k not in _FIELD_UPDATE_KEYS]
    if unknown:
        raise ApiError(400, "BAD_REQUEST", f"Unknown field(s): {', '.join(sorted(unknown))}")
    if not body:
        raise ApiError(400, "BAD_REQUEST", "Request body must include at least one field to update")

    if "name" in body:
        _require_string(body["name"], "name")
    if "latitude" in body:
        _require_number(body["latitude"], "latitude", -90, 90)
    if "longitude" in body:
        _require_number(body["longitude"], "longitude", -180, 180)
    if "area_ha" in body:
        _require_number(body["area_ha"], "area_ha", minimum=0)
    if "elevation_m" in body and body["elevation_m"] is not None:
        _require_number(body["elevation_m"], "elevation_m")
    if "soil_type" in body and body["soil_type"] is not None:
        _require_enum(body["soil_type"], "soil_type", SOIL_TYPES)
    if "current_crop" in body and body["current_crop"] is not None:
        _require_enum(body["current_crop"], "current_crop", CROP_TYPES)
    if "sown_on" in body and body["sown_on"] is not None:
        _require_string(body["sown_on"], "sown_on")
        try:
            date.fromisoformat(body["sown_on"])
        except ValueError:
            raise ApiError(400, "BAD_REQUEST", "sown_on must be an ISO-8601 date (YYYY-MM-DD)")


def validate_feedback_create(body: dict) -> None:
    rating = body["rating"]
    if isinstance(rating, bool) or not isinstance(rating, int) or not (1 <= rating <= 5):
        raise ApiError(400, "BAD_REQUEST", "rating must be an integer between 1 and 5")
    if not isinstance(body["helpful"], bool):
        raise ApiError(400, "BAD_REQUEST", "helpful must be a boolean")
    if "comment" in body and body["comment"] is not None:
        _require_string(body["comment"], "comment")
