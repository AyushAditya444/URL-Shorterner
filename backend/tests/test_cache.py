from datetime import datetime, timedelta

from app.cache import cache_set_link, cache_get_link, cache_delete_link, ttl_for_expiry


def test_set_then_get_returns_target_url_and_link_id(fake_redis):
    cache_set_link(fake_redis, "abc1234", "https://example.com", link_id=7)
    assert cache_get_link(fake_redis, "abc1234") == {"target_url": "https://example.com", "link_id": 7}


def test_get_missing_code_returns_none(fake_redis):
    assert cache_get_link(fake_redis, "nope000") is None


def test_delete_removes_entry(fake_redis):
    cache_set_link(fake_redis, "abc1234", "https://example.com", link_id=7)
    cache_delete_link(fake_redis, "abc1234")
    assert cache_get_link(fake_redis, "abc1234") is None


def test_set_applies_ttl(fake_redis):
    cache_set_link(fake_redis, "abc1234", "https://example.com", link_id=7, ttl_seconds=100)
    ttl = fake_redis.ttl("short:abc1234")
    assert 0 < ttl <= 100


def test_ttl_for_expiry_returns_default_when_no_expiry():
    assert ttl_for_expiry(None, default_ttl=3600) == 3600


def test_ttl_for_expiry_clamps_to_remaining_lifetime():
    expires_at = datetime.utcnow() + timedelta(seconds=30)
    assert ttl_for_expiry(expires_at, default_ttl=3600) <= 30


def test_ttl_for_expiry_returns_zero_when_already_expired():
    expires_at = datetime.utcnow() - timedelta(seconds=1)
    assert ttl_for_expiry(expires_at, default_ttl=3600) == 0
