"""A dedicated Flask-Limiter instance for ``/v2/auth/request-otp`` only
(Module 27; module kept at this filename to avoid an unrelated import
churn across the codebase — the limiter itself is OTP-specific, not
login-specific, see ``otp_request_limiter``'s use in ``routes/auth_v2.py``).

Kept separate from the general per-API-key limiter in ``app.py``
(Module 16) because Flask-Limiter's ``.limit()`` decorator must be
applied to the view function *before* it is registered on a Flask app
(decorating an already-registered ``app.view_functions[...]`` entry
afterward is a documented no-op in this version) — so the decorator has
to live at import time in ``routes/auth_v2.py``, independent of any one
``Flask`` instance. ``otp_request_limiter.init_app(app)`` is called once
per app in ``create_app`` (see ``app.py``); re-initialising a
module-level ``Limiter`` against a fresh app for each test does not leak
rate-limit state between apps (verified: two ``create_app()`` calls each
get their own 429 threshold).

Rate-limiting OTP requests (not just login attempts) matters here
specifically because each request-otp call generates and "sends" (logs)
a real code — without a limit, an attacker could spam a phone number
with OTPs or brute-force-probe which phone numbers exist.
"""
from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

otp_request_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
