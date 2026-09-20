"""A malformed id must read as "not found" on the Supabase store, as it does
on SQLite, instead of surfacing PostgREST's invalid-uuid error as a 500."""
from agro_mirai.persistence.supabase_store import SupabaseDataStore, _is_uuid


class _ExplodingClient:
    def table(self, *_):
        raise AssertionError("must not query with a malformed id")


def _store():
    store = SupabaseDataStore.__new__(SupabaseDataStore)
    store._client = _ExplodingClient()
    return store


def test_is_uuid():
    assert _is_uuid("2ee3e29a-653b-4d91-9f7a-d435ec02e672")
    assert not _is_uuid("does-not-exist")


def test_get_advisory_bad_id_is_none():
    assert _store().get_advisory("2ee3e29a-653b-4d91-9f7a-d435ec02e672", "does-not-exist") is None


def test_get_field_bad_id_is_none():
    assert _store().get_field("2ee3e29a-653b-4d91-9f7a-d435ec02e672", "nope") is None


def test_get_farmer_bad_id_is_none():
    assert _store().get_farmer("nope") is None
