"""One-time-password auth (Module 27).

Replaces Module 19's bcrypt+email/password `/v2` auth (and the
short-lived Module 26 Supabase Auth migration, reverted) with the
simplest thing that works for a farmer with a phone and no email: enter
name + phone, get a 6-digit OTP, enter it back to log in.

Dev/demo posture, stated plainly (see decisions/0023-name-phone-otp-auth.md):
no SMS provider is wired up yet, so the OTP is never sent anywhere — it
is written to the server's own log output via `logging`, which is fine
for local dev/testing/a capstone demo where the person running the
server can read the code off the terminal, and is exactly the kind of
"nothing is hand-faked" honesty CLAUDE.md asks for rather than pretending
an SMS was sent. `OTP_DELIVERY=log` is the only mode today;
`send_otp(phone, code)` is the single seam a real provider (Twilio
Verify, etc.) plugs into later without touching request-otp/verify-otp's
calling code.

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

    def issue(self, phone: str, now: datetime | None = None, signup: dict | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        code = f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"
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


def send_otp(phone: str, code: str) -> None:
    """The one delivery seam. Today: server logs only (OTP_DELIVERY=log,
    the only supported mode). A real SMS provider (e.g. Twilio Verify)
    replaces this function's body later without touching callers."""
    logger.info("OTP for %s: %s (valid %d min)", phone, code, int(OTP_TTL.total_seconds() // 60))


otp_store = OtpStore()
