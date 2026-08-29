"""Password hashing via bcrypt.

Not a hand-rolled hash (sha256(password), etc.) — bcrypt is a real,
established KDF with a built-in per-hash salt and a tunable work factor.
See decisions/0017-multi-tenant-v2.md for why bcrypt over argon2 (both
are acceptable per the module spec; bcrypt was picked for its smaller,
dependency-free wheel and this project's scale).
"""
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Return a bcrypt hash (includes its own salt) as a str, safe to
    store in Farmer.password_hash. Never store the input `password`."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """True iff `password` matches `password_hash`. False (never raises)
    for a missing/malformed hash — e.g. a /v1-only Farmer with no
    password_hash set at all."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
