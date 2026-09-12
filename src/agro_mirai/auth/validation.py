"""Registration input validation — email shape and password strength.

Pure functions, no Flask/DataStore dependency. Each raises ``ValueError``
with a human-readable message on failure; ``api/routes/auth_v2.py``
catches that and maps it to a 400 ``ApiError``.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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
