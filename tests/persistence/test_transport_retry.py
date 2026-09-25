"""A dropped Supabase connection must be retried even when the store method wraps
it in ConflictError (the live irrigation 500 "Server disconnected")."""
import httpx
import pytest

from agro_mirai.persistence.store import ConflictError
from agro_mirai.persistence.supabase_store import _is_transport_error, _with_transport_retry


def _dropped():
    try:
        raise httpx.RemoteProtocolError("Server disconnected")
    except httpx.RemoteProtocolError as e:
        try:
            raise ConflictError(str(e)) from e
        except ConflictError as c:
            return c


def test_transport_error_is_seen_through_conflict_error():
    assert _is_transport_error(_dropped())
    assert not _is_transport_error(ConflictError("duplicate key"))
    assert not _is_transport_error(ValueError("x"))


def test_retries_a_dropped_connection_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    calls = {"n": 0}

    @_with_transport_retry
    def save():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _dropped()
        return "saved"

    assert save() == "saved" and calls["n"] == 3


def test_a_real_conflict_is_not_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    calls = {"n": 0}

    @_with_transport_retry
    def save():
        calls["n"] += 1
        raise ConflictError("duplicate key value")

    with pytest.raises(ConflictError):
        save()
    assert calls["n"] == 1


def test_gives_up_after_three_attempts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    calls = {"n": 0}

    @_with_transport_retry
    def save():
        calls["n"] += 1
        raise _dropped()

    with pytest.raises(ConflictError):
        save()
    assert calls["n"] == 3
