from __future__ import annotations

from datetime import datetime, timezone

from agro_mirai.api.routes.admin import _bug_report_events
from agro_mirai.persistence.models import BugReport, Farmer
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def test_bug_report_events_yields_new_reports_only():
    store = SQLiteDataStore(":memory:")
    store.save_farmer(Farmer(id="f1", created_at=datetime.now(timezone.utc),
                              updated_at=datetime.now(timezone.utc), name="A",
                              preferred_language="en"))
    store.save_bug_report("f1", BugReport(id="b1", farmer_id="f1",
                                           created_at=datetime.now(timezone.utc)))

    gen = _bug_report_events(store, poll_interval=0, max_iterations=1)
    first_batch = list(gen)
    assert len(first_batch) == 1
    assert "b1" in first_batch[0]

    store.save_bug_report("f1", BugReport(id="b2", farmer_id="f1",
                                           created_at=datetime.now(timezone.utc)))
    gen2 = _bug_report_events(store, poll_interval=0, max_iterations=1, seen_ids={"b1"})
    second_batch = list(gen2)
    assert len(second_batch) == 1
    assert "b2" in second_batch[0]
    assert "b1" not in second_batch[0]


def test_stream_route_returns_event_stream_content_type():
    from agro_mirai.api.app import create_app
    from _otp_helpers import register_and_login

    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    client = app.test_client()
    register_and_login(client, "+919000000099", name="Admin")
    admin = store.get_farmer_by_phone("+919000000099")
    admin.role = "admin"
    store.save_farmer(admin)
    register_and_login(client, "+919000000099", name="Admin")

    resp = client.get("/v2/admin/stream/bug-reports",
                       headers={"Accept": "text/event-stream"})
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    resp.close()
