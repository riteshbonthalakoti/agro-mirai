"""End-to-end smoke test against a REAL deployed instance — not a local
Flask test client, unlike everything in tests/api/.

These tests only run against a URL you actually give them; there is no
"discover the deployed URL" magic and nothing here fabricates a passing
result if the deployment isn't reachable. Set:

    AGRO_MIRAI_DEPLOYED_URL=https://<your-service>.onrender.com
    AGRO_MIRAI_DEPLOYED_API_KEY=<the real API_KEY configured on that instance>

then run:

    python -m pytest tests/e2e/test_deployed_smoke.py -v

Both env vars are required — the whole module is skipped (not failed)
if either is unset, so the regular full-suite run
(`pytest --ignore=tests/voice`) never depends on network access or a
live deployment being up.

Render's free tier spins down after inactivity — the first request after
a while can take up to ~60s to cold-start (see docs/DEMO_DAY.md). The
health check below uses a longer timeout for exactly that reason.
"""
from __future__ import annotations

import os

import pytest
import requests

DEPLOYED_URL = os.environ.get("AGRO_MIRAI_DEPLOYED_URL", "").rstrip("/")
API_KEY = os.environ.get("AGRO_MIRAI_DEPLOYED_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not DEPLOYED_URL or not API_KEY,
    reason="AGRO_MIRAI_DEPLOYED_URL and AGRO_MIRAI_DEPLOYED_API_KEY must both be set "
    "to exercise the real deployed instance",
)

AUTH_HEADERS = {"Authorization": f"Bearer {API_KEY}"}
COLD_START_TIMEOUT = 90


@pytest.fixture(scope="module")
def first_field_id():
    resp = requests.get(f"{DEPLOYED_URL}/fields", headers=AUTH_HEADERS, timeout=COLD_START_TIMEOUT)
    assert resp.status_code == 200, resp.text
    fields = resp.json()["items"]
    assert len(fields) > 0, "deployed instance has no seeded fields"
    return fields[0]["id"]


def test_health_check():
    resp = requests.get(f"{DEPLOYED_URL}/health", timeout=COLD_START_TIMEOUT)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("ok", "degraded")


def test_health_check_needs_no_auth():
    resp = requests.get(f"{DEPLOYED_URL}/health", timeout=COLD_START_TIMEOUT)
    assert resp.status_code == 200


def test_auth_rejects_missing_and_wrong_key():
    resp = requests.get(f"{DEPLOYED_URL}/farmers/me", timeout=30)
    assert resp.status_code == 401

    resp = requests.get(
        f"{DEPLOYED_URL}/farmers/me",
        headers={"Authorization": "Bearer wrong-key"},
        timeout=30,
    )
    assert resp.status_code == 401


def test_authenticated_advisory_request_returns_schema_valid_data(first_field_id):
    resp = requests.get(
        f"{DEPLOYED_URL}/fields/{first_field_id}/advisories",
        headers=AUTH_HEADERS,
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) > 0, "no advisories returned for the deployed instance's first field"
    advisory = items[-1]

    for key in ("id", "field_id", "severity", "title", "body"):
        assert key in advisory, f"advisory response missing '{key}': {advisory}"
    assert advisory["severity"] in ("low", "moderate", "high", "severe")
    assert isinstance(advisory["body"], str) and advisory["body"]


def test_unknown_field_id_is_404_not_500():
    resp = requests.get(
        f"{DEPLOYED_URL}/fields/00000000-0000-0000-0000-000000000000/advisories",
        headers=AUTH_HEADERS,
        timeout=30,
    )
    assert resp.status_code == 404, resp.text


def test_feedback_submission_round_trips(first_field_id):
    advisory_resp = requests.get(
        f"{DEPLOYED_URL}/fields/{first_field_id}/advisories",
        headers=AUTH_HEADERS,
        timeout=30,
    )
    assert advisory_resp.status_code == 200, advisory_resp.text
    advisory_id = advisory_resp.json()["items"][-1]["id"]

    post_resp = requests.post(
        f"{DEPLOYED_URL}/feedback",
        headers=AUTH_HEADERS,
        json={"advisory_id": advisory_id, "rating": 5, "helpful": True, "comment": "e2e smoke test"},
        timeout=30,
    )
    assert post_resp.status_code == 201, post_resp.text
    saved = post_resp.json()
    assert saved["advisory_id"] == advisory_id
    assert saved["rating"] == 5
    assert saved["helpful"] is True
    assert "id" in saved
