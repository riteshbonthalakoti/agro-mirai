"""A dedicated Flask-Limiter instance for ``/v2/auth/login`` only.

Kept separate from the general per-API-key limiter in ``app.py``
(Module 16) because Flask-Limiter's ``.limit()`` decorator must be
applied to the view function *before* it is registered on a Flask app
(decorating an already-registered ``app.view_functions[...]`` entry
afterward is a documented no-op in this version) — so the decorator has
to live at import time in ``routes/auth_v2.py``, independent of any one
``Flask`` instance. ``login_limiter.init_app(app)`` is called once per
app in ``create_app`` (see ``app.py``); re-initialising a module-level
``Limiter`` against a fresh app for each test does not leak rate-limit
state between apps (verified: two ``create_app()`` calls each get their
own 429 threshold).
"""
from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

login_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
