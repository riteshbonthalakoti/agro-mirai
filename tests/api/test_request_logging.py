"""Request-id propagation: header echoed back, and present on log records
for that request so a single request's log lines are traceable end to end.
"""
from __future__ import annotations

import logging
import re
import uuid

from conftest import _auth_headers

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_response_echoes_request_id_header(client):
    resp = client.get("/health")
    request_id = resp.headers.get("X-Request-Id")
    assert request_id is not None
    assert _UUID_RE.match(request_id)


def test_each_request_gets_a_distinct_request_id(client):
    first = client.get("/health").headers["X-Request-Id"]
    second = client.get("/health").headers["X-Request-Id"]
    assert first != second


def test_client_supplied_request_id_is_ignored_new_one_generated(client):
    # The id is server-generated per request, not trusted from the client.
    resp = client.get("/health", headers={"X-Request-Id": "not-a-real-id"})
    assert resp.headers["X-Request-Id"] != "not-a-real-id"
    assert _UUID_RE.match(resp.headers["X-Request-Id"])


def test_log_records_for_a_request_carry_its_request_id(app, client, caplog):
    with caplog.at_level(logging.INFO, logger=app.logger.name):
        resp = client.get("/farmers/me", headers=_auth_headers())
    request_id = resp.headers["X-Request-Id"]
    assert any(
        getattr(record, "request_id", None) == request_id
        for record in caplog.records
    )
