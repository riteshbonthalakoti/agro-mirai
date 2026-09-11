"""Input validation still used post-Module-26.

``validate_email``/``validate_password_strength`` were removed along with
``/v2/auth/register`` (Module 26 — registration now happens entirely
against Supabase Auth, which enforces its own password policy). Only
``validate_name`` survives: ``PATCH /v2/farmers/me`` still needs it.
"""
from __future__ import annotations


def validate_name(name: str) -> None:
    if not name or not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")
