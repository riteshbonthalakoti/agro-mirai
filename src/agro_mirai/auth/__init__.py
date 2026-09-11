"""Local input validation surviving Module 26's Supabase Auth migration.

``password.py`` (bcrypt hashing) was removed — Supabase Auth owns
credentials now. ``validation.py`` keeps only ``validate_name``, the one
rule ``/v2`` still checks locally (``PATCH /v2/farmers/me``).
"""
