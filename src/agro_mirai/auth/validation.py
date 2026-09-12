"""Registration input validation.

Pure functions, no Flask/DataStore dependency. Each raises ``ValueError``
with a human-readable message on failure; callers map that to a 400
``ApiError``. ``validate_phone``/``validate_otp_code`` back Module 27's
Name+Phone+OTP auth (``api/routes/auth_v2.py``); ``validate_email``/
``validate_password_strength`` are kept for the out-of-band admin-account
path (``api/routes/admin_ui.py``), which still authenticates via
email+password since admin accounts are provisioned directly against the
DataStore, not through farmer self-registration.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# E.164-ish: optional leading '+', 7-15 digits total. Loose on purpose —
# real E.164 validation needs a country-code table this project has no
# use for yet; this just rejects obvious garbage ("abc", "1", "").
_PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
_OTP_RE = re.compile(r"^[0-9]{6}$")

MIN_PASSWORD_LENGTH = 8


def validate_email(email: str) -> None:
    if not email or not isinstance(email, str) or not _EMAIL_RE.match(email):
        raise ValueError("email must be a valid email address")


def validate_password_strength(password: str) -> None:
    """Real strength requirements, not "any non-empty string": minimum
    length plus upper/lower/digit coverage. Rejects e.g. "a", "password",
    "12345678"."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if not re.search(r"[a-z]", password):
        raise ValueError("password must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("password must contain an uppercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("password must contain a digit")


def validate_name(name: str) -> None:
    if not name or not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")


def validate_phone(phone: str) -> None:
    if not phone or not isinstance(phone, str) or not _PHONE_RE.match(phone):
        raise ValueError("phone must be a valid phone number (7-15 digits, optional leading +)")


def validate_otp_code(code: str) -> None:
    if not code or not isinstance(code, str) or not _OTP_RE.match(code):
        raise ValueError(f"otp must be a {6}-digit code")
