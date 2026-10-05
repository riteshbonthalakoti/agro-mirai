"""One-time-password auth (Module 27).

Replaces Module 19's bcrypt+email/password `/v2` auth (and the
short-lived Module 26 Supabase Auth migration, reverted) with the
simplest thing that works for a farmer with a phone and no email: enter
name + phone, get a 6-digit OTP, enter it back to log in.

Module 56: real delivery is now wired up via `agro_mirai.auth.otp_providers`
(`OtpSender` + `build_otp_sender`, selected by `OTP_PROVIDER`) -- this
module only generates, stores, and verifies the code; it has no opinion
on how the code reaches the farmer. `OtpStore.issue`'s optional `code`
argument lets a caller (the `test` provider's whitelist) force a fixed
code instead of a random one.

Storage is a single process-local in-memory dict, not a DataStore table
or Redis — acceptable because a restart invalidating in-flight OTPs is a
non-issue at this project's current (single-process, pre-production)
stage, and it avoids adding persistence-layer/schema surface for a value
that only ever needs to live for a couple of minutes. If this app is ever
run with multiple worker processes, this stops working (each worker has
its own dict) — the same documented limitation the general per-key rate
limiter already carries (see api/app.py's `_configure_rate_limit`
docstring), not a new one.
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("agro_mirai.auth.otp")

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=10)
MAX_VERIFY_ATTEMPTS = 5


MIN_RESEND = timedelta(seconds=15)
MAX_PENDING = 5000


class ResendTooSoon(Exception):
    """A code was issued for this phone a moment ago."""


@dataclass
class _PendingOtp:
    code: str
    expires_at: datetime
    attempts: int = 0
    issued_at: datetime | None = None
    #: name / language for a phone we have never seen; the account is only
    #: created once the code is verified (no accounts from unverified requests)
    signup: dict | None = None


class OtpStore:
    """Process-local, thread-safe. One pending OTP per phone number at a
    time — requesting a new one overwrites any prior pending code for
    that phone, so an old code can never be used after a fresh request."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingOtp] = {}

    def issue(
        self,
        phone: str,
        now: datetime | None = None,
        signup: dict | None = None,
        code: str | None = None,
    ) -> str:
        """Generate (or, if `code` is given, use) the pending OTP for
        `phone`. `code` is for the `test` provider's whitelisted numbers
        only -- everyone else gets a fresh random code."""
        now = now or datetime.now(timezone.utc)
        code = code if code is not None else f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"
        with self._lock:
            old = self._pending.get(phone)
            if old is not None and old.issued_at and now - old.issued_at < MIN_RESEND:
                raise ResendTooSoon()
            if len(self._pending) >= MAX_PENDING:
                # drop expired codes; if still full, the oldest ones
                for k in [k for k, v in self._pending.items() if now > v.expires_at]:
                    del self._pending[k]
                while len(self._pending) >= MAX_PENDING:
                    del self._pending[next(iter(self._pending))]
            self._pending[phone] = _PendingOtp(
                code=code, expires_at=now + OTP_TTL, issued_at=now, signup=signup
            )
        return code

    def verify(self, phone: str, code: str, now: datetime | None = None) -> bool:
        return self.verify_with_signup(phone, code, now)[0]

    def verify_with_signup(
        self, phone: str, code: str, now: datetime | None = None
    ) -> tuple[bool, dict | None]:
        """True iff `code` matches the pending OTP for `phone` and it
        hasn't expired or been guessed too many times. A correct or
        exhausted verification consumes the pending OTP (one-shot, and a
        used code can't be replayed); a wrong-but-not-yet-exhausted guess
        does not, so the farmer can retry within MAX_VERIFY_ATTEMPTS."""
        now = now or datetime.now(timezone.utc)
        with self._lock:
            pending = self._pending.get(phone)
            if pending is None:
                return False, None
            if now > pending.expires_at:
                del self._pending[phone]
                return False, None
            pending.attempts += 1
            if pending.attempts > MAX_VERIFY_ATTEMPTS:
                del self._pending[phone]
                return False, None
            if not secrets.compare_digest(pending.code, code):
                return False, None
            del self._pending[phone]
            return True, pending.signup

    def peek_all(self, now: datetime | None = None) -> list[dict]:
        """Read-only snapshot of currently-pending (not yet expired) OTPs,
        newest first. Never consumes/deletes anything, unlike verify() —
        this exists only for the admin-only debug viewer
        (api/routes/admin.py's GET /v2/admin/otps) so a developer or a
        classmate testing the app can retrieve an OTP without SMS being
        wired up, without touching the actual login flow."""
        now = now or datetime.now(timezone.utc)
        with self._lock:
            items = [
                {"phone": phone, "code": p.code, "issued_at": p.issued_at, "expires_at": p.expires_at}
                for phone, p in self._pending.items()
                if now <= p.expires_at
            ]
        items.sort(key=lambda i: i["issued_at"] or now, reverse=True)
        return items


otp_store = OtpStore()
