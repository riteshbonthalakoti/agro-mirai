"""Shared Name+Phone+OTP login helper for /v2 integration tests (Module
27). Not a pytest fixture module — plain importable functions, since the
tests that need this each build their own ``app``/``client`` with
different config (rate limits, etc.) via their own fixtures.
"""
from __future__ import annotations

from agro_mirai.auth.otp import otp_store


def register_and_login(client, phone: str, name: str = "Farmer"):
    """request-otp -> read the real code out of the process-local
    OtpStore (standing in for "read it off the server logs") ->
    verify-otp. Returns the verify-otp response."""
    resp = client.post(
        "/v2/auth/request-otp",
        json={"phone": phone, "name": name, "preferred_language": "en"},
    )
    assert resp.status_code == 200, resp.get_json()
    code = otp_store._pending[phone].code
    return client.post("/v2/auth/verify-otp", json={"phone": phone, "otp": code})
