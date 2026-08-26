"""Regression test for the SQLite cross-thread bug.

``app.test_client()`` dispatches requests synchronously in the test's own
thread, so it never exercises the multi-threaded dispatch path that
``flask run`` (and any real WSGI server) uses. This test starts the real
app on a real werkzeug server with ``threaded=True`` and fires concurrent
HTTP requests at a route that touches ``SQLiteDataStore``, asserting none
of them 500.

Against the pre-fix ``SQLiteDataStore`` (one ``sqlite3.connect()`` reused
across threads) this reproduces:
    sqlite3.ProgrammingError: SQLite objects created in a thread can only
    be used in that same thread.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import requests
from werkzeug.serving import make_server

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import Farmer
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

API_KEY = "threaded-test-key"
FARMER_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def running_server(tmp_path):
    db_path = str(tmp_path / "threaded.db")
    store = SQLiteDataStore(db_path)
    store.save_farmer(
        Farmer(
            id=FARMER_ID,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            name="Test Farmer",
            preferred_language="en",
            phone=None,
            district=None,
            state=None,
        )
    )

    application = create_app(
        {
            "API_KEY": API_KEY,
            "FARMER_ID": FARMER_ID,
            "TESTING": True,
            "DATA_STORE": store,
            "CROP_MODEL": MagicMock(),
            "IRRIGATION_MODEL": MagicMock(),
            "DISEASE_MODEL": MagicMock(),
            "DECISION_ENGINE": MagicMock(),
        }
    )

    server = make_server("127.0.0.1", 0, application, threaded=True)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        store.close()


def test_concurrent_requests_to_threaded_server_do_not_500(running_server):
    def hit():
        resp = requests.get(
            f"{running_server}/farmers/me",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10,
        )
        return resp.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: hit(), range(20)))

    assert all(s == 200 for s in statuses), statuses
