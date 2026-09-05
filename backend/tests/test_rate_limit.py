import pytest
from fastapi import HTTPException

from app.rate_limit import check_rate_limit


def test_allows_requests_under_the_limit(fake_redis):
    for _ in range(5):
        assert check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60) is True


def test_blocks_requests_over_the_limit(fake_redis):
    for _ in range(5):
        check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60)
    assert check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60) is False


def test_different_keys_have_independent_limits(fake_redis):
    for _ in range(5):
        check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60)
    assert check_rate_limit(fake_redis, "ip:9.9.9.9:test", limit=5, window_seconds=60) is True


def test_sets_expiry_on_first_increment(fake_redis):
    check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60)
    ttl = fake_redis.ttl("ratelimit:ip:1.2.3.4:test")
    assert 0 < ttl <= 60
