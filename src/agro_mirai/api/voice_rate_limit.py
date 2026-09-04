"""A dedicated Flask-Limiter instance for ``/v2/advisories/{id}/audio``
and ``/v2/stt`` (Module 23). TTS/STT calls are far more expensive per
request than a JSON read or even the CNN image path (a live model call on
the Oracle VM, not just a local prediction), so Module 16's general
per-API-key limiter is not tuned for them — same reasoning as
``login_rate_limit.py``, and for the same mechanical reason: this
version's Flask-Limiter silently no-ops ``.limit(...)`` applied to a view
function *after* it's registered on a Flask app, so the decorator has to
live at import time in ``routes/voice_v2.py``, independent of any one
``Flask`` instance. ``voice_limiter.init_app(app)`` is called once per app
in ``create_app`` (see ``app.py``).
"""
from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

voice_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
