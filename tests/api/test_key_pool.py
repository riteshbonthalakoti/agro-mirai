"""KeyPool: provider-agnostic round-robin key rotation for the AI cascade
restructure's free-tier providers. No network calls here -- this module
has none."""
from agro_mirai.api.key_pool import KeyPool


def test_no_keys_configured_returns_none(monkeypatch):
    for i in range(1, 10):
        monkeypatch.delenv(f"TESTPROV_{i}", raising=False)
    pool = KeyPool("testprov", "TESTPROV")
    assert pool.get_key() is None
    assert pool.key_count() == 0
    assert pool.all_exhausted() is True


def test_round_robins_configured_keys(monkeypatch):
    monkeypatch.setenv("TESTPROV_1", "k1")
    monkeypatch.setenv("TESTPROV_2", "k2")
    pool = KeyPool("testprov", "TESTPROV")
    assert pool.key_count() == 2
    seen = [pool.get_key() for _ in range(4)]
    assert seen == ["k1", "k2", "k1", "k2"]


def test_rate_limited_key_cools_down_and_is_skipped(monkeypatch):
    monkeypatch.setenv("TESTPROV_1", "k1")
    monkeypatch.setenv("TESTPROV_2", "k2")
    pool = KeyPool("testprov", "TESTPROV", cooldown_s=60.0)
    first = pool.get_key()
    assert first == "k1"
    pool.mark_rate_limited("k1")
    # next two calls should both land on k2 since k1 is cooling down
    assert pool.get_key() == "k2"
    assert pool.get_key() == "k2"


def test_mark_success_clears_cooldown(monkeypatch):
    monkeypatch.setenv("TESTPROV_1", "k1")
    pool = KeyPool("testprov", "TESTPROV", cooldown_s=60.0)
    pool.get_key()
    pool.mark_rate_limited("k1")
    assert pool.all_exhausted() is True
    pool.mark_success("k1")
    assert pool.all_exhausted() is False
    assert pool.get_key() == "k1"


def test_skips_unset_slots(monkeypatch):
    monkeypatch.setenv("TESTPROV_1", "k1")
    monkeypatch.delenv("TESTPROV_2", raising=False)
    monkeypatch.setenv("TESTPROV_3", "k3")
    pool = KeyPool("testprov", "TESTPROV")
    assert pool.key_count() == 2
